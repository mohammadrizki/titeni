from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.adaptive.models import EvidenceEvaluation
from apps.adaptive.recalculation import reevaluate_for_evidence
from apps.assessments.acquisition import allowed, require_evidence_view
from apps.evidence.matching import baseline_requirements, candidates, resolve_placement
from apps.evidence.models import EvidencePlacement, EvidenceRecord, LearnerEvidenceBaseline
from apps.evidence.plans import can_access_plan


class PlacementForm(forms.Form):
    record_id = forms.IntegerField(min_value=1)
    requirement_number = forms.IntegerField(min_value=1)
    reason = forms.CharField(label="Alasan penempatan", max_length=500)


@require_http_methods(["GET", "POST"])
@login_required
def reconcile(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    roles = program_role_permissions(actor, program_id)
    if not can_access_plan(actor, program_id, "view"):
        raise PermissionDenied
    require_evidence_view(actor, roles)
    baseline = get_object_or_404(
        LearnerEvidenceBaseline.objects.select_related(
            "enrollment__learner__account",
            "enrollment__cohort__period__program",
            "publication__version",
        ),
        enrollment_id=enrollment_id,
        enrollment__cohort__period__program_id=program_id,
        enrollment__cohort__period__program__in=configurable_programs(actor),
        publication__artifact_map__program_id=program_id,
    )
    requirements = baseline_requirements(baseline)
    can_place = allowed(actor, roles, "evidence.add_evidenceplacement")
    records = EvidenceRecord.objects.filter(
        attempt__participation__enrollment_id=enrollment_id,
        attempt__participation__event__component__version__blueprint__program_id=program_id,
    )
    error = ""
    if request.method == "POST":
        if not can_place:
            raise PermissionDenied
        form = PlacementForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                record_id = form.cleaned_data["record_id"]
                get_object_or_404(records.select_for_update(), pk=record_id)
                record = (
                    records.eligible_for_reconciliation()
                    .select_related("source_link")
                    .filter(pk=record_id)
                    .first()
                )
                if record is None:
                    return HttpResponse("Versi bukti ini sudah tidak layak dihitung.", status=409)
                choices = candidates(record, requirements)
                number = form.cleaned_data["requirement_number"]
                if not any(choice.requirement.number == number for choice in choices):
                    error = "Persyaratan ini tidak cocok untuk bukti yang dipilih."
                elif len(choices) == 1 and choices[0].automatic:
                    error = "Bukti ini sudah dihitung otomatis."
                else:
                    stored, created = EvidencePlacement.objects.get_or_create(
                        record=record,
                        defaults={
                            "baseline": baseline,
                            "requirement_number": number,
                            "reason": form.cleaned_data["reason"],
                            "created_by": actor,
                        },
                    )
                    if not created and (
                        stored.baseline_id != baseline.pk or stored.requirement_number != number
                    ):
                        return HttpResponse("Bukti ini sudah memiliki penempatan.", status=409)
                    if created:
                        reevaluate_for_evidence(record, actor, EvidenceEvaluation.Trigger.PLACEMENT)
                    return redirect(
                        "academics:evidence:reconcile",
                        program_id=program_id,
                        enrollment_id=enrollment_id,
                    )
        else:
            error = "Pilih persyaratan dan isi alasan penempatan."

    counts = {requirement.number: 0 for requirement in requirements}
    counted = []
    pending = []
    for record in records.eligible_for_reconciliation().select_related(
        "source_link__capability__source",
        "source_link__capability__evidence_type",
        "placement__created_by",
    ):
        choices = candidates(record, requirements)
        requirement, placement = resolve_placement(record, baseline, choices)
        if requirement is not None:
            counts[requirement.number] += 1
            counted.append({"record": record, "requirement": requirement, "placement": placement})
        else:
            pending.append({"record": record, "choices": choices})

    return render(
        request,
        "evidence/reconciliation.html",
        {
            "program": baseline.enrollment.cohort.period.program,
            "baseline": baseline,
            "progress": [(requirement, counts[requirement.number]) for requirement in requirements],
            "counted": counted,
            "pending": pending,
            "can_place": can_place,
            "can_evaluate": allowed(actor, roles, "adaptive.view_evidenceevaluation"),
            "error": error,
        },
        status=400 if error else 200,
    )
