import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.exam_imports.adapters import ADAPTERS, MAX_FILE_BYTES, Adapter
from apps.assessments.models import (
    AssessmentEvent,
    BlueprintItem,
    ExamImportProtocol,
    ExamResultImport,
    ImportedExamResult,
)

SIGNING_SALT = "titeni.exam-results.v1"
MAX_TOKEN_BYTES = 1_500_000
VIEW_PERMISSION = "assessments.view_examresultimport"
ADD_PERMISSION = "assessments.add_examresultimport"


def authorized_events(actor: User, *, write: bool = False) -> QuerySet[AssessmentEvent]:
    permissions = {VIEW_PERMISSION, ADD_PERMISSION} if write else {VIEW_PERMISSION}
    remaining = {permission for permission in permissions if not actor.has_perm(permission)}
    programs = configurable_programs(actor)
    allowed = (
        programs
        if not remaining
        else [
            program
            for program in programs
            if remaining <= program_role_permissions(actor, program.pk)
        ]
    )
    return AssessmentEvent.objects.filter(
        component__version__blueprint__program__in=allowed
    ).select_related("component__version__blueprint__program")


def positive_pk(value: str) -> int | None:
    if value.isascii() and value.isdecimal() and len(value) <= 19:
        number = int(value)
        if 0 < number <= 2**63 - 1:
            return number
    return None


class ExamUploadForm(forms.Form):
    file = forms.FileField(label="Berkas hasil ujian")

    def __init__(self, *args, adapter: Adapter, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.adapter = adapter
        self.fields["file"].widget.attrs["accept"] = adapter.extension

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > MAX_FILE_BYTES:
            raise forms.ValidationError("Ukuran maksimum berkas adalah 3 MiB.")
        if Path(upload.name).suffix.lower() != self.adapter.extension:
            raise forms.ValidationError(f"Gunakan berkas {self.adapter.extension}.")
        return upload


@never_cache
@require_safe
@login_required
def index(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    protocols = list(ExamImportProtocol.objects.filter(active=True))
    write_events = authorized_events(actor, write=True)
    methods = (
        list(
            write_events.order_by("component__method")
            .values_list("component__method", flat=True)
            .distinct()
        )
        if protocols
        else []
    )
    requested_method = request.GET.get("method", "")
    method = requested_method if requested_method in methods else ""
    method_events = write_events.filter(component__method=method) if method else write_events.none()
    components = (
        BlueprintItem.objects.filter(pk__in=method_events.order_by().values("component_id"))
        .select_related("version__blueprint__program")
        .order_by("name", "code", "pk")
    )
    component_id = positive_pk(request.GET.get("component", ""))
    component = components.filter(pk=component_id).first() if component_id is not None else None
    dates = (
        method_events.filter(component=component).order_by("-occurred_on", "name", "pk")
        if component is not None
        else method_events.none()
    )
    event_id = positive_pk(request.GET.get("event", ""))
    event = dates.filter(pk=event_id).first() if event_id is not None else None
    return render(
        request,
        "assessments/exam_import_index.html",
        {
            "protocols": protocols,
            "methods": methods,
            "method": method,
            "components": components,
            "component": component,
            "dates": dates,
            "event": event,
            "history": ExamResultImport.objects.filter(
                event__in=authorized_events(actor)
            ).select_related("event__component__version__blueprint__program")[:30],
        },
    )


def configuration_signature(protocol: ExamImportProtocol) -> str:
    return json.dumps([protocol.engine, protocol.options], sort_keys=True)


@never_cache
@require_http_methods(["GET", "POST"])
@login_required
def exam_import(request: HttpRequest, adapter_slug: str) -> HttpResponse:
    protocol = get_object_or_404(ExamImportProtocol, slug=adapter_slug, active=True)
    adapter = ADAPTERS[protocol.engine]
    actor = cast(User, request.user)
    events = authorized_events(actor)
    write_events = authorized_events(actor, write=True)
    method = request.GET.get("method", "")
    component_id = positive_pk(request.GET.get("component", ""))
    event_id = positive_pk(request.GET.get("event", ""))
    if not method or component_id is None or event_id is None:
        if request.method == "GET":
            return redirect("exam_imports:index")
        if not write_events.exists():
            raise PermissionDenied
        return HttpResponse("Pilih metode, jenis, dan tanggal ujian terlebih dahulu.", status=400)
    selected_events = write_events.filter(component__method=method, component_id=component_id)
    event = get_object_or_404(selected_events, pk=event_id)
    form = ExamUploadForm(adapter=adapter)
    results = None
    token = ""
    error = ""
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "preview":
            form = ExamUploadForm(request.POST, request.FILES, adapter=adapter)
            if form.is_valid():
                content = form.cleaned_data["file"].read(MAX_FILE_BYTES + 1)
                options = protocol.options
                try:
                    results = adapter.read(content, options)
                except ValidationError as invalid:
                    form.add_error("file", invalid)
                else:
                    if not results.errors:
                        fingerprint = sha256(content + json.dumps(options, sort_keys=True).encode())
                        token = signing.dumps(
                            [
                                str(actor.pk),
                                protocol.slug,
                                configuration_signature(protocol),
                                event.pk,
                                fingerprint.hexdigest(),
                                [asdict(row) for row in results.results],
                            ],
                            salt=SIGNING_SALT,
                            compress=True,
                        )
                        if len(token) > MAX_TOKEN_BYTES:
                            token = ""
                            error = "Hasil pratinjau terlalu besar. Bagi hasil ke beberapa berkas."
        elif action == "import":
            submitted = request.POST.get("preview_token", "")
            try:
                owner, protocol_key, signature, preview_event_id, digest, rows = signing.loads(
                    submitted,
                    salt=SIGNING_SALT,
                    max_age=1800,
                )
            except (signing.BadSignature, ValueError):
                error = "Pratinjau tidak berlaku. Unggah kembali berkas."
            else:
                if (
                    owner != str(actor.pk)
                    or protocol_key != protocol.slug
                    or preview_event_id != event.pk
                ):
                    return HttpResponse(status=400)
                with transaction.atomic():
                    current = get_object_or_404(
                        ExamImportProtocol.objects.select_for_update(), pk=protocol.pk, active=True
                    )
                    if signature != configuration_signature(current):
                        return HttpResponse(
                            "Pengaturan protokol berubah. Buat pratinjau baru.", status=409
                        )
                    event = get_object_or_404(
                        selected_events.select_for_update(of=("self",)), pk=event.pk
                    )
                    batch, created = ExamResultImport.objects.get_or_create(
                        event=event,
                        adapter=protocol.slug,
                        digest=digest,
                        defaults={
                            "source_label": current.name,
                            "row_count": len(rows),
                            "created_by": actor,
                        },
                    )
                    if created:
                        ImportedExamResult.objects.bulk_create(
                            [
                                ImportedExamResult(
                                    batch=batch,
                                    row_number=row["row"],
                                    participant=row["participant"],
                                    score=row["score"],
                                    raw_score=row["raw_score"],
                                    maximum=row["maximum"],
                                    session=row["session"],
                                    status=row["status"],
                                )
                                for row in rows
                            ]
                        )
                return redirect("exam_imports:batch", batch_id=batch.pk)
        else:
            return HttpResponse(status=400)
    history = ExamResultImport.objects.filter(
        event__in=events, adapter=protocol.slug
    ).select_related("event__component__version__blueprint__program")[:30]
    return render(
        request,
        "assessments/exam_import.html",
        {
            "protocol": protocol,
            "extension": adapter.extension,
            "form": form,
            "event": event,
            "results": results,
            "token": token,
            "error": error,
            "history": history,
        },
        status=400 if error else 200,
    )


@never_cache
@require_safe
@login_required
def batch_results(request: HttpRequest, batch_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    batch = get_object_or_404(
        ExamResultImport.objects.select_related("event__component__version__blueprint__program"),
        pk=batch_id,
        event__in=authorized_events(actor),
    )
    return render(
        request,
        "assessments/exam_import_batch.html",
        {
            "batch": batch,
            "protocol_active": ExamImportProtocol.objects.filter(
                slug=batch.adapter, active=True
            ).exists(),
            "page": Paginator(batch.results.all(), 100).get_page(request.GET.get("page")),
        },
    )
