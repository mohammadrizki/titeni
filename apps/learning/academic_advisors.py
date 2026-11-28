from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import configurable_programs
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import PROGRAM_LEAD_ROLE, SYNTHESIS_REVIEWER_ROLE
from apps.reflection.sharing import posted_pk

from .models import AcademicAdvisorAssignment, LongitudinalSynthesis

ASSIGN_PERMISSION = "add_academicadvisorassignment"
READ_PERMISSION = "view_longitudinalsynthesis"
WRITE_PERMISSION = "add_longitudinalsynthesis"


def role_grants(role: str, permission: str) -> QuerySet[UserRoleAssignment]:
    return UserRoleAssignment.objects.filter(
        account__is_active=True,
        role__name=role,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="learning",
        role__permissions__codename=permission,
    )


def program_lead_has_permission(actor: User, program_id: int, permission: str) -> bool:
    return (
        role_grants(PROGRAM_LEAD_ROLE, permission)
        .filter(account=actor, program_id=program_id)
        .exists()
    )


def advisor_assignments(
    actor: User, permission: str = READ_PERMISSION
) -> QuerySet[AcademicAdvisorAssignment]:
    programs = (
        role_grants(SYNTHESIS_REVIEWER_ROLE, permission).filter(account=actor).values("program_id")
    )
    return AcademicAdvisorAssignment.objects.filter(
        advisor=actor,
        revoked_at__isnull=True,
        enrollment__cohort__period__program_id__in=programs,
    )


class AdvisorForm(forms.Form):
    advisor = forms.ModelChoiceField(label="Peninjau Sintesis", queryset=User.objects.none())


class SynthesisForm(forms.ModelForm):
    class Meta:
        model = LongitudinalSynthesis
        fields = ("body",)


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def manage_advisors(request: HttpRequest, program_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    if not program_lead_has_permission(actor, program_id, ASSIGN_PERMISSION):
        raise PermissionDenied
    enrollment = get_object_or_404(
        LearnerEnrollment,
        pk=enrollment_id,
        cohort__period__program_id=program_id,
        cohort__period__program__in=configurable_programs(actor),
    )
    assignments = AcademicAdvisorAssignment.objects.filter(enrollment=enrollment)
    action = request.POST.get("action")
    form = AdvisorForm(request.POST if action == "assign" else None)
    cast(forms.ModelChoiceField, form.fields["advisor"]).queryset = (
        User.objects.filter(
            pk__in=role_grants(SYNTHESIS_REVIEWER_ROLE, WRITE_PERMISSION)
            .filter(program_id=program_id)
            .values("account_id")
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
                        "learning/academic_advisors.html",
                        {"enrollment": enrollment, "assignments": assignments, "form": form},
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
        return redirect("academics:academic_advisors", program_id, enrollment_id)
    return render(
        request,
        "learning/academic_advisors.html",
        {
            "enrollment": enrollment,
            "assignments": assignments.select_related("advisor"),
            "form": form,
        },
    )


@never_cache
@login_required
@require_GET
def review_queue(request: HttpRequest) -> HttpResponse:
    assignments = advisor_assignments(cast(User, request.user)).select_related(
        "enrollment__learner",
        "enrollment__cohort__period__program",
        "enrollment__evidence_baseline",
    )
    return render(request, "learning/academic_review_queue.html", {"assignments": assignments})
