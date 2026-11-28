from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import configurable_programs
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import PROGRAM_LEAD_ROLE

from .models import (
    EntrustableProfessionalActivity,
    EPAAssessorAssignment,
    EPAObservation,
    EPAPublication,
    SupervisionScaleVersion,
)

PUBLISH = "add_epapublication"
ASSIGN = "add_epaassessorassignment"
RECORD = "add_epaobservation"


def program_grants(role: str, permission: str) -> QuerySet[UserRoleAssignment]:
    return UserRoleAssignment.objects.filter(
        account__is_active=True,
        role__scope=AccessRole.Scope.PROGRAM,
        role__name=role,
        role__permissions__content_type__app_label="epa",
        role__permissions__codename=permission,
    )


def program_lead_can(actor: User, program_id: int, permission: str) -> bool:
    return (
        program_grants(PROGRAM_LEAD_ROLE, permission)
        .filter(account=actor, program_id=program_id)
        .exists()
    )


def active_publication(activity_id: int) -> EPAPublication | None:
    return EPAPublication.objects.filter(version__activity_id=activity_id).first()


class AssessorAssignmentForm(forms.ModelForm):
    class Meta:
        model = EPAAssessorAssignment
        fields = ("enrollment", "assessor")
        labels = {"enrollment": "Pendaftaran mahasiswa", "assessor": "Asesor"}

    def __init__(self, *args, program_id: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(
            forms.ModelChoiceField, self.fields["enrollment"]
        ).queryset = LearnerEnrollment.objects.filter(
            cohort__period__program_id=program_id
        ).select_related("learner__account", "cohort")
        cast(forms.ModelChoiceField, self.fields["assessor"]).queryset = User.objects.filter(
            pk__in=program_grants("Asesor", RECORD)
            .filter(program_id=program_id)
            .values("account_id")
        ).order_by("username")


class ObservationForm(forms.ModelForm):
    class Meta:
        model = EPAObservation
        fields = ("occurred_on", "context", "case_complexity", "level", "feedback")
        widgets = {"occurred_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, scale: SupervisionScaleVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["level"]).queryset = scale.levels.all()

    def clean_occurred_on(self):
        occurred_on = self.cleaned_data["occurred_on"]
        if occurred_on > timezone.localdate():
            raise forms.ValidationError("Tanggal observasi tidak boleh di masa depan.")
        return occurred_on


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def manage(
    request: HttpRequest, program_id: int, activity_id: int, version_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    can_publish = program_lead_can(actor, program_id, PUBLISH)
    can_assign = program_lead_can(actor, program_id, ASSIGN)
    if not (can_publish or can_assign):
        raise PermissionDenied
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    activities = EntrustableProfessionalActivity.objects.filter(program=program)
    activity = get_object_or_404(activities, pk=activity_id)
    versions = activity.versions.filter(
        scale__scale__program=program, framework__framework__program=program
    ).select_related("scale__scale")
    version = get_object_or_404(versions, pk=version_id)
    current = active_publication(activity.pk)
    publication = EPAPublication.objects.filter(version=version).first()
    form = AssessorAssignmentForm(program_id=program_id)
    error = ""
    if request.method == "POST":
        with transaction.atomic():
            get_object_or_404(activities.select_for_update(), pk=activity_id)
            version = get_object_or_404(versions.select_for_update(of=("self",)), pk=version_id)
            current = active_publication(activity.pk)
            publication = EPAPublication.objects.filter(version=version).first()
            match request.POST.get("action"):
                case "publish":
                    if not can_publish:
                        raise PermissionDenied
                    scale = SupervisionScaleVersion.objects.select_for_update().get(
                        pk=version.scale_id
                    )
                    if publication is not None and publication == current:
                        return redirect("academics:epa:manage", program_id, activity_id, version_id)
                    if current is not None and current.version.number >= version.number:
                        error = "Versi yang lebih baru sudah berlaku."
                    elif not scale.levels.exists():
                        error = "Tambahkan tingkat pada versi skala sebelum memberlakukan EPA."
                    else:
                        EPAPublication.objects.create(version=version, created_by=actor)
                        return redirect("academics:epa:manage", program_id, activity_id, version_id)
                case "assign":
                    if not can_assign:
                        raise PermissionDenied
                    if publication is None or publication != current:
                        error = "Gunakan versi EPA yang sedang berlaku."
                    else:
                        assignment = EPAAssessorAssignment(
                            publication=publication, created_by=actor
                        )
                        form = AssessorAssignmentForm(
                            request.POST, instance=assignment, program_id=program_id
                        )
                        if form.is_valid():
                            EPAAssessorAssignment.objects.get_or_create(
                                publication=publication,
                                enrollment=form.cleaned_data["enrollment"],
                                assessor=form.cleaned_data["assessor"],
                                defaults={"created_by": actor},
                            )
                            return redirect(
                                "academics:epa:manage", program_id, activity_id, version_id
                            )
                case _:
                    return HttpResponse(status=400)
    return render(
        request,
        "epa/manage.html",
        {
            "program": program,
            "activity": activity,
            "version": version,
            "publication": publication,
            "current": publication is not None and publication == current,
            "can_publish": can_publish
            and publication is None
            and (current is None or current.version.number < version.number),
            "assignment_form": form
            if can_assign and publication is not None and publication == current
            else None,
            "assignments": EPAAssessorAssignment.objects.filter(publication=publication)
            .select_related("enrollment__learner__account", "enrollment__cohort", "assessor")
            .annotate(observation_count=Count("observations"))
            if publication is not None
            else (),
            "error": error,
        },
        status=400 if request.method == "POST" else 200,
    )


def own_assignments(actor: User) -> QuerySet[EPAAssessorAssignment]:
    programs = program_grants("Asesor", RECORD).filter(account=actor).values("program_id")
    return EPAAssessorAssignment.objects.filter(
        assessor=actor,
        publication__version__activity__program_id__in=programs,
        enrollment__cohort__period__program_id=F("publication__version__activity__program_id"),
    ).select_related(
        "publication__version__activity",
        "publication__version__scale__scale",
        "enrollment__learner__account",
        "enrollment__cohort",
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def observations(request: HttpRequest, assignment_id: int | None = None) -> HttpResponse:
    actor = cast(User, request.user)
    assignments = own_assignments(actor)
    if assignment_id is None:
        if request.method == "POST":
            return HttpResponse(status=405, headers={"Allow": "GET"})
        return render(request, "epa/observations.html", {"assignments": assignments})

    assignment = get_object_or_404(assignments, pk=assignment_id)
    version = assignment.publication.version
    can_record = assignment.publication == active_publication(version.activity_id)
    form = ObservationForm(scale=version.scale)
    if request.method == "POST":
        with transaction.atomic():
            EntrustableProfessionalActivity.objects.select_for_update().get(pk=version.activity_id)
            assignment = get_object_or_404(
                assignments.select_for_update(of=("self",)), pk=assignment_id
            )
            if assignment.publication != active_publication(version.activity_id):
                return HttpResponse("Gunakan penugasan untuk versi EPA yang berlaku.", status=409)
            observation = EPAObservation(assignment=assignment, created_by=actor)
            form = ObservationForm(request.POST, instance=observation, scale=version.scale)
            if form.is_valid():
                form.save()
                return redirect("epa_observation_assignment", assignment.pk)
    return render(
        request,
        "epa/observations.html",
        {
            "assignment": assignment,
            "form": form if can_record else None,
            "observations": assignment.observations.select_related("level"),
        },
        status=400 if request.method == "POST" else 200,
    )
