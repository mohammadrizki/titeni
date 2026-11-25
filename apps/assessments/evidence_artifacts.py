import re
from hashlib import sha256
from pathlib import Path
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed, require_evidence_view, scoped_evidence_attempts
from apps.evidence.models import EvidenceArtifact, EvidenceRecord

MAX_PDF_SIZE = 10 * 1024 * 1024


class ArtifactForm(forms.Form):
    file = forms.FileField(
        label="Lampiran PDF", widget=forms.FileInput(attrs={"accept": ".pdf,application/pdf"})
    )

    def clean_file(self) -> UploadedFile:
        upload = self.cleaned_data["file"]
        if upload.size > MAX_PDF_SIZE:
            raise forms.ValidationError("Ukuran PDF maksimal 10 MiB.")
        if Path(upload.name).suffix.lower() != ".pdf":
            raise forms.ValidationError("Unggah berkas berformat PDF.")
        header = upload.read(16)
        upload.seek(max(0, upload.size - 1024))
        tail = upload.read().rstrip()
        upload.seek(0)
        if not re.match(rb"%PDF-(?:1\.[0-7]|2\.0)[\r\n]", header) or not tail.endswith(b"%%EOF"):
            raise forms.ValidationError("Berkas tidak memiliki format PDF yang dapat dikenali.")
        return upload


def scoped_artifact_record(
    request: HttpRequest, program_id: int, event_id: int, attempt_id: int, record_id: int
):
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    require_evidence_view(actor, roles)
    attempt = get_object_or_404(scoped_evidence_attempts(program, event_id), pk=attempt_id)
    record = get_object_or_404(attempt.evidence_records.all(), pk=record_id)
    return actor, roles, program, attempt, record


@require_POST
@login_required
def upload_artifact(
    request: HttpRequest, program_id: int, event_id: int, attempt_id: int, record_id: int
) -> HttpResponse:
    actor, roles, program, attempt, record = scoped_artifact_record(
        request, program_id, event_id, attempt_id, record_id
    )
    if not allowed(actor, roles, "evidence.add_evidencerecord"):
        raise PermissionDenied
    form = ArtifactForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        digest = sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(0)
        stored: EvidenceArtifact | None = None
        try:
            with transaction.atomic():
                record = get_object_or_404(EvidenceRecord.objects.select_for_update(), pk=record_id)
                if hasattr(record, "superseded_by") or hasattr(record, "invalidation"):
                    return HttpResponse(
                        "Lampiran hanya dapat ditambahkan pada versi bukti yang aktif.", status=409
                    )
                checksum = digest.hexdigest()
                if not record.artifacts.filter(sha256=checksum).exists():
                    stored = EvidenceArtifact(
                        record=record,
                        created_by=actor,
                        original_name=upload.name,
                        size_bytes=upload.size,
                        sha256=checksum,
                    )
                    stored.file.save(upload.name, upload, save=False)
                    stored.save(force_insert=True)
        except Exception:
            if stored is not None and stored.file.name:
                stored.file.delete(save=False)
            raise
        return redirect(
            "academics:assessments:verify_evidence",
            program_id=program_id,
            event_id=event_id,
            attempt_id=attempt_id,
            record_id=record_id,
        )
    return render(
        request,
        "assessments/upload_artifact.html",
        {
            "program": program,
            "attempt": attempt,
            "event": attempt.participation.event,
            "record": record,
            "form": form,
        },
        status=400,
    )


@require_safe
@login_required
def download_artifact(
    request: HttpRequest,
    program_id: int,
    event_id: int,
    attempt_id: int,
    record_id: int,
    artifact_id: int,
) -> FileResponse:
    _, _, _, _, record = scoped_artifact_record(
        request, program_id, event_id, attempt_id, record_id
    )
    artifact = get_object_or_404(record.artifacts.all(), pk=artifact_id)
    try:
        stream = artifact.file.open("rb")
    except FileNotFoundError as error:
        raise Http404 from error
    response = FileResponse(
        stream, as_attachment=True, filename=artifact.original_name, content_type="application/pdf"
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
