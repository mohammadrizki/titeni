from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User
from apps.assessments.models import ExamImportProtocol

DELIMITERS = {"comma": ",", "semicolon": ";", "tab": "\t"}
COLUMN_FIELDS = ("participant", "score", "raw_score", "session")


class ProtocolForm(forms.ModelForm):
    delimiter = forms.ChoiceField(
        label="Pemisah CSV",
        choices=[("comma", "Koma"), ("semicolon", "Titik koma"), ("tab", "Tab")],
    )
    participant = forms.CharField(label="Kolom pengenal peserta", max_length=120)
    score = forms.CharField(label="Kolom nilai akhir", max_length=120)
    raw_score = forms.CharField(label="Kolom nilai mentah", max_length=120, required=False)
    session = forms.CharField(label="Kolom sesi", max_length=120, required=False)

    class Meta:
        model = ExamImportProtocol
        fields = ["name", "active"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.csv = self.instance.pk is None or self.instance.engine == ExamImportProtocol.Engine.CSV
        if self.csv and self.instance.pk is not None:
            for name in COLUMN_FIELDS:
                self.initial[name] = self.instance.options.get(name, "")
            self.initial["delimiter"] = next(
                (
                    key
                    for key, value in DELIMITERS.items()
                    if value == self.instance.options.get("delimiter")
                ),
                "comma",
            )
        if not self.csv:
            for name in ("delimiter", *COLUMN_FIELDS):
                del self.fields[name]
        self.order_fields(["name", "delimiter", *COLUMN_FIELDS, "active"])

    def clean(self) -> dict:
        super().clean()
        data = self.cleaned_data
        if self.csv:
            columns = [data.get(name) for name in COLUMN_FIELDS if data.get(name)]
            if len(set(columns)) != len(columns):
                self.add_error(None, "Gunakan nama kolom CSV yang berbeda untuk setiap pemetaan.")
        if self.instance.pk is None and data.get("name"):
            slug = slugify(data["name"])[:40].strip("-")
            if not slug or slug in {"pengaturan", "batch"}:
                self.add_error("name", "Gunakan nama aplikasi yang dapat dijadikan alamat menu.")
            elif ExamImportProtocol.objects.filter(slug=slug).exists():
                self.add_error("name", "Alamat menu aplikasi ini sudah digunakan.")
            else:
                self.instance.slug = slug
                self.instance.engine = ExamImportProtocol.Engine.CSV
        if self.csv and data.get("delimiter"):
            self.instance.options = {
                "delimiter": DELIMITERS[data["delimiter"]],
                **{name: data.get(name, "") for name in COLUMN_FIELDS},
            }
        return data


@require_http_methods(["GET", "POST"])
@login_required
def settings(request: HttpRequest, protocol_id: int | None = None) -> HttpResponse:
    actor = cast(User, request.user)
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    with transaction.atomic():
        writing = request.method == "POST"
        protocols = (
            ExamImportProtocol.objects.select_for_update()
            if writing
            else ExamImportProtocol.objects.all()
        )
        protocol = get_object_or_404(protocols, pk=protocol_id) if protocol_id is not None else None
        if writing and request.POST.get("action") == "toggle":
            if protocol is None or request.POST.get("active") not in {"0", "1"}:
                return HttpResponse(status=400)
            protocol.active = request.POST["active"] == "1"
            protocol.updated_by = actor
            protocol.save(update_fields=["active", "updated_by", "updated_at"])
            messages.success(request, "Status protokol impor diperbarui.")
            return redirect("exam_imports:settings")

        form = ProtocolForm(request.POST if writing else None, instance=protocol)
        if writing and form.is_valid():
            try:
                with transaction.atomic():
                    updated = form.save(commit=False)
                    updated.updated_by = actor
                    updated.save()
            except IntegrityError:
                form.add_error("name", "Nama atau alamat menu aplikasi sudah digunakan.")
            else:
                messages.success(request, "Protokol impor disimpan.")
                return redirect("exam_imports:settings")
    return render(
        request,
        "assessments/exam_import_settings.html",
        {"form": form, "editing": protocol, "protocols": ExamImportProtocol.objects.all()},
    )
