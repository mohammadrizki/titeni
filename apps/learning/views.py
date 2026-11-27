from datetime import date
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import program_role_permissions as actor_program_permissions
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.competencies.models import CompetencyItem
from apps.evidence.models import LearnerEvidenceBaseline
from apps.reflection.models import CoachingRecommendation, ReflectionRevision

from .models import InterventionApproval, LearningGoal, LearningPlan


class RecommendationChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: CoachingRecommendation) -> str:
        return obj.body if len(obj.body) <= 100 else f"{obj.body[:97]}…"


class GoalForm(forms.ModelForm):
    revision = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    coaching_source = RecommendationChoiceField(
        label="Rekomendasi coaching asal",
        queryset=CoachingRecommendation.objects.none(),
        required=False,
    )

    class Meta:
        model = LearningGoal
        fields = (
            "competency",
            "reflection_source",
            "coaching_source",
            "rationale",
            "activity",
            "expected_outcome",
            "improvement_evidence",
            "completion_criteria",
            "due_on",
            "review_on",
        )
        labels = {"competency": "Kompetensi"}
        widgets = {
            "due_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "review_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def plan(
    request: HttpRequest, enrollment_id: int | None = None, goal_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_learninggoal",
    ).values("program_id")
    enrollments = LearnerEnrollment.objects.filter(
        learner__account=actor,
        learner__account__is_active=True,
        cohort__period__program_id__in=programs,
    ).select_related("cohort__period__program")
    if enrollment_id is None:
        if request.method == "POST":
            return HttpResponse(status=405)
        return render(request, "learning/index.html", {"enrollments": enrollments})

    enrollment = get_object_or_404(enrollments, pk=enrollment_id)
    program = enrollment.cohort.period.program
    framework_versions = LearnerEvidenceBaseline.objects.filter(
        enrollment=enrollment,
        publication__artifact_map__program=program,
        publication__version__blueprint_version__blueprint__program=program,
    ).values("publication__version__blueprint_version__framework_version_id")
    competencies = CompetencyItem.objects.filter(
        version_id__in=framework_versions, version__framework__program=program
    )
    reflections = ReflectionRevision.objects.filter(reflection__enrollment=enrollment)
    recommendations = CoachingRecommendation.objects.filter(
        share__revision__reflection__enrollment=enrollment,
        share__assignment__enrollment=enrollment,
        author_id=F("share__assignment__advisor_id"),
    )
    initial = {}
    for field, choices in (
        ("reflection_source", reflections),
        ("coaching_source", recommendations),
    ):
        value = request.GET.get(field, "")
        if value.isascii() and value.isdecimal() and len(value) <= 18:
            initial[field] = choices.filter(pk=int(value)).values_list("pk", flat=True).first()
    goals = LearningGoal.objects.filter(plan__enrollment=enrollment).select_related(
        "competency", "reflection_source", "coaching_source"
    )
    writing = request.method == "POST"
    status = 200
    with transaction.atomic():
        editing = None
        snapshot = {}
        if goal_id is not None:
            scoped = goals.select_for_update(of=("self",)) if writing else goals
            editing = get_object_or_404(scoped, pk=goal_id)
            if "learning.change_learninggoal" not in actor_program_permissions(actor, program.pk):
                raise PermissionDenied
            initial = {"revision": editing.revision_number}
            for field in GoalForm.Meta.fields:
                value = getattr(editing, field)
                snapshot[field] = value.isoformat() if isinstance(value, date) else str(value or "")
        form = GoalForm(request.POST if writing else None, initial=initial, instance=editing)
        cast(forms.ModelChoiceField, form.fields["reflection_source"]).queryset = reflections
        cast(forms.ModelChoiceField, form.fields["coaching_source"]).queryset = recommendations
        cast(forms.ModelChoiceField, form.fields["competency"]).queryset = competencies
        if writing and form.is_valid():
            if editing and form.cleaned_data["revision"] != editing.revision_number:
                form.add_error(None, "Tujuan sudah berubah. Buka kembali versi terbaru.")
                status = 409
            else:
                goal = form.save(commit=False)
                if editing is None:
                    goal.plan, _ = LearningPlan.objects.get_or_create(enrollment=enrollment)
                    goal.save()
                elif set(form.changed_data).intersection(GoalForm.Meta.fields):
                    goal.revisions.create(number=goal.revision_number, snapshot=snapshot)
                    goal.revision_number += 1
                    goal.save()
                return (
                    redirect("learning_goal", enrollment.pk, goal.pk)
                    if editing
                    else redirect("learning_plan", enrollment.pk)
                )
    permissions = actor_program_permissions(actor, program.pk)
    return render(
        request,
        "learning/plan.html",
        {
            "enrollment": enrollment,
            "goals": goals,
            "approved_interventions": InterventionApproval.objects.filter(
                draft__assignment__enrollment=enrollment,
                draft__evaluation__baseline__enrollment=enrollment,
            )
            .select_related(
                "draft__evaluation__rule__standard__standard__item",
                "approved_by",
                "interventioncompletionreport__reassessment",
            )
            .order_by("-approved_at"),
            "editing": editing,
            "can_edit": "learning.change_learninggoal" in permissions,
            "can_report_completion": "learning.add_interventioncompletionreport" in permissions,
            "form": form,
            "has_competencies": competencies.exists(),
        },
        status=status,
    )
