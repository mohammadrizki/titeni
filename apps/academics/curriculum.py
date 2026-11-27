from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.academics.models import Curriculum, CurriculumStage, CurriculumVersion
from apps.accounts.access import (
    configurable_programs,
    has_program_permission,
    require_program_permission,
)
from apps.accounts.models import User


class CurriculumForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = ["code", "name"]


class StageForm(forms.ModelForm):
    class Meta:
        model = CurriculumStage
        fields = ["code", "name"]


@require_http_methods(["GET", "POST"])
@login_required
def curricula(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if request.method == "POST":
        require_program_permission(actor, program_id, "academics.add_curriculum")
    form = CurriculumForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        curriculum = form.save(commit=False)
        curriculum.program = program
        try:
            with transaction.atomic():
                curriculum.save()
                version = curriculum.versions.create(number=1, created_by=actor)
        except IntegrityError:
            if not Curriculum.objects.filter(program=program, code=curriculum.code).exists():
                raise
            form.add_error("code", "Kode kurikulum sudah digunakan di prodi ini.")
        else:
            messages.success(request, "Draf kurikulum dibuat.")
            return redirect(
                "academics:curriculum_version", program_id=program.pk, version_id=version.pk
            )
    return render(
        request,
        "academics/curricula.html",
        {
            "program": program,
            "form": form,
            "can_view_reflection_prompts": has_program_permission(
                actor, program_id, "reflection.view_reflectionprompt"
            ),
            "curricula": Curriculum.objects.filter(program=program).prefetch_related("versions"),
        },
    )


@require_POST
@login_required
def new_curriculum_version(
    request: HttpRequest, program_id: int, curriculum_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    programs = configurable_programs(actor)
    with transaction.atomic():
        curriculum = get_object_or_404(
            Curriculum.objects.select_for_update(),
            program__in=programs,
            program_id=program_id,
            pk=curriculum_id,
        )
        require_program_permission(actor, program_id, "academics.add_curriculumversion")
        latest = curriculum.versions.first()
        version = curriculum.versions.create(
            number=latest.number + 1 if latest else 1, created_by=actor
        )
    messages.success(request, "Draf versi baru dibuat.")
    return redirect("academics:curriculum_version", program_id=program_id, version_id=version.pk)


@require_http_methods(["GET", "POST"])
@login_required
def curriculum_version(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    version = get_object_or_404(
        CurriculumVersion.objects.select_related("curriculum__program"),
        pk=version_id,
        curriculum__program_id=program_id,
        curriculum__program__in=configurable_programs(actor),
    )
    if request.method == "POST":
        require_program_permission(actor, program_id, "academics.add_curriculumstage")
    form = StageForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        stage = form.save(commit=False)
        stage.version = version
        stage.created_by = actor
        try:
            with transaction.atomic():
                stage.save()
        except IntegrityError:
            if not version.stages.filter(code=stage.code).exists():
                raise
            form.add_error("code", "Kode tahap sudah digunakan di versi ini.")
        else:
            messages.success(request, "Tahap kurikulum berhasil disimpan.")
            return redirect(
                "academics:curriculum_version", program_id=program_id, version_id=version.pk
            )
    return render(
        request,
        "academics/curriculum_version.html",
        {
            "program": version.curriculum.program,
            "form": form,
            "version": version,
            "stages": version.stages.all(),
        },
    )
