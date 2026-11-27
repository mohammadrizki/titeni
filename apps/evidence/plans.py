from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import can_view_evidence_records
from apps.evidence.models import ArtifactMapVersion, LearnerEvidencePlan


def can_access_plan(actor: User, program_id: int, action: str) -> bool:
    permission = f"evidence.{action}_learnerevidenceplan"
    roles = program_role_permissions(actor, program_id)
    return (
        actor.has_perm("academics.view_learnerenrollment")
        or "academics.view_learnerenrollment" in roles
    ) and (actor.has_perm(permission) or permission in roles)


class MapVersionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: ArtifactMapVersion) -> str:
        return f"Peta versi {obj.number} · Blueprint versi {obj.blueprint_version.number}"


class PlanDraftForm(forms.Form):
    artifact_map_version = MapVersionChoiceField(
        label="Versi peta artefak", queryset=ArtifactMapVersion.objects.none()
    )

    def __init__(self, *args, program_id: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = cast(MapVersionChoiceField, self.fields["artifact_map_version"])
        field.queryset = (
            ArtifactMapVersion.objects.filter(
                artifact_map__program_id=program_id,
                blueprint_version__blueprint__program_id=program_id,
            )
            .select_related("blueprint_version")
            .defer("snapshot")
        )


@require_http_methods(["GET", "POST"])
@login_required
def plan_drafts(
    request: HttpRequest, program_id: int, enrollment_id: int, plan_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    if not can_access_plan(actor, program_id, "view"):
        raise PermissionDenied
    enrollment = get_object_or_404(
        LearnerEnrollment.objects.select_related(
            "learner__account", "cohort__period__program", "evidence_baseline__publication__version"
        ),
        pk=enrollment_id,
        cohort__period__program_id=program_id,
        cohort__period__program__in=configurable_programs(actor),
    )
    plans = enrollment.evidence_plan_drafts.filter(
        artifact_map_version__artifact_map__program_id=program_id,
        artifact_map_version__blueprint_version__blueprint__program_id=program_id,
    ).select_related("artifact_map_version")
    selected = get_object_or_404(plans, pk=plan_id) if plan_id is not None else None
    can_add = can_access_plan(actor, program_id, "add")
    form = None
    if request.method == "POST":
        if plan_id is not None:
            return HttpResponse(status=405, headers={"Allow": "GET"})
        if not can_add:
            raise PermissionDenied
        form = PlanDraftForm(request.POST, program_id=program_id)
        if form.is_valid():
            draft, _ = LearnerEvidencePlan.objects.get_or_create(
                enrollment=enrollment,
                artifact_map_version=form.cleaned_data["artifact_map_version"],
                defaults={"created_by": actor},
            )
            return redirect(
                "academics:evidence:plan_draft",
                program_id=program_id,
                enrollment_id=enrollment_id,
                plan_id=draft.pk,
            )
    elif can_add and selected is None:
        form = PlanDraftForm(program_id=program_id)
    snapshot = selected.artifact_map_version.snapshot if selected is not None else {}
    return render(
        request,
        "evidence/plan_drafts.html",
        {
            "program": enrollment.cohort.period.program,
            "enrollment": enrollment,
            "plans": plans.defer("artifact_map_version__snapshot") if selected is None else None,
            "selected": selected,
            "baseline": getattr(enrollment, "evidence_baseline", None),
            "can_reconcile": can_view_evidence_records(
                actor, program_role_permissions(actor, program_id)
            ),
            "snapshot": snapshot,
            "has_blueprint_proposals": "blueprint_proposals" in snapshot,
            "form": form,
        },
    )
