from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import StudyProgram
from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed, can_view_evidence_records, require_evidence_view
from apps.competencies.models import PerformanceStandardVersion
from apps.evidence.matching import baseline_requirements
from apps.evidence.models import EvidenceRecord, LearnerEvidenceBaseline
from apps.evidence.plans import can_access_plan
from apps.learning.academic_advisors import (
    READ_PERMISSION,
    WRITE_PERMISSION,
    SynthesisForm,
    advisor_assignments,
    kaprodi_has_permission,
)
from apps.learning.intervention_eligibility import current_intervention_evaluations
from apps.learning.interventions import can_approve_interventions
from apps.learning.models import InterventionApproval, LongitudinalSynthesis
from apps.learning.sharing import advisor_goal_shares
from apps.reflection.sharing import recipient_shares

from .findings import (
    ASSESSOR_PERMISSION,
    ASSIGN_PERMISSION,
    assign_finding,
    revise_finding,
    submit_finding,
)
from .models import (
    AssessorFinding,
    AssessorFindingAssignment,
    AttemptReservation,
    EvaluationRuleVersion,
    EvidenceEvaluation,
)
from .performance import PerformanceThresholds, StandardFinding, evaluate_performance
from .policy_views import VIEW_POLICY
from .services import (
    PUBLISH_PERMISSION,
    StaleSimulationPreview,
    preview,
    preview_token,
    publish_rule,
    record_evaluation,
    retire_rule,
)


class RuleForm(forms.Form):
    standard = forms.ModelChoiceField(
        label="Versi standar performa", queryset=PerformanceStandardVersion.objects.none()
    )
    minimum_attempts = forms.IntegerField(
        label="Minimum percobaan unik", min_value=1, max_value=10000
    )
    minimum_contexts = forms.IntegerField(
        label="Minimum konteks unik", min_value=1, max_value=10000
    )
    minimum_verifiers = forms.IntegerField(
        label="Minimum verifikator unik", min_value=1, max_value=10000
    )
    minimum_sources = forms.IntegerField(
        label="Minimum sumber unik", min_value=1, max_value=10000, required=False
    )
    maximum_age_days = forms.IntegerField(
        label="Usia maksimum bukti (hari)", min_value=1, max_value=36500, required=False
    )


class PublicationForm(forms.Form):
    rule = forms.ModelChoiceField(
        label="Draf aturan produksi", queryset=EvaluationRuleVersion.objects.none()
    )
    minimum_below = forms.IntegerField(
        label="Minimum percobaan di bawah standar", min_value=1, max_value=10000
    )
    minimum_meets = forms.IntegerField(
        label="Minimum percobaan memenuhi standar", min_value=1, max_value=10000
    )


class EvaluationRuleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: EvaluationRuleVersion) -> str:
        mode = "Demonstrasi" if obj.demonstration else "Produksi"
        return f"{obj} · {mode}"


class SimulationForm(forms.Form):
    preview_token = forms.CharField(max_length=64, required=False, widget=forms.HiddenInput)
    rule = EvaluationRuleChoiceField(
        label="Versi aturan evaluasi", queryset=EvaluationRuleVersion.objects.none()
    )


class PerformanceDemonstrationForm(forms.Form):
    sufficiency = forms.ChoiceField(
        label="Kecukupan bukti sintetis", choices=EvidenceEvaluation.Sufficiency.choices
    )
    below = forms.IntegerField(label="Percobaan di bawah standar", min_value=0, max_value=100)
    meets = forms.IntegerField(label="Percobaan memenuhi standar", min_value=0, max_value=100)
    minimum_below = forms.IntegerField(
        label="Minimum untuk temuan terbuka", min_value=1, max_value=100
    )
    minimum_meets = forms.IntegerField(
        label="Minimum untuk temuan tertutup", min_value=1, max_value=100
    )


class AssignmentForm(forms.Form):
    record = forms.ModelChoiceField(label="Revisi bukti", queryset=EvidenceRecord.objects.none())
    standard = forms.ModelChoiceField(
        label="Versi standar performa", queryset=PerformanceStandardVersion.objects.none()
    )
    assessor = forms.ModelChoiceField(label="Asesor", queryset=User.objects.none())


class FindingForm(forms.Form):
    assignment = forms.ModelChoiceField(
        label="Penugasan", queryset=AssessorFindingAssignment.objects.none()
    )
    outcome = forms.ChoiceField(label="Temuan asesor", choices=AssessorFinding.Outcome.choices)
    rationale = forms.CharField(label="Alasan", max_length=500)


class FindingRevisionForm(forms.Form):
    finding = forms.ModelChoiceField(queryset=AssessorFinding.objects.none())
    previous_number = forms.IntegerField(min_value=1)
    outcome = forms.ChoiceField(choices=AssessorFinding.Outcome.choices)
    rationale = forms.CharField(max_length=500)
    reason = forms.CharField(max_length=500)


class RetirementForm(forms.Form):
    rule = forms.ModelChoiceField(queryset=EvaluationRuleVersion.objects.none())
    reason = forms.CharField(max_length=500)


def scoped_evaluation_baseline(
    actor: User, program_id: int, enrollment_id: int
) -> tuple[StudyProgram, LearnerEvidenceBaseline, set[str]]:
    roles = program_role_permissions(actor, program_id)
    if not (
        can_access_plan(actor, program_id, "view")
        and allowed(actor, roles, "adaptive.view_evidenceevaluation")
    ):
        raise PermissionDenied
    require_evidence_view(actor, roles)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    return program, review_baseline(program, enrollment_id), roles


def review_baseline(program: StudyProgram, enrollment_id: int) -> LearnerEvidenceBaseline:
    return get_object_or_404(
        LearnerEvidenceBaseline.objects.select_related(
            "publication__version__blueprint_version", "enrollment__learner"
        ),
        enrollment_id=enrollment_id,
        enrollment__cohort__period__program=program,
        publication__artifact_map__program=program,
        publication__version__blueprint_version__blueprint__program=program,
        publication__version__blueprint_version__framework_version__framework__program=program,
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def longitudinal_review(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    scope = {"enrollment_id": enrollment_id, "enrollment__cohort__period__program_id": program_id}
    advisor = advisor_assignments(actor).filter(**scope).exists()
    head = kaprodi_has_permission(actor, program_id, READ_PERMISSION)
    if advisor or head:
        program = get_object_or_404(StudyProgram, pk=program_id)
        baseline = review_baseline(program, enrollment_id)
        roles = program_role_permissions(actor, program_id)
        can_open_evaluation = (
            can_access_plan(actor, program_id, "view")
            and allowed(actor, roles, "adaptive.view_evidenceevaluation")
            and can_view_evidence_records(actor, roles)
            and configurable_programs(actor).filter(pk=program_id).exists()
        )
    else:
        program, baseline, roles = scoped_evaluation_baseline(actor, program_id, enrollment_id)
        can_open_evaluation = True

    writing = request.method == "POST"
    writers = advisor_assignments(actor, WRITE_PERMISSION).filter(**scope)
    can_write = advisor and writers.exists()
    form = SynthesisForm(request.POST if writing else None) if can_write else None
    if writing:
        if form is None:
            raise PermissionDenied
        with transaction.atomic():
            assignment = get_object_or_404(writers.select_for_update(of=("self",)))
            if form.is_valid():
                synthesis = form.save(commit=False)
                synthesis.assignment = assignment
                synthesis.save()
                return redirect("academics:evidence:longitudinal_review", program_id, enrollment_id)

    can_review_evidence = advisor or can_open_evaluation
    blueprint = baseline.publication.version.blueprint_version
    evaluations = EvidenceEvaluation.objects.filter(
        baseline=baseline,
        rule__demonstration=False,
        rule__publication__isnull=False,
        rule__standard__standard__item__version_id=blueprint.framework_version_id,
    ).select_related("rule__standard__standard__item", "created_by")
    coverage = baseline.publication.version.snapshot.get("coverage", [])
    milestones = [row for row in coverage if row.get("milestones")]
    reservations = (
        AttemptReservation.objects.filter(baseline=baseline, evaluation__in=evaluations)
        .select_related("event", "evaluation__rule__standard__standard__item")
        .order_by("-event__occurred_on", "-pk")
        if can_open_evaluation and VIEW_POLICY in roles
        else ()
    )
    interventions = (
        InterventionApproval.objects.filter(
            draft__evaluation__in=evaluations,
            draft__assignment__enrollment_id=enrollment_id,
        )
        .select_related(
            "draft__evaluation__rule__standard__standard__item",
            "interventioncompletionreport__reassessment",
        )
        .order_by("-approved_at", "-pk")
        if can_open_evaluation and can_approve_interventions(actor, program_id)
        else ()
    )
    return render(
        request,
        "adaptive/longitudinal_review.html",
        {
            "program": program,
            "baseline": baseline,
            "synthesis_form": form,
            "can_read_syntheses": advisor or head,
            "syntheses": LongitudinalSynthesis.objects.filter(
                assignment__enrollment_id=enrollment_id
            ).select_related("assignment__advisor")
            if advisor or head
            else (),
            "can_open_evaluation": can_open_evaluation,
            "can_review_evidence": can_review_evidence,
            "requirements": baseline_requirements(baseline) if can_review_evidence else (),
            "milestones": milestones,
            "history": Paginator(evaluations, 25).get_page(request.GET.get("page"))
            if can_review_evidence
            else None,
            "reservations": reservations,
            "interventions": interventions,
            "shared_reflections": recipient_shares(actor)
            .filter(assignment__enrollment_id=enrollment_id)
            .order_by("-shared_at", "-pk"),
            "shared_goals": advisor_goal_shares(actor).filter(
                assignment__enrollment_id=enrollment_id
            ),
        },
        status=400 if writing else 200,
    )


@require_http_methods(["GET", "POST"])
@login_required
def evaluations(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program, baseline, roles = scoped_evaluation_baseline(actor, program_id, enrollment_id)
    standards = PerformanceStandardVersion.objects.filter(
        standard__item__version_id=baseline.publication.version.blueprint_version.framework_version_id
    ).select_related("standard__item")
    action = request.POST.get("action") if request.method == "POST" else None
    can_add_rule = allowed(actor, roles, "adaptive.add_evaluationruleversion")
    can_simulate = allowed(actor, roles, "adaptive.add_evidenceevaluation")
    can_publish = PUBLISH_PERMISSION in roles
    rule_form = RuleForm(request.POST if action in {"new-rule", "new-production-rule"} else None)
    cast(forms.ModelChoiceField, rule_form.fields["standard"]).queryset = standards
    simulation_form = SimulationForm(request.POST if action in {"preview", "record"} else None)
    rules = EvaluationRuleVersion.objects.filter(
        standard__in=standards, demonstration=True
    ).select_related("standard__standard__item", "retirement__created_by")
    production_rules = EvaluationRuleVersion.objects.filter(
        standard__in=standards, demonstration=False
    ).select_related(
        "standard__standard__item", "publication__created_by", "retirement__created_by"
    )
    cast(forms.ModelChoiceField, simulation_form.fields["rule"]).queryset = (
        EvaluationRuleVersion.objects.filter(standard__in=standards, retirement__isnull=True)
        .filter(Q(demonstration=True) | Q(publication__isnull=False))
        .select_related("standard__standard__item", "publication")
    )
    publication_form = PublicationForm(request.POST if action == "publish" else None)
    cast(
        forms.ModelChoiceField, publication_form.fields["rule"]
    ).queryset = production_rules.filter(publication__isnull=True)
    can_retire = allowed(actor, roles, "adaptive.add_evaluationruleretirement")
    retirement_form = RetirementForm(
        request.POST if action in {"retire", "retire-production"} else None
    )
    cast(forms.ModelChoiceField, retirement_form.fields["rule"]).queryset = (
        production_rules.filter(publication__isnull=False)
        if action == "retire-production"
        else rules
    )
    records = EvidenceRecord.objects.eligible_for_reconciliation().filter(
        attempt__participation__enrollment_id=baseline.enrollment_id,
        attempt__participation__event__component__version__blueprint__program=program,
    )
    can_assign = ASSIGN_PERMISSION in roles
    can_submit = ASSESSOR_PERMISSION in roles
    assignment_form = AssignmentForm(request.POST if action == "assign-finding" else None)
    cast(forms.ModelChoiceField, assignment_form.fields["record"]).queryset = records
    cast(forms.ModelChoiceField, assignment_form.fields["standard"]).queryset = standards
    cast(forms.ModelChoiceField, assignment_form.fields["assessor"]).queryset = (
        User.objects.filter(
            is_active=True,
            role_assignments__program=program,
            role_assignments__role__scope="program",
            role_assignments__role__permissions__content_type__app_label="adaptive",
            role_assignments__role__permissions__codename="add_assessorfinding",
        )
        .distinct()
        .order_by("username")
    )
    finding_form = FindingForm(request.POST if action == "submit-finding" else None)
    cast(
        forms.ModelChoiceField, finding_form.fields["assignment"]
    ).queryset = AssessorFindingAssignment.objects.filter(
        record__in=records, standard__in=standards, assessor=actor, finding__isnull=True
    ).select_related("record", "standard__standard__item")
    own_findings = (
        AssessorFinding.objects.filter(
            assignment__record__in=records,
            assignment__standard__in=standards,
            assignment__assessor=actor,
        )
        .select_related("assignment__record", "assignment__standard__standard__item")
        .prefetch_related("revisions")
        .order_by("pk")
    )
    revision_form = FindingRevisionForm(request.POST if action == "revise-finding" else None)
    cast(forms.ModelChoiceField, revision_form.fields["finding"]).queryset = own_findings
    performance_form = PerformanceDemonstrationForm(
        request.POST if action == "performance-demo" else None
    )
    performance_result = None
    result = None
    token = ""
    status = 200
    if request.method == "POST":
        if (action == "new-rule" and can_add_rule) or (
            action == "new-production-rule" and can_publish
        ):
            if rule_form.is_valid():
                standard = rule_form.cleaned_data["standard"]
                with transaction.atomic():
                    PerformanceStandardVersion.objects.select_for_update().get(pk=standard.pk)
                    latest = EvaluationRuleVersion.objects.filter(standard=standard).aggregate(
                        number=Max("number")
                    )["number"]
                    EvaluationRuleVersion.objects.create(
                        number=(latest or 0) + 1,
                        created_by=actor,
                        demonstration=action == "new-rule",
                        **rule_form.cleaned_data,
                    )
                return redirect(request.path)
        elif action in {"preview", "record"} and can_simulate:
            if simulation_form.is_valid():
                rule = simulation_form.cleaned_data["rule"]
                if action == "record":
                    try:
                        record_evaluation(
                            baseline, rule, actor, simulation_form.cleaned_data["preview_token"]
                        )
                    except StaleSimulationPreview:
                        simulation_form.add_error(
                            None, "Konfirmasi pratinjau terbaru sebelum mencatat simulasi."
                        )
                        result = preview(baseline, rule)
                        status = 409
                    except ValidationError as error:
                        simulation_form.add_error("rule", error)
                    else:
                        return redirect(request.path)
                else:
                    result = preview(baseline, rule)
                if result is not None:
                    token = preview_token(baseline, rule, actor, result)
        elif action == "performance-demo" and can_simulate:
            if performance_form.is_valid():
                values = performance_form.cleaned_data
                findings = [StandardFinding.BELOW] * values["below"] + [
                    StandardFinding.MEETS
                ] * values["meets"]
                performance_result = evaluate_performance(
                    EvidenceEvaluation.Sufficiency(values["sufficiency"]),
                    enumerate(findings),
                    PerformanceThresholds(values["minimum_below"], values["minimum_meets"]),
                )
        elif action == "assign-finding" and can_assign:
            if assignment_form.is_valid():
                try:
                    assign_finding(baseline, actor=actor, **assignment_form.cleaned_data)
                except ValidationError as error:
                    assignment_form.add_error(None, error)
                else:
                    return redirect(request.path)
        elif action == "submit-finding" and can_submit:
            if finding_form.is_valid():
                try:
                    submit_finding(actor=actor, **finding_form.cleaned_data)
                except ValidationError as error:
                    finding_form.add_error(None, ValidationError(error.messages))
                else:
                    return redirect(request.path)
        elif action == "revise-finding" and can_submit:
            if revision_form.is_valid():
                try:
                    revise_finding(actor=actor, **revision_form.cleaned_data)
                except ValidationError as error:
                    revision_form.add_error(None, ValidationError(error.messages))
                else:
                    return redirect(request.path)
        elif action == "publish" and can_publish:
            if publication_form.is_valid():
                try:
                    publish_rule(actor=actor, **publication_form.cleaned_data)
                except ValidationError as error:
                    publication_form.add_error(None, error)
                else:
                    return redirect(request.path)
        elif (action == "retire" and can_retire) or (action == "retire-production" and can_publish):
            if retirement_form.is_valid():
                try:
                    retire_rule(actor=actor, **retirement_form.cleaned_data)
                except ValidationError as error:
                    retirement_form.add_error(None, error)
                else:
                    return redirect(request.path)
        else:
            raise PermissionDenied
    history = Paginator(
        EvidenceEvaluation.objects.filter(baseline=baseline).select_related("rule", "created_by"),
        25,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "adaptive/evaluations.html",
        {
            "program": program,
            "baseline": baseline,
            "rule_form": rule_form,
            "simulation_form": simulation_form,
            "can_add_rule": can_add_rule,
            "can_view_policy": VIEW_POLICY in roles,
            "can_publish": can_publish,
            "can_assign": can_assign,
            "can_submit": can_submit,
            "assignment_form": assignment_form,
            "finding_form": finding_form,
            "revision_form": revision_form,
            "own_findings": own_findings if can_submit else (),
            "finding_outcomes": AssessorFinding.Outcome.choices,
            "production_rules": production_rules,
            "publication_form": publication_form,
            "can_retire": can_retire,
            "retirement_form": retirement_form,
            "rules": rules,
            "can_simulate": can_simulate,
            "performance_form": performance_form,
            "performance_result": performance_result,
            "result": result,
            "preview_token": token,
            "history": history,
            "can_approve_intervention": "learning.add_interventionapproval" in roles,
            "intervention_evaluations": current_intervention_evaluations(baseline),
        },
        status=status,
    )
