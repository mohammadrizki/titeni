from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.access import configurable_programs
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.adaptive.models import EvaluationRuleVersion, EvidenceEvaluation
from apps.evidence.models import LearnerEvidenceBaseline
from apps.reflection.models import ReflectionAdvisorAssignment
from apps.reflection.sharing import posted_pk

from .intervention_eligibility import current_intervention_evaluations
from .models import (
    InterventionApproval,
    InterventionCompletionReport,
    InterventionDraft,
    ReassessmentRequirement,
)


class InterventionForm(forms.ModelForm):
    class Meta:
        model = InterventionDraft
        fields = ("activity", "rationale", "expected_outcome")


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def intervention_drafts(request: HttpRequest, assignment_id: int | None = None) -> HttpResponse:
    actor = cast(User, request.user)
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        account__is_active=True,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_interventiondraft",
    ).values("program_id")
    assignments = ReflectionAdvisorAssignment.objects.filter(
        advisor=actor,
        revoked_at__isnull=True,
        enrollment__cohort__period__program_id__in=programs,
    ).select_related("enrollment__learner__account")
    if assignment_id is None:
        if request.method == "POST":
            raise Http404
        return render(request, "learning/interventions.html", {"assignments": assignments})

    assignment = get_object_or_404(assignments, pk=assignment_id)
    baselines = LearnerEvidenceBaseline.objects.filter(enrollment=assignment.enrollment)
    writing = request.method == "POST"
    with transaction.atomic():
        if writing:
            assignment = get_object_or_404(
                assignments.select_for_update(of=("self",)), pk=assignment_id
            )
            baselines = baselines.select_for_update(of=("self",))
        baseline = baselines.first()
        eligible = (
            EvidenceEvaluation.objects.filter(pk__in=current_intervention_evaluations(baseline))
            if baseline
            else EvidenceEvaluation.objects.none()
        ).select_related("rule__standard__standard__item")
        form = InterventionForm(request.POST if writing else None)
        form.fields["evaluation"] = forms.ModelChoiceField(
            label="Indikasi intervensi", queryset=eligible
        )
        if writing and form.is_valid():
            draft = form.save(commit=False)
            draft.assignment = assignment
            draft.evaluation = form.cleaned_data["evaluation"]
            draft.save()
            return redirect("intervention_drafts", assignment.pk)

    can_verify = verification_assignments(actor).filter(pk=assignment.pk).exists()
    return render(
        request,
        "learning/interventions.html",
        {
            "assignment": assignment,
            "form": form,
            "has_indications": eligible.exists(),
            "drafts": InterventionDraft.objects.filter(assignment=assignment)
            .select_related("evaluation__rule__standard__standard__item")
            .order_by("-pk"),
            "reports": completion_reports(assignment).select_related(
                "approval__draft__evaluation__rule__standard__standard__item", "reassessment"
            )
            if can_verify
            else (),
            "can_verify": can_verify,
        },
    )


def can_approve_interventions(actor: User, program_id: int) -> bool:
    return UserRoleAssignment.objects.filter(
        account=actor,
        account__is_active=True,
        program_id=program_id,
        role__scope=AccessRole.Scope.PROGRAM,
        role__name="Kaprodi",
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_interventionapproval",
    ).exists()


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def approve_intervention(request: HttpRequest, program_id: int, baseline_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    baseline = get_object_or_404(
        LearnerEvidenceBaseline,
        pk=baseline_id,
        enrollment__cohort__period__program_id=program_id,
        enrollment__cohort__period__program__in=configurable_programs(actor),
    )
    if not can_approve_interventions(actor, program_id):
        raise PermissionDenied
    drafts = InterventionDraft.objects.filter(
        evaluation__baseline=baseline, assignment__enrollment_id=baseline.enrollment_id
    ).select_related("interventionapproval", "evaluation__rule__standard__standard__item")
    error = ""
    with transaction.atomic():
        if request.method == "POST":
            LearnerEvidenceBaseline.objects.select_for_update().get(pk=baseline.pk)
            draft = get_object_or_404(drafts, pk=posted_pk(request, "draft"))
            if hasattr(draft, "interventionapproval"):
                return redirect("intervention_approvals", program_id, baseline.pk)
            EvaluationRuleVersion.objects.select_for_update().get(pk=draft.evaluation.rule_id)
            eligible = current_intervention_evaluations(baseline)
            if draft.evaluation_id not in eligible:
                error = "Indikasi intervensi sudah tidak berlaku."
            else:
                InterventionApproval.objects.create(draft=draft, approved_by=actor)
                return redirect("intervention_approvals", program_id, baseline.pk)
        else:
            eligible = current_intervention_evaluations(baseline)
    return render(
        request,
        "learning/intervention_approvals.html",
        {
            "baseline": baseline,
            "drafts": drafts,
            "eligible": eligible,
            "error": error,
        },
        status=409 if error else 200,
    )


@never_cache
@login_required
@require_POST
def report_intervention_completion(
    request: HttpRequest, enrollment_id: int, approval_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        account__is_active=True,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_interventioncompletionreport",
    ).values("program_id")
    approval = get_object_or_404(
        InterventionApproval,
        pk=approval_id,
        draft__assignment__enrollment_id=enrollment_id,
        draft__evaluation__baseline__enrollment_id=enrollment_id,
        draft__assignment__enrollment__learner__account=actor,
        draft__assignment__enrollment__cohort__period__program_id__in=programs,
    )
    InterventionCompletionReport.objects.get_or_create(
        approval=approval, defaults={"reported_by": actor}
    )
    return redirect("learning_plan", enrollment_id)


def verification_assignments(actor: User) -> QuerySet[ReflectionAdvisorAssignment]:
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        account__is_active=True,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_reassessmentrequirement",
    ).values("program_id")
    return ReflectionAdvisorAssignment.objects.filter(
        advisor=actor, revoked_at__isnull=True, enrollment__cohort__period__program_id__in=programs
    )


def completion_reports(
    assignment: ReflectionAdvisorAssignment,
) -> QuerySet[InterventionCompletionReport]:
    return InterventionCompletionReport.objects.filter(
        approval__draft__assignment__enrollment_id=assignment.enrollment_id,
        approval__draft__evaluation__baseline__enrollment_id=assignment.enrollment_id,
        reported_by_id=assignment.enrollment.learner.account_id,
    ).order_by("-reported_at", "-pk")


@never_cache
@login_required
@require_POST
@transaction.atomic
def verify_intervention_completion(
    request: HttpRequest, assignment_id: int, report_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    assignment = get_object_or_404(
        verification_assignments(actor).select_for_update(of=("self",)), pk=assignment_id
    )
    completion = get_object_or_404(
        completion_reports(assignment).select_related("approval__draft__evaluation"), pk=report_id
    )
    LearnerEvidenceBaseline.objects.select_for_update().get(
        pk=completion.approval.draft.evaluation.baseline_id
    )
    ReassessmentRequirement.objects.get_or_create(
        completion=completion, defaults={"verified_assignment": assignment}
    )
    return redirect("intervention_drafts", assignment.pk)
