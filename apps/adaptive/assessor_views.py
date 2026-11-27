from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import OuterRef, QuerySet, Subquery
from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from apps.accounts.access import configurable_programs
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.assessments.evidence_artifacts import private_pdf_response
from apps.evidence.models import EvidenceRecord

from .findings import revise_finding, submit_finding
from .models import AssessorFinding, AssessorFindingAssignment, ScheduledAssessorAssignment
from .views import FindingRevisionForm


def assessor_programs(actor: User) -> QuerySet:
    grants = UserRoleAssignment.objects.filter(
        account=actor,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="adaptive",
        role__permissions__codename="add_assessorfinding",
    ).values("program_id")
    return configurable_programs(actor).filter(pk__in=grants)


def scoped_assignments(actor: User) -> QuerySet[AssessorFindingAssignment]:
    programs = assessor_programs(actor)
    return AssessorFindingAssignment.objects.filter(
        assessor=actor,
        record__in=EvidenceRecord.objects.eligible_for_reconciliation(),
        record__attempt__participation__enrollment__cohort__period__program__in=programs,
        record__attempt__participation__event__component__version__blueprint__program__in=programs,
        standard__standard__item__version__framework__program__in=programs,
    ).select_related("record", "standard__standard__item")


class AssignedFindingForm(forms.Form):
    assignment = forms.ModelChoiceField(
        label="Penugasan", queryset=AssessorFindingAssignment.objects.none()
    )
    outcome = forms.ChoiceField(label="Temuan", choices=AssessorFinding.Outcome.choices)
    rationale = forms.CharField(label="Alasan", max_length=500)


@require_http_methods(["GET", "POST"])
@login_required
def assessor_assignments(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    assignments = scoped_assignments(actor)
    action = request.POST.get("action", "submit-finding") if request.method == "POST" else None
    form = AssignedFindingForm(request.POST if action == "submit-finding" else None)
    cast(forms.ModelChoiceField, form.fields["assignment"]).queryset = assignments.filter(
        finding__isnull=True
    )
    revision_form = FindingRevisionForm(request.POST if action == "revise-finding" else None)
    own_findings = (
        AssessorFinding.objects.filter(assignment__in=assignments)
        .select_related("assignment__record", "assignment__standard__standard__item")
        .prefetch_related("revisions")
    )
    cast(forms.ModelChoiceField, revision_form.fields["finding"]).queryset = own_findings
    if action == "submit-finding" and form.is_valid():
        try:
            submit_finding(actor=actor, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, ValidationError(error.messages))
        else:
            return redirect("assessor_assignments")
    if action == "revise-finding" and revision_form.is_valid():
        try:
            revise_finding(actor=actor, **revision_form.cleaned_data)
        except ValidationError as error:
            revision_form.add_error(None, ValidationError(error.messages))
        else:
            return redirect("assessor_assignments")
    latest = ScheduledAssessorAssignment.objects.filter(
        reservation_id=OuterRef("reservation_id")
    ).values("pk")[:1]
    scheduled = (
        ScheduledAssessorAssignment.objects.filter(
            pk=Subquery(latest),
            assessor=actor,
            reservation__released_at__isnull=True,
            reservation__attempt__isnull=True,
            reservation__baseline__enrollment__cohort__period__program__in=assessor_programs(actor),
            reservation__event__occurred_on__gte=timezone.localdate(),
        )
        .select_related("reservation__event", "reservation__baseline__enrollment__learner__account")
        .order_by("reservation__event__occurred_on", "pk")
    )
    return render(
        request,
        "adaptive/assessor_assignments.html",
        {
            "assignments": assignments.select_related("finding").prefetch_related(
                "record__artifacts"
            ),
            "form": form,
            "revision_form": revision_form,
            "own_findings": own_findings,
            "scheduled": scheduled,
            "finding_outcomes": AssessorFinding.Outcome.choices,
        },
    )


@require_safe
@login_required
def assessor_artifact(request: HttpRequest, assignment_id: int, artifact_id: int) -> FileResponse:
    assignment = get_object_or_404(scoped_assignments(cast(User, request.user)), pk=assignment_id)
    return private_pdf_response(get_object_or_404(assignment.record.artifacts, pk=artifact_id))
