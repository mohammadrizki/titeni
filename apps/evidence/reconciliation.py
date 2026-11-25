from dataclasses import dataclass
from typing import Any, cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed, require_evidence_view
from apps.evidence.models import EvidencePlacement, EvidenceRecord, LearnerEvidenceBaseline
from apps.evidence.plans import can_access_plan


@dataclass(frozen=True)
class Requirement:
    number: int
    origin: str
    entry: dict[str, Any]

    @property
    def label(self) -> str:
        return (
            self.entry.get("label") or self.entry.get("component") or f"Persyaratan {self.number}"
        )

    @property
    def minimum(self) -> int:
        return self.entry.get("minimum", self.entry.get("minimum_observations", 0))


@dataclass(frozen=True)
class Match:
    requirement: Requirement
    automatic: bool


def match(record: EvidenceRecord, requirement: Requirement) -> Match | None:
    entry = requirement.entry
    capability_id = record.source_link.capability_id
    if requirement.origin == "manual":
        expected_capability = entry.get("capability_id")
        if expected_capability is None or expected_capability == capability_id:
            return Match(requirement, automatic=False)
        return None

    component_id = entry.get("component_id")
    source_ids = {
        source["capability_id"]
        for source in entry.get("sources", [])
        if source.get("capability_id")
    }
    if component_id is not None and component_id != record.source_link.item_id:
        return None
    if source_ids and capability_id not in source_ids:
        return None
    expected_context = entry.get("context", "").strip().casefold()
    observed_context = record.context.strip().casefold()
    if expected_context and observed_context and expected_context != observed_context:
        return None
    automatic = bool(component_id and source_ids and expected_context and observed_context)
    return Match(requirement, automatic=automatic)


def candidates(record: EvidenceRecord, requirements: list[Requirement]) -> list[Match]:
    return [candidate for requirement in requirements if (candidate := match(record, requirement))]


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
    requirements = [
        Requirement(number, row["origin"], row["entry"])
        for number, row in enumerate(baseline.publication.requirements, start=1)
    ]
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
        placement = getattr(record, "placement", None)
        chosen = next(
            (
                choice
                for choice in choices
                if placement is not None
                and placement.baseline_id == baseline.pk
                and choice.requirement.number == placement.requirement_number
            ),
            None,
        )
        if chosen is not None:
            counts[chosen.requirement.number] += 1
            counted.append(
                {"record": record, "requirement": chosen.requirement, "placement": placement}
            )
        elif len(choices) == 1 and choices[0].automatic:
            requirement = choices[0].requirement
            counts[requirement.number] += 1
            counted.append({"record": record, "requirement": requirement})
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
            "error": error,
        },
        status=400 if error else 200,
    )
