from datetime import date

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Institution, Learner, StudyProgram
from apps.accounts.models import ProgramConfigurationGrant, User


@pytest.mark.django_db
def test_cohorts_and_enrollments_require_program_scope_and_explicit_permissions(
    client: Client,
) -> None:
    manager = User.objects.create_user(username="manager")
    student = User.objects.create_user(username="student", email="student@example.test")
    faculty = Institution.objects.create(name="Fakultas Kedokteran", updated_by=manager)
    program = StudyProgram.objects.create(
        institution=faculty,
        code="med",
        name="Kedokteran",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=manager,
    )
    other = StudyProgram.objects.create(
        institution=faculty,
        code="peds",
        name="Anak",
        education_stage=StudyProgram.Stage.SPECIALIST,
        created_by=manager,
    )
    first, second = [
        AcademicPeriod.objects.create(
            program=scope,
            code="2026",
            name="2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=manager,
        )
        for scope in [program, other]
    ]
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, starts_on=timezone.localdate(), granted_by=manager
    )
    client.force_login(manager)
    assert client.get(reverse("academics:programs")).status_code == 200
    list_url = reverse("academics:cohorts", args=[program.pk])
    cohort_data = {"code": "a", "name": "Kohort A"}
    assert client.post(list_url, {**cohort_data, "period": second.pk}).status_code == 200
    assert not Cohort.objects.exists()
    assert client.post(list_url, {**cohort_data, "period": first.pk}).status_code == 302
    assert client.post(list_url, {**cohort_data, "period": first.pk}).status_code == 200
    cohort = Cohort.objects.get()
    url = reverse("academics:enrollments", args=[program.pk, cohort.pk])
    assert client.get(url).status_code == 403
    manager.user_permissions.add(Permission.objects.get(codename="view_learnerenrollment"))
    assert client.get(url).status_code == 200
    enrollment = {"email": student.email.upper(), "enrolled_on": "2026-01-01"}
    assert client.post(url, enrollment).status_code == 403
    manager.user_permissions.add(Permission.objects.get(codename="add_learnerenrollment"))
    other_cohort = Cohort.objects.create(period=second, code="a", name="B", created_by=manager)
    forged = reverse("academics:enrollments", args=[program.pk, other_cohort.pk])
    assert client.post(forged, enrollment).status_code == 404
    assert not Learner.objects.exists()
    assert client.post(url, enrollment).status_code == 302
    assert client.post(url, enrollment).status_code == 200
    learner = Learner.objects.get(account=student)
    saved = learner.enrollments.get()
    assert saved.cohort == cohort and saved.created_by == manager
    assert "student" in client.get(url).content.decode()
