from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import (
    configurable_programs,
    program_role_permissions,
    require_program_permission,
)
from apps.accounts.models import AccessRole, User, UserRoleAssignment

from .models import (
    CoachingRecommendation,
    ReflectionAdvisorAssignment,
    ReflectionRevision,
    ReflectionShare,
)
from .views import own_enrollments


def posted_pk(request: HttpRequest, field: str) -> int:
    value = request.POST.get(field, "")
    if not value.isascii() or not value.isdecimal() or len(value) > 18:
        raise Http404
    return int(value)


def recipient_roles():
    return UserRoleAssignment.objects.filter(
        role__scope=AccessRole.Scope.PROGRAM,
        account__is_active=True,
        role__permissions__content_type__app_label="reflection",
        role__permissions__codename="view_reflectionshare",
    )


class AdvisorForm(forms.Form):
    advisor = forms.ModelChoiceField(label="Pembimbing", queryset=User.objects.none())


class ShareForm(forms.Form):
    assignment = forms.ModelChoiceField(
        label="Penerima versi ini", queryset=ReflectionAdvisorAssignment.objects.none()
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def advisors(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    require_program_permission(actor, program_id, "reflection.add_reflectionadvisorassignment")
    enrollment = get_object_or_404(
        LearnerEnrollment,
        pk=enrollment_id,
        cohort__period__program_id=program_id,
        cohort__period__program__in=configurable_programs(actor),
    )
    assignments = ReflectionAdvisorAssignment.objects.filter(enrollment=enrollment)
    action = request.POST.get("action")
    form = AdvisorForm(request.POST if action == "assign" else None)
    cast(forms.ModelChoiceField, form.fields["advisor"]).queryset = (
        User.objects.filter(
            pk__in=recipient_roles().filter(program_id=program_id).values("account_id")
        )
        .exclude(pk=enrollment.learner.account_id)
        .order_by("username")
    )
    if request.method == "POST":
        with transaction.atomic():
            LearnerEnrollment.objects.select_for_update().get(pk=enrollment.pk)
            if action == "revoke":
                assignment = get_object_or_404(assignments, pk=posted_pk(request, "assignment"))
                assignments.filter(pk=assignment.pk, revoked_at__isnull=True).update(
                    revoked_at=timezone.now(), revoked_by=actor
                )
            elif action == "assign":
                if not form.is_valid():
                    return render(
                        request,
                        "reflection/advisors.html",
                        {
                            "enrollment": enrollment,
                            "assignments": assignments,
                            "form": form,
                        },
                        status=400,
                    )
                assignments.get_or_create(
                    enrollment=enrollment,
                    advisor=form.cleaned_data["advisor"],
                    revoked_at=None,
                    defaults={"assigned_by": actor},
                )
            else:
                raise Http404
        return redirect("academics:reflection_advisors", program_id, enrollment_id)
    return render(
        request,
        "reflection/advisors.html",
        {
            "enrollment": enrollment,
            "assignments": assignments.select_related("advisor"),
            "form": form,
        },
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def share_revision(request: HttpRequest, enrollment_id: int, revision_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    enrollment = get_object_or_404(own_enrollments(actor), pk=enrollment_id)
    revision = get_object_or_404(
        ReflectionRevision, pk=revision_id, reflection__enrollment=enrollment
    )
    shares = ReflectionShare.objects.filter(revision=revision)
    action = request.POST.get("action")
    form = ShareForm(request.POST if action == "share" else None)
    cast(
        forms.ModelChoiceField, form.fields["assignment"]
    ).queryset = ReflectionAdvisorAssignment.objects.filter(
        enrollment=enrollment,
        revoked_at__isnull=True,
        advisor_id__in=recipient_roles()
        .filter(program_id=enrollment.cohort.period.program_id)
        .values("account_id"),
    ).select_related("advisor")
    if request.method == "POST":
        with transaction.atomic():
            LearnerEnrollment.objects.select_for_update().get(pk=enrollment.pk)
            if action == "revoke":
                share = get_object_or_404(shares, pk=posted_pk(request, "share"))
                shares.filter(pk=share.pk, revoked_at__isnull=True).update(
                    revoked_at=timezone.now()
                )
            elif action == "share":
                if not form.is_valid():
                    return render(
                        request,
                        "reflection/share.html",
                        {
                            "revision": revision,
                            "shares": shares,
                            "form": form,
                        },
                        status=400,
                    )
                shares.get_or_create(
                    revision=revision,
                    assignment=form.cleaned_data["assignment"],
                    revoked_at=None,
                )
            else:
                raise Http404
        return redirect("reflection_share", enrollment_id, revision_id)
    return render(
        request,
        "reflection/share.html",
        {
            "revision": revision,
            "shares": shares.select_related("assignment__advisor"),
            "form": form,
        },
    )


def recipient_shares(actor: User) -> QuerySet[ReflectionShare]:
    programs = recipient_roles().filter(account=actor).values("program_id")
    return ReflectionShare.objects.filter(
        assignment__advisor=actor,
        assignment__revoked_at__isnull=True,
        revoked_at__isnull=True,
        assignment__enrollment__cohort__period__program_id__in=programs,
        revision__reflection__enrollment_id=F("assignment__enrollment_id"),
    ).select_related("revision__reflection", "assignment__enrollment__learner")


@never_cache
@login_required
@require_http_methods(["GET"])
def shared_reflections(request: HttpRequest, share_id: int | None = None) -> HttpResponse:
    actor = cast(User, request.user)
    shares = recipient_shares(actor)
    if share_id is not None:
        share = get_object_or_404(shares, pk=share_id)
        return render(request, "reflection/shared_detail.html", {"share": share})
    return render(request, "reflection/shared_list.html", {"shares": shares})


class CoachingForm(forms.Form):
    body = forms.CharField(label="Pesan coaching", max_length=4000, widget=forms.Textarea)


class RecommendationForm(forms.Form):
    body = forms.CharField(label="Rekomendasi", max_length=4000, widget=forms.Textarea)
    due_on = forms.DateField(
        label="Tenggat (opsional)", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )


class FollowUpForm(forms.Form):
    note = forms.CharField(label="Catatan tindak lanjut", max_length=4000)


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def coaching(request: HttpRequest, share_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    accessible = ReflectionShare.objects.filter(
        Q(revision__reflection__enrollment__in=own_enrollments(actor))
        | Q(pk__in=recipient_shares(actor).values("pk")),
        revision__reflection__enrollment_id=F("assignment__enrollment_id"),
    ).select_related("revision", "assignment__enrollment__cohort__period", "assignment__advisor")
    share = get_object_or_404(accessible, pk=share_id)
    action = request.POST.get("action", "message") if request.method == "POST" else None
    form = CoachingForm(request.POST if action == "message" else None)
    recommendation_form = RecommendationForm(request.POST if action == "recommend" else None)
    follow_up_form = FollowUpForm(request.POST if action == "complete" else None)
    with transaction.atomic():
        if request.method == "POST":
            LearnerEnrollment.objects.select_for_update().get(pk=share.assignment.enrollment_id)
            share = get_object_or_404(accessible, pk=share_id)
        active = recipient_shares(share.assignment.advisor).filter(pk=share.pk).exists()
        program_id = share.assignment.enrollment.cohort.period.program_id
        permissions = program_role_permissions(actor, program_id)
        can_post = active and "reflection.add_reflectioncoachingmessage" in permissions
        can_recommend = (
            active
            and share.assignment.advisor_id == actor.pk
            and "reflection.add_coachingrecommendation" in permissions
        )
        is_owner = share.assignment.enrollment.learner.account_id == actor.pk
        can_complete = (
            active and is_owner and "reflection.complete_coachingrecommendation" in permissions
        )
        if action == "message" and can_post:
            if form.is_valid():
                share.messages.create(author=actor, body=form.cleaned_data["body"])
                return redirect("reflection_coaching", share.pk)
        elif action == "recommend" and can_recommend:
            if recommendation_form.is_valid():
                share.recommendations.create(author=actor, **recommendation_form.cleaned_data)
                return redirect("reflection_coaching", share.pk)
        elif action == "complete" and can_complete:
            recommendation = get_object_or_404(
                CoachingRecommendation, pk=posted_pk(request, "recommendation"), share=share
            )
            if follow_up_form.is_valid():
                share.recommendations.filter(
                    pk=recommendation.pk, completed_at__isnull=True
                ).update(
                    completed_at=timezone.now(), completion_note=follow_up_form.cleaned_data["note"]
                )
                return redirect("reflection_coaching", share.pk)
        elif action is not None:
            raise Http404
    return render(
        request,
        "reflection/coaching.html",
        {
            "share": share,
            "messages_in_thread": share.messages.select_related("author"),
            "form": form,
            "can_post": can_post,
            "recommendations": share.recommendations.select_related("author"),
            "recommendation_form": recommendation_form,
            "follow_up_form": follow_up_form,
            "can_recommend": can_recommend,
            "can_complete": can_complete,
            "is_owner": is_owner,
        },
    )
