from datetime import date
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import program_role_permissions
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.reflection.models import ReflectionAdvisorAssignment
from apps.reflection.sharing import posted_pk, recipient_roles

from .models import LearningGoal, LearningGoalShare

PUBLIC_FIELDS = (
    "competency",
    "rationale",
    "activity",
    "expected_outcome",
    "improvement_evidence",
    "completion_criteria",
    "due_on",
    "review_on",
)


class ShareForm(forms.Form):
    number = forms.ChoiceField(label="Versi tujuan")
    assignment = forms.ModelChoiceField(
        label="Pembimbing", queryset=ReflectionAdvisorAssignment.objects.none()
    )


class ReviewForm(forms.Form):
    note = forms.CharField(label="Catatan pembimbing", max_length=4000, widget=forms.Textarea)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def goal_shares(request: HttpRequest, enrollment_id: int, goal_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    goal = get_object_or_404(
        LearningGoal.objects.select_related("plan__enrollment__cohort__period"),
        pk=goal_id,
        plan__enrollment_id=enrollment_id,
        plan__enrollment__learner__account=actor,
    )
    program_id = goal.plan.enrollment.cohort.period.program_id
    if not actor.is_active or "learning.add_learninggoalshare" not in program_role_permissions(
        actor, program_id
    ):
        raise Http404
    action = request.POST.get("action") if request.method == "POST" else None
    shares = LearningGoalShare.objects.filter(goal=goal).select_related("assignment__advisor")
    with transaction.atomic():
        if action is not None:
            LearnerEnrollment.objects.select_for_update().get(pk=enrollment_id)
            goal = LearningGoal.objects.select_for_update().get(pk=goal.pk)
        form = ShareForm(request.POST if action == "share" else None)
        versions = {str(version.number): version.snapshot for version in goal.revisions.all()}
        versions[str(goal.revision_number)] = {
            field: value.isoformat() if isinstance(value, date) else str(value)
            for field in PUBLIC_FIELDS
            for value in (getattr(goal, field),)
        }
        cast(forms.ChoiceField, form.fields["number"]).choices = [
            (number, f"Versi {number}") for number in reversed(versions)
        ]
        cast(
            forms.ModelChoiceField, form.fields["assignment"]
        ).queryset = ReflectionAdvisorAssignment.objects.filter(
            enrollment_id=enrollment_id,
            revoked_at__isnull=True,
            advisor_id__in=recipient_roles().filter(program_id=program_id).values("account_id"),
        ).select_related("advisor")
        if action == "revoke":
            share = get_object_or_404(shares, pk=posted_pk(request, "share"))
            shares.filter(pk=share.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
            return redirect("learning_goal_shares", enrollment_id, goal.pk)
        if action == "share" and form.is_valid():
            number = form.cleaned_data["number"]
            LearningGoalShare.objects.get_or_create(
                goal=goal,
                assignment=form.cleaned_data["assignment"],
                number=int(number),
                revoked_at=None,
                defaults={"snapshot": {field: versions[number][field] for field in PUBLIC_FIELDS}},
            )
            return redirect("learning_goal_shares", enrollment_id, goal.pk)
    return render(request, "learning/shares.html", {"goal": goal, "shares": shares, "form": form})


def accessible_shares(actor: User):
    return LearningGoalShare.objects.filter(
        Q(goal__plan__enrollment__learner__account=actor)
        | Q(
            assignment__advisor=actor, assignment__revoked_at__isnull=True, revoked_at__isnull=True
        ),
        goal__plan__enrollment_id=F("assignment__enrollment_id"),
    ).select_related("goal__plan__enrollment__cohort__period", "assignment__advisor")


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def review_goal(request: HttpRequest, share_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    share = get_object_or_404(accessible_shares(actor), pk=share_id)
    writing = request.method == "POST"
    form = ReviewForm(request.POST if writing else None)
    with transaction.atomic():
        if writing:
            LearnerEnrollment.objects.select_for_update().get(pk=share.assignment.enrollment_id)
            share = get_object_or_404(accessible_shares(actor), pk=share_id)
        enrollment = share.goal.plan.enrollment
        permissions = program_role_permissions(actor, enrollment.cohort.period.program_id)
        owner = enrollment.learner.account_id == actor.pk
        if not actor.is_active or (
            owner
            and "learning.add_learninggoalshare" not in permissions
            or not owner
            and "learning.add_learninggoalreview" not in permissions
        ):
            raise Http404
        can_review = not owner
        if writing and not can_review:
            raise Http404
        if writing and form.is_valid():
            share.reviews.create(author=actor, note=form.cleaned_data["note"])
            return redirect("learning_goal_review", share.pk)
    return render(
        request,
        "learning/review.html",
        {
            "share": share,
            "form": form,
            "can_review": can_review,
            "reviews": share.reviews.select_related("author"),
        },
    )


def advisor_goal_shares(actor: User):
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        account__is_active=True,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename="add_learninggoalreview",
    ).values("program_id")
    return (
        accessible_shares(actor)
        .filter(
            assignment__advisor=actor,
            revoked_at__isnull=True,
            assignment__revoked_at__isnull=True,
            goal__plan__enrollment__cohort__period__program_id__in=programs,
        )
        .order_by("-shared_at")
    )


@never_cache
@login_required
@require_http_methods(["GET"])
def review_queue(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    return render(request, "learning/review_queue.html", {"shares": advisor_goal_shares(actor)})
