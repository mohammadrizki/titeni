from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.academics.models import StudyProgram
from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.evidence.models import ArtifactMapPublication, ArtifactMapVersion

PUBLISH_PERMISSION = "evidence.add_artifactmappublication"


def can_publish(actor: User, program_id: int) -> bool:
    return actor.has_perm(PUBLISH_PERMISSION) or (
        PUBLISH_PERMISSION in program_role_permissions(actor, program_id)
    )


class PublicationForm(forms.Form):
    effective_on = forms.DateField(
        label="Tanggal efektif", widget=forms.DateInput(attrs={"type": "date"})
    )


class RequirementSelection(forms.Form):
    selected = forms.BooleanField(label="Berlaku", required=False)
    due_on = forms.DateField(
        label="Tenggat", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    responsible = forms.CharField(label="Penanggung jawab", required=False, max_length=200)


@require_http_methods(["GET", "POST"])
@login_required
def publish_artifact_map(request: HttpRequest, program_id: int, map_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if not can_publish(actor, program_id):
        raise PermissionDenied
    version = get_object_or_404(
        ArtifactMapVersion.objects.select_related("artifact_map"),
        pk=map_id,
        artifact_map__program=program,
        blueprint_version__blueprint__program=program,
    )
    back_url = reverse("academics:evidence:saved_artifact_map", args=[program_id, map_id])
    if hasattr(version, "publication"):
        return redirect(back_url)

    data = request.POST if request.method == "POST" else None
    form = PublicationForm(data)
    rows = [
        {
            "origin": origin,
            "entry": entry,
            "form": RequirementSelection(data, prefix=f"{origin}-{index}"),
        }
        for origin, entries in (
            ("manual", version.snapshot.get("requirements", [])),
            ("blueprint", version.snapshot.get("blueprint_proposals", [])),
        )
        for index, entry in enumerate(entries)
    ]
    if request.method == "POST":
        selections_valid = all([row["form"].is_valid() for row in rows])
        if form.is_valid() and selections_valid:
            requirements = []
            for row in rows:
                values = row["form"].cleaned_data
                if values["selected"]:
                    due_on = values["due_on"]
                    requirements.append(
                        {
                            "origin": row["origin"],
                            "entry": row["entry"],
                            "due_on": due_on.isoformat() if due_on else "",
                            "responsible": values["responsible"],
                        }
                    )
            if not requirements:
                form.add_error(None, "Pilih setidaknya satu persyaratan untuk diterbitkan.")
            else:
                effective_on = form.cleaned_data["effective_on"]
                with transaction.atomic():
                    # Enrollment resolves the effective publication under the same lock.
                    StudyProgram.objects.select_for_update().get(pk=program_id)
                    if ArtifactMapPublication.objects.filter(version=version).exists():
                        return redirect(back_url)
                    if ArtifactMapPublication.objects.filter(
                        artifact_map=version.artifact_map, effective_on=effective_on
                    ).exists():
                        form.add_error(
                            "effective_on", "Tanggal ini sudah dipakai oleh versi terbit."
                        )
                    else:
                        ArtifactMapPublication.objects.create(
                            artifact_map=version.artifact_map,
                            version=version,
                            effective_on=effective_on,
                            requirements=requirements,
                            created_by=actor,
                        )
                        messages.success(request, "Peta artefak berhasil diterbitkan.")
                        return redirect(back_url)

    return render(
        request,
        "evidence/publish_artifact_map.html",
        {"program": program, "version": version, "form": form, "rows": rows},
    )
