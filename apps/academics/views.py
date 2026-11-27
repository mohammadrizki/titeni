from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.academics.forms import AcademicPeriodForm, InstitutionForm, StudyProgramForm
from apps.academics.models import AcademicPeriod, Institution, StudyProgram
from apps.accounts.access import configurable_programs, require_program_permission
from apps.accounts.models import User


@require_http_methods(["GET", "POST"])
@login_required
@permission_required(
    ("accounts.access_system_workspace", "academics.change_institution"), raise_exception=True
)
def faculty(request: HttpRequest) -> HttpResponse:
    institution = Institution.objects.filter(pk=1).first()
    form = InstitutionForm(request.POST if request.method == "POST" else None, instance=institution)
    if request.method == "POST" and form.is_valid():
        Institution.objects.update_or_create(
            pk=1,
            defaults={"name": form.cleaned_data["name"], "updated_by": cast(User, request.user)},
        )
        messages.success(request, "Profil fakultas berhasil disimpan.")
        return redirect("academics:faculty")
    return render(request, "academics/faculty.html", {"form": form})


@require_http_methods(["GET", "POST"])
@login_required
@permission_required(
    ("accounts.access_system_workspace", "academics.add_studyprogram"), raise_exception=True
)
def register_program(request: HttpRequest) -> HttpResponse:
    institution = Institution.objects.filter(pk=1).first()
    edit_id = request.GET.get("sunting")
    editing = None
    if edit_id is not None:
        if not request.user.has_perm("academics.change_studyprogram"):
            raise PermissionDenied
        if not edit_id.isascii() or not edit_id.isdecimal() or len(edit_id) > 19:
            raise Http404
        editing = get_object_or_404(StudyProgram, pk=int(edit_id), institution=institution)
    form = StudyProgramForm(request.POST if request.method == "POST" else None, instance=editing)
    if request.method == "POST" and form.is_valid() and institution is not None:
        program = form.save(commit=False)
        program.institution = institution
        if editing is None:
            program.created_by = cast(User, request.user)
        try:
            with transaction.atomic():
                if editing is None:
                    program.save()
                elif not StudyProgram.objects.filter(pk=program.pk).update(
                    code=program.code, name=program.name, education_stage=program.education_stage
                ):
                    raise Http404
        except IntegrityError:
            if not StudyProgram.objects.filter(code=program.code).exclude(pk=program.pk).exists():
                raise
            form.add_error("code", "Kode program sudah digunakan.")
        else:
            messages.success(request, "Program studi berhasil disimpan.")
            return redirect("academics:register_program")
    return render(
        request,
        "academics/register_program.html",
        {
            "form": form,
            "editing": editing,
            "institution": institution,
            "programs": StudyProgram.objects.exclude(pk=editing.pk)
            if editing is not None
            else StudyProgram.objects.all(),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
@permission_required(
    (
        "accounts.access_system_workspace",
        "academics.add_studyprogram",
        "academics.delete_studyprogram",
    ),
    raise_exception=True,
)
def delete_program(request: HttpRequest, program_id: int) -> HttpResponse:
    program = get_object_or_404(StudyProgram, pk=program_id)
    if request.method == "POST":
        try:
            with transaction.atomic():
                program.delete()
        except IntegrityError:
            return render(
                request,
                "academics/delete_program.html",
                {"program": program, "protected": True},
                status=409,
            )
        messages.success(request, "Program studi berhasil dihapus.")
        return redirect("academics:register_program")
    return render(request, "academics/delete_program.html", {"program": program})


@require_http_methods(["GET", "HEAD"])
@login_required
def programs(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "academics/programs.html",
        {
            "programs": configurable_programs(cast(User, request.user)),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def periods(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if request.method == "POST":
        require_program_permission(actor, program_id, "academics.add_academicperiod")
    form = AcademicPeriodForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        period = form.save(commit=False)
        period.program = program
        period.created_by = actor
        try:
            with transaction.atomic():
                period.save()
        except IntegrityError:
            if not AcademicPeriod.objects.filter(program=program, code=period.code).exists():
                raise
            form.add_error("code", "Kode periode sudah digunakan di program ini.")
        else:
            return redirect("academics:periods", program_id=program.pk)
    return render(
        request,
        "academics/periods.html",
        {
            "program": program,
            "form": form,
            "periods": AcademicPeriod.objects.filter(program=program),
        },
    )
