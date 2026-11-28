from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import (
    configurable_programs,
    has_program_permission,
    require_program_permission,
)
from apps.accounts.models import User

from .forms import (
    ActivityForm,
    ActivityVersionForm,
    CompetencyForm,
    LevelForm,
    ScaleForm,
    ScaleVersionForm,
)
from .models import (
    EntrustableProfessionalActivity,
    EPACompetencyLink,
    EPAPublication,
    EPAVersion,
    SupervisionLevel,
    SupervisionScale,
    SupervisionScaleVersion,
)
from .observations import ASSIGN, PUBLISH, program_lead_can
from .reviews import ASSIGN_REVIEW


@require_http_methods(["GET", "POST"])
@login_required
def index(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    require_program_permission(actor, program_id, "epa.view_entrustableprofessionalactivity")
    require_program_permission(actor, program_id, "epa.view_supervisionscale")
    activity = EntrustableProfessionalActivity(program=program, created_by=actor)
    scale = SupervisionScale(program=program, created_by=actor)
    activity_form = ActivityForm(instance=activity, prefix="activity")
    scale_form = ScaleForm(instance=scale, prefix="scale")
    if request.method == "POST":
        with transaction.atomic():
            get_object_or_404(configurable_programs(actor).select_for_update(), pk=program_id)
            match request.POST.get("action"):
                case "activity":
                    require_program_permission(
                        actor, program_id, "epa.add_entrustableprofessionalactivity"
                    )
                    activity_form = ActivityForm(request.POST, instance=activity, prefix="activity")
                    if activity_form.is_valid():
                        activity = activity_form.save()
                        return redirect("academics:epa:activity", program_id, activity.pk)
                case "scale":
                    require_program_permission(actor, program_id, "epa.add_supervisionscale")
                    scale_form = ScaleForm(request.POST, instance=scale, prefix="scale")
                    if scale_form.is_valid():
                        scale = scale_form.save()
                        return redirect("academics:epa:scale", program_id, scale.pk)
                case _:
                    return HttpResponse(status=400)
    return render(
        request,
        "epa/index.html",
        {
            "program": program,
            "activities": EntrustableProfessionalActivity.objects.filter(program=program),
            "scales": SupervisionScale.objects.filter(program=program),
            "activity_form": activity_form
            if has_program_permission(actor, program_id, "epa.add_entrustableprofessionalactivity")
            else None,
            "scale_form": scale_form
            if has_program_permission(actor, program_id, "epa.add_supervisionscale")
            else None,
        },
        status=400 if request.method == "POST" else 200,
    )


@require_http_methods(["GET", "POST"])
@login_required
def activity_detail(
    request: HttpRequest, program_id: int, activity_id: int, version_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    require_program_permission(actor, program_id, "epa.view_entrustableprofessionalactivity")
    require_program_permission(actor, program_id, "epa.view_epaversion")
    activities = EntrustableProfessionalActivity.objects.filter(program=program)
    activity = get_object_or_404(activities, pk=activity_id)
    versions = activity.versions.select_related(
        "framework__framework__program", "scale__scale", "publication"
    )
    version = get_object_or_404(versions, pk=version_id) if version_id is not None else None
    published = version is not None and EPAPublication.objects.filter(version=version).exists()
    form: forms.ModelForm
    if version is None:
        permission = "epa.add_epaversion"
        draft = EPAVersion(activity=activity, created_by=actor)
        form = ActivityVersionForm(instance=draft, program=program)
        if request.method == "POST":
            require_program_permission(actor, program_id, permission)
            with transaction.atomic():
                get_object_or_404(activities.select_for_update(), pk=activity_id)
                latest = versions.first()
                draft.number = latest.number + 1 if latest else 1
                form = ActivityVersionForm(request.POST, instance=draft, program=program)
                if form.is_valid():
                    saved = form.save()
                    return redirect(
                        "academics:epa:activity_version", program_id, activity_id, saved.pk
                    )
    else:
        require_program_permission(actor, program_id, "epa.view_epacompetencylink")
        permission = "epa.add_epacompetencylink"
        link = EPACompetencyLink(version=version, created_by=actor)
        form = CompetencyForm(instance=link)
        if request.method == "POST":
            require_program_permission(actor, program_id, permission)
            with transaction.atomic():
                get_object_or_404(versions.select_for_update(of=("self",)), pk=version_id)
                if EPAPublication.objects.filter(version=version).exists():
                    return HttpResponse("Versi EPA yang sudah berlaku terkunci.", status=409)
                form = CompetencyForm(request.POST, instance=link)
                if form.is_valid():
                    form.save()
                    return redirect(
                        "academics:epa:activity_version", program_id, activity_id, version_id
                    )
    return render(
        request,
        "epa/activity.html",
        {
            "program": program,
            "activity": activity,
            "versions": versions,
            "version": version,
            "competencies": version.competencies.select_related("item").order_by("item__code")
            if version is not None
            else (),
            "published": published,
            "can_assign_review": published and program_lead_can(actor, program_id, ASSIGN_REVIEW),
            "can_manage": version is not None
            and (
                program_lead_can(actor, program_id, PUBLISH)
                or program_lead_can(actor, program_id, ASSIGN)
            ),
            "form": form
            if not published and has_program_permission(actor, program_id, permission)
            else None,
        },
        status=400 if request.method == "POST" else 200,
    )


@require_http_methods(["GET", "POST"])
@login_required
def scale_detail(
    request: HttpRequest, program_id: int, scale_id: int, version_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    require_program_permission(actor, program_id, "epa.view_supervisionscale")
    require_program_permission(actor, program_id, "epa.view_supervisionscaleversion")
    scales = SupervisionScale.objects.filter(program=program)
    scale = get_object_or_404(scales, pk=scale_id)
    versions = scale.versions.all()
    version = get_object_or_404(versions, pk=version_id) if version_id is not None else None
    published = (
        version is not None and EPAPublication.objects.filter(version__scale=version).exists()
    )
    form: forms.ModelForm
    if version is None:
        permission = "epa.add_supervisionscaleversion"
        draft = SupervisionScaleVersion(scale=scale, created_by=actor)
        form = ScaleVersionForm(instance=draft)
        if request.method == "POST":
            require_program_permission(actor, program_id, permission)
            with transaction.atomic():
                get_object_or_404(scales.select_for_update(), pk=scale_id)
                latest = versions.first()
                draft.number = latest.number + 1 if latest else 1
                form = ScaleVersionForm(request.POST, instance=draft)
                if form.is_valid():
                    saved = form.save()
                    return redirect("academics:epa:scale_version", program_id, scale_id, saved.pk)
    else:
        require_program_permission(actor, program_id, "epa.view_supervisionlevel")
        permission = "epa.add_supervisionlevel"
        level = SupervisionLevel(version=version, created_by=actor)
        form = LevelForm(instance=level)
        if request.method == "POST":
            require_program_permission(actor, program_id, permission)
            with transaction.atomic():
                get_object_or_404(versions.select_for_update(), pk=version_id)
                if EPAPublication.objects.filter(version__scale=version).exists():
                    return HttpResponse("Versi skala yang sudah digunakan terkunci.", status=409)
                form = LevelForm(request.POST, instance=level)
                if form.is_valid():
                    form.save()
                    return redirect("academics:epa:scale_version", program_id, scale_id, version_id)
    return render(
        request,
        "epa/scale.html",
        {
            "program": program,
            "scale": scale,
            "versions": versions,
            "version": version,
            "published": published,
            "form": form
            if not published and has_program_permission(actor, program_id, permission)
            else None,
        },
        status=400 if request.method == "POST" else 200,
    )
