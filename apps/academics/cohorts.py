from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.academics.enrollment import enroll_account
from apps.academics.models import AcademicPeriod, Cohort, StudyProgram
from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.evidence.plans import can_access_plan


class CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["code", "name", "period"]
        labels = {"period": "Periode akademik"}

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        period = cast(forms.ModelChoiceField, self.fields["period"])
        period.queryset = AcademicPeriod.objects.filter(program=program)


class EnrollmentForm(forms.Form):
    email = forms.EmailField(label="Email akun mahasiswa", max_length=254)
    enrolled_on = forms.DateField(
        label="Tanggal pendaftaran", widget=forms.DateInput(attrs={"type": "date"})
    )


@require_http_methods(["GET", "POST"])
@login_required
def cohorts(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    form = CohortForm(request.POST if request.method == "POST" else None, program=program)
    if request.method == "POST" and form.is_valid():
        cohort = form.save(commit=False)
        cohort.created_by = actor
        try:
            with transaction.atomic():
                cohort.save()
        except IntegrityError:
            if not Cohort.objects.filter(period=cohort.period, code=cohort.code).exists():
                raise
            form.add_error("code", "Kode kohort sudah digunakan pada periode ini.")
        else:
            messages.success(request, "Kohort berhasil dibuat.")
            return redirect("academics:cohorts", program_id=program_id)

    return render(
        request,
        "academics/cohorts.html",
        {
            "program": program,
            "form": form,
            "cohorts": Cohort.objects.filter(period__program=program).select_related("period"),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def enrollments(request: HttpRequest, program_id: int, cohort_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    if not actor.has_perm("academics.view_learnerenrollment"):
        raise PermissionDenied
    cohort = get_object_or_404(
        Cohort.objects.select_related("period__program"),
        pk=cohort_id,
        period__program_id=program_id,
        period__program__in=configurable_programs(actor),
    )
    can_enroll = actor.has_perm("academics.add_learnerenrollment")
    form = EnrollmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if not can_enroll:
            raise PermissionDenied
        if form.is_valid():
            try:
                enroll_account(
                    cohort,
                    email=form.cleaned_data["email"],
                    enrolled_on=form.cleaned_data["enrolled_on"],
                    actor=actor,
                )
            except ValidationError as error:
                form.add_error("email", error)
            else:
                messages.success(request, "Pendaftaran mahasiswa berhasil disimpan.")
                return redirect("academics:enrollments", program_id=program_id, cohort_id=cohort_id)

    return render(
        request,
        "academics/enrollments.html",
        {
            "program": cohort.period.program,
            "cohort": cohort,
            "form": form if can_enroll else None,
            "can_view_plans": can_access_plan(actor, program_id, "view"),
            "enrollments": cohort.enrollments.select_related("learner__account"),
        },
    )
