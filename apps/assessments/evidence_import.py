import csv
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed, require_evidence_view, scoped_evidence_attempts
from apps.assessments.models import AssessmentAttempt, BlueprintItemEvidenceSource
from apps.evidence.models import EvidenceImportBatch, EvidenceRecord

HEADERS = ("kode_sumber", "kode_jenis_bukti", "referensi", "konteks")
MAX_BYTES = 128 * 1024
MAX_ROWS = 100
SIGNING_SALT = "titeni.evidence.csv.v1"


class UploadForm(forms.Form):
    file = forms.FileField(
        label="Berkas CSV", widget=forms.FileInput(attrs={"accept": ".csv,text/csv"})
    )


@dataclass
class ImportRow:
    line: int
    source: str
    evidence_type: str
    reference: str
    context: str
    link_id: int | None = None
    status: str = ""
    message: str = ""


def parse_csv(content: bytes) -> list[list[int | str]]:
    if len(content) > MAX_BYTES:
        raise ValidationError("Ukuran maksimum CSV adalah 128 KiB.")
    try:
        reader = csv.reader(StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        if tuple(next(reader, [])) != HEADERS:
            raise ValidationError("Kepala CSV harus sesuai dengan contoh.")
        entries: list[list[int | str]] = []
        for values in reader:
            if not values:
                continue
            if len(entries) >= MAX_ROWS:
                raise ValidationError("CSV dapat memuat paling banyak 100 baris data.")
            if len(values) != len(HEADERS):
                raise ValidationError(f"Baris {reader.line_num} harus memiliki empat kolom.")
            entries.append([reader.line_num, *(value.strip() for value in values)])
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValidationError("Gunakan CSV UTF-8 dengan format yang valid.") from error
    if not entries:
        raise ValidationError("CSV belum memuat baris data.")
    return entries


def assess_rows(
    attempt: AssessmentAttempt, entries: list, *, lock: bool = False
) -> tuple[list[ImportRow], list[EvidenceRecord]]:
    links = (
        BlueprintItemEvidenceSource.objects.filter(item_id=attempt.participation.event.component_id)
        .select_related("capability__source", "capability__evidence_type")
        .order_by("pk")
    )
    if lock:
        links = links.select_for_update(of=("self",))
    by_code = {
        (link.capability.source.code, link.capability.evidence_type.code): link for link in links
    }
    contexts: dict[tuple[int, str], set[str]] = {}
    for link_id, reference, context in attempt.evidence_records.values_list(
        "source_link_id", "reference", "context"
    ):
        contexts.setdefault((link_id, reference), set()).add(context)

    rows = []
    pending = []
    for values in entries:
        row = ImportRow(*values)
        rows.append(row)
        link = by_code.get((row.source, row.evidence_type))
        row.link_id = link.pk if link is not None else None
        if any("\x00" in value for value in values[1:]):
            row.status, row.message = "error", "Baris memuat karakter yang tidak didukung."
        elif link is None:
            row.status, row.message = "error", "Sumber dan jenis bukti tidak tertaut ke komponen."
        elif not row.reference or len(row.reference) > 160 or len(row.context) > 250:
            row.status, row.message = (
                "error",
                "Referensi wajib (maks. 160); konteks maks. 250 karakter.",
            )
        else:
            key = (link.pk, row.reference)
            seen = contexts.get(key)
            if seen is not None:
                if row.context in seen:
                    row.status, row.message = "duplicate", "Entri identik dilewati."
                else:
                    row.status, row.message = "error", "Referensi sudah ada dengan konteks berbeda."
            else:
                row.status, row.message = "ready", "Siap diimpor."
                contexts[key] = {row.context}
                pending.append(
                    EvidenceRecord(
                        attempt=attempt,
                        source_link=link,
                        reference=row.reference,
                        context=row.context,
                    )
                )
    return rows, pending


@require_http_methods(["GET", "POST"])
@login_required
def import_evidence(
    request: HttpRequest, program_id: int, event_id: int, attempt_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    require_evidence_view(actor, roles)
    if not allowed(actor, roles, "evidence.add_evidencerecord"):
        raise PermissionDenied

    attempts = scoped_evidence_attempts(program, event_id)
    attempt = get_object_or_404(attempts, pk=attempt_id)
    binding = [str(actor.pk), attempt_id]
    form = UploadForm()
    rows: list[ImportRow] = []
    token = ""
    error = ""
    imported = None
    skipped = 0
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "preview":
            form = UploadForm(request.POST, request.FILES)
            if form.is_valid():
                content = form.cleaned_data["file"].read(MAX_BYTES + 1)
                try:
                    entries = parse_csv(content)
                except ValidationError as invalid:
                    form.add_error("file", invalid)
                else:
                    rows, _ = assess_rows(attempt, entries)
                    if not any(row.status == "error" for row in rows):
                        token = signing.dumps(
                            [
                                binding,
                                sha256(content).hexdigest(),
                                entries,
                                [row.link_id for row in rows],
                            ],
                            salt=SIGNING_SALT,
                            compress=True,
                        )
        elif action == "import":
            try:
                signed_binding, digest, entries, preview_links = signing.loads(
                    request.POST.get("preview_token", ""), salt=SIGNING_SALT, max_age=1800
                )
            except (signing.BadSignature, ValueError):
                error = "Pratinjau tidak valid atau kedaluwarsa. Unggah ulang CSV."
            else:
                if signed_binding != binding:
                    return HttpResponse(status=400)
                with transaction.atomic():
                    attempt = get_object_or_404(
                        attempts.select_for_update(of=("self",)), pk=attempt_id
                    )
                    rows, pending = assess_rows(attempt, entries, lock=True)
                    if (
                        not any(row.status == "error" for row in rows)
                        and [row.link_id for row in rows] != preview_links
                    ):
                        error = "Tautan sumber berubah setelah pratinjau. Unggah ulang CSV."
                    if not error and not any(row.status == "error" for row in rows):
                        imported = len(pending)
                        skipped = sum(row.status == "duplicate" for row in rows)
                        if pending:
                            batch = EvidenceImportBatch.objects.create(
                                attempt=attempt,
                                file_digest=digest,
                                created_by=actor,
                                created_count=imported,
                                skipped_count=skipped,
                            )
                            for record in pending:
                                record.created_by = actor
                                record.import_batch = batch
                            EvidenceRecord.objects.bulk_create(pending)
                        for row in rows:
                            if row.status == "ready":
                                row.message = "Diimpor."
        else:
            return HttpResponse(status=400)

    return render(
        request,
        "assessments/evidence_import.html",
        {
            "program": program,
            "event": attempt.participation.event,
            "attempt": attempt,
            "form": form,
            "rows": rows,
            "token": token,
            "error": error,
            "imported": imported,
            "skipped": skipped,
        },
        status=400 if error else 200,
    )
