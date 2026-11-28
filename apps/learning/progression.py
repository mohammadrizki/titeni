from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.adaptive.models import EvidenceEvaluation
from apps.epa.models import EntrustmentDecision

from .academic_advisors import program_lead_has_permission, role_grants
from .models import ProgressionReview, ProgressionReviewAssignment, ProgressionReviewEvidence

ASSIGN = "add_progressionreviewassignment"
WRITE = "add_progressionreview"
REVIEWER_ROLE = "Peninjau Progresi"


def own_progression_reviews(actor: User) -> QuerySet[ProgressionReviewAssignment]:
    programs = role_grants(REVIEWER_ROLE, WRITE).filter(account=actor).values("program_id")
    return ProgressionReviewAssignment.objects.filter(
        reviewer=actor, enrollment__cohort__period__program_id__in=programs
    ).select_related("enrollment__learner__account", "enrollment__cohort__period__program")


def production_history(enrollment_id: int, program_id: int) -> QuerySet[EvidenceEvaluation]:
    return EvidenceEvaluation.objects.filter(
        baseline__enrollment_id=enrollment_id,
        baseline__enrollment__cohort__period__program_id=program_id,
        baseline__publication__artifact_map__program_id=program_id,
        rule__demonstration=False,
        rule__publication__isnull=False,
        rule__standard__standard__item__version_id=F(
            "baseline__publication__version__blueprint_version__framework_version_id"
        ),
    ).select_related("rule__standard__standard__item")


def decisions_for(enrollment_id: int, program_id: int) -> QuerySet[EntrustmentDecision]:
    return EntrustmentDecision.objects.filter(
        ballot__enrollment_id=enrollment_id,
        ballot__publication__version__activity__program_id=program_id,
    ).select_related(
        "ballot__publication__version__activity",
        "ballot__draft__level",
        "ballot__proposed_level",
        "replacement",
    )


class ReviewerForm(forms.Form):
    reviewer = forms.ModelChoiceField(label="Peninjau Progresi", queryset=User.objects.none())


class EvaluationChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj: EvidenceEvaluation) -> str:
        return (
            f"#{obj.pk} · {obj.rule.standard.standard.item} · "
            f"{obj.created_at:%d-%m-%Y} · {obj.get_sufficiency_display()}"
        )


class DecisionChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj: EntrustmentDecision) -> str:
        status = " · Digantikan" if hasattr(obj, "replacement") else ""
        return f"#{obj.pk} · {obj.ballot.publication.version} · {obj.ballot.level}{status}"


class DraftForm(forms.ModelForm):
    previous = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    evaluations = EvaluationChoices(
        label="Evaluasi pendukung",
        queryset=EvidenceEvaluation.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    decisions = DecisionChoices(
        label="Keputusan EPA pendukung",
        queryset=EntrustmentDecision.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = ProgressionReview
        fields = ("recommendation", "rationale")

    def clean(self) -> dict:
        data = super().clean() or {}
        if not self.errors and not (data.get("evaluations") or data.get("decisions")):
            raise forms.ValidationError("Pilih setidaknya satu evaluasi atau keputusan pendukung.")
        return data


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def assign(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    if not program_lead_has_permission(actor, program_id, ASSIGN):
        raise PermissionDenied
    enrollment = get_object_or_404(
        LearnerEnrollment.objects.select_related("learner__account", "cohort__period__program"),
        pk=enrollment_id,
        cohort__period__program_id=program_id,
        cohort__period__program__in=configurable_programs(actor),
    )
    writing = request.method == "POST"
    form = ReviewerForm(request.POST if writing else None)
    cast(forms.ModelChoiceField, form.fields["reviewer"]).queryset = (
        User.objects.filter(
            pk__in=role_grants(REVIEWER_ROLE, WRITE)
            .filter(program_id=program_id)
            .values("account_id")
        )
        .exclude(pk=enrollment.learner.account_id)
        .order_by("username")
    )
    if writing and form.is_valid():
        ProgressionReviewAssignment.objects.get_or_create(
            enrollment=enrollment,
            reviewer=form.cleaned_data["reviewer"],
            defaults={"assigned_by": actor},
        )
        return redirect("academics:assign_progression_review", program_id, enrollment_id)
    return render(
        request,
        "learning/progression_assign.html",
        {
            "enrollment": enrollment,
            "form": form,
            "assignments": ProgressionReviewAssignment.objects.filter(enrollment=enrollment)
            .select_related("reviewer")
            .annotate(draft_count=Count("drafts")),
        },
        status=400 if writing else 200,
    )


@never_cache
@login_required
@require_safe
def queue(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "learning/progression_queue.html",
        {"assignments": own_progression_reviews(cast(User, request.user))},
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def draft(request: HttpRequest, assignment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    assignments = own_progression_reviews(actor)
    assignment = get_object_or_404(assignments, pk=assignment_id)
    enrollment_id = assignment.enrollment_id
    program_id = assignment.enrollment.cohort.period.program_id
    evaluations = production_history(enrollment_id, program_id)
    decisions = decisions_for(enrollment_id, program_id)
    latest = assignment.drafts.first()
    initial: dict[str, object] = {"previous": latest.number if latest else 0}
    if latest:
        initial.update(
            recommendation=latest.recommendation,
            rationale=latest.rationale,
            evaluations=list(
                latest.evidence.exclude(evaluation=None).values_list("evaluation_id", flat=True)
            ),
            decisions=list(
                latest.evidence.exclude(decision=None).values_list("decision_id", flat=True)
            ),
        )
    writing = request.method == "POST"
    form = DraftForm(request.POST if writing else None, initial=initial)
    cast(forms.ModelMultipleChoiceField, form.fields["evaluations"]).queryset = evaluations
    cast(forms.ModelMultipleChoiceField, form.fields["decisions"]).queryset = decisions
    status = 200
    if writing:
        with transaction.atomic():
            assignment = get_object_or_404(
                assignments.select_for_update(of=("self",)), pk=assignment_id
            )
            latest = assignment.drafts.first()
            number = latest.number if latest else 0
            status = 400
            if form.is_valid():
                if form.cleaned_data["previous"] != number:
                    form.add_error(
                        None, "Draf sudah berubah. Muat ulang halaman untuk melanjutkan."
                    )
                    status = 409
                else:
                    review = form.save(commit=False)
                    review.assignment, review.number, review.created_by = (
                        assignment,
                        number + 1,
                        actor,
                    )
                    review.save()
                    ProgressionReviewEvidence.objects.bulk_create(
                        [
                            ProgressionReviewEvidence(review=review, evaluation=item)
                            for item in form.cleaned_data["evaluations"]
                        ]
                        + [
                            ProgressionReviewEvidence(review=review, decision=item)
                            for item in form.cleaned_data["decisions"]
                        ]
                    )
                    return redirect("progression_review_draft", assignment_id)
    return render(
        request,
        "learning/progression_draft.html",
        {
            "assignment": assignment,
            "evaluations": evaluations,
            "decisions": decisions,
            "form": form,
            "drafts": assignment.drafts.prefetch_related("evidence"),
        },
        status=status,
    )
