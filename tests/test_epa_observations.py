from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Institution, Learner, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.competencies.models import CompetencyFramework
from apps.epa.models import (
    EntrustableProfessionalActivity,
    EPAAssessorAssignment,
    EPAObservation,
    SupervisionScale,
)


@pytest.mark.django_db
def test_published_epa_preserves_scale_and_limits_recording_to_assigned_assessor(client: Client):
    admin = User.objects.create_superuser(username="admin-epa-observasi")
    head = User.objects.create_user(username="kaprodi-epa")
    assessor = User.objects.create_user(username="asesor-epa")
    other = User.objects.create_user(username="asesor-lain-epa")
    staff = User.objects.create_user(username="kurikulum-epa")
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program, foreign = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=admin,
        )
        for code in ("a", "b")
    ]
    synchronize_roles(admin, apply=True)
    for account, role, scope in (
        (head, "Kaprodi", program),
        (staff, "Pengelola Kurikulum", program),
        (assessor, "Asesor", program),
        (other, "Asesor", foreign),
    ):
        UserRoleAssignment.objects.create(
            account=account,
            role=AccessRole.objects.get(name=role),
            program=scope,
            assigned_by=admin,
        )
    today = timezone.localdate()
    for account in (head, staff):
        ProgramConfigurationGrant.objects.create(
            account=account, program=program, starts_on=today, granted_by=admin
        )

    enrollments = []
    for study_program in (program, foreign):
        period = AcademicPeriod.objects.create(
            program=study_program,
            code=str(today.year),
            name="Periode",
            starts_on=date(today.year, 1, 1),
            ends_on=date(today.year, 12, 31),
            created_by=admin,
        )
        cohort = Cohort.objects.create(period=period, code="1", name="Kohort", created_by=admin)
        student = User.objects.create_user(username=f"mahasiswa-epa-{study_program.code}")
        learner = Learner.objects.create(account=student)
        enrollments.append(
            cohort.enrollments.create(learner=learner, enrolled_on=today, created_by=admin)
        )
    enrollment, foreign_enrollment = enrollments
    framework = CompetencyFramework.objects.create(program=program).versions.create(
        number=1, created_by=admin
    )
    item = framework.items.create(code="kom", name="Komunikasi", created_by=admin)
    scale = SupervisionScale.objects.create(program=program, code="klinis", created_by=admin)
    first, second = [
        scale.versions.create(number=number, name=f"Skala {number}", created_by=admin)
        for number in (1, 2)
    ]
    level_data = {"position": 1, "label": "Observasi langsung", "description": "Pembimbing hadir"}
    wrong_level = second.levels.create(**level_data, created_by=admin)
    activity = EntrustableProfessionalActivity.objects.create(
        program=program, code="visite", created_by=admin
    )
    old, new = [
        activity.versions.create(
            number=number,
            title="Visite",
            description="Kunjungan klinis",
            framework=framework,
            scale=scale_version,
            created_by=admin,
        )
        for number, scale_version in ((1, first), (2, second))
    ]
    manage = "academics:epa:manage"
    manage_url = reverse(manage, args=[program.pk, activity.pk, old.pk])
    newer_url = reverse(manage, args=[program.pk, activity.pk, new.pk])
    scale_url = reverse("academics:epa:scale_version", args=[program.pk, scale.pk, first.pk])
    version_url = reverse("academics:epa:activity_version", args=[program.pk, activity.pk, old.pk])
    assignment_data = {"action": "assign", "enrollment": enrollment.pk, "assessor": assessor.pk}

    client.force_login(staff)
    assert client.post(manage_url, {"action": "publish"}).status_code == 403
    client.force_login(head)
    assert client.post(manage_url, assignment_data).status_code == 400
    assert client.post(manage_url, {"action": "publish"}).status_code == 400
    assert client.post(scale_url, level_data).status_code == 302
    assert client.post(version_url, {"item": item.pk, "kind": "core"}).status_code == 302
    assert client.post(manage_url, {"action": "publish"}).status_code == 302
    assert client.post(manage_url, {"action": "publish"}).status_code == 302
    assert client.post(scale_url, {**level_data, "position": 2}).status_code == 409
    assert client.post(version_url, {"item": item.pk, "kind": "core"}).status_code == 409
    assert client.post(manage_url, {**assignment_data, "assessor": other.pk}).status_code == 400
    assert (
        client.post(
            manage_url, {**assignment_data, "enrollment": foreign_enrollment.pk}
        ).status_code
        == 400
    )
    assert client.post(manage_url, assignment_data).status_code == 302
    assert client.post(manage_url, assignment_data).status_code == 302
    assignment = EPAAssessorAssignment.objects.get()
    observation_url = reverse("epa_observation_assignment", args=[assignment.pk])
    level = first.levels.get()
    data = {
        "occurred_on": today.isoformat(),
        "context": "Bangsal rawat inap",
        "case_complexity": "Komorbiditas multipel",
        "level": level.pk,
        "feedback": "Sampaikan prioritas perawatan lebih awal.",
    }
    assert client.post(observation_url, data).status_code == 404
    client.force_login(other)
    assert client.get(observation_url).status_code == 404
    assert client.post(observation_url, data).status_code == 404
    client.force_login(assessor)
    assert observation_url in client.get(reverse("epa_observations")).content.decode()
    assert client.post(observation_url, {**data, "level": wrong_level.pk}).status_code == 400
    assert (
        client.post(
            observation_url, {**data, "occurred_on": (today + timedelta(days=1)).isoformat()}
        ).status_code
        == 400
    )
    assert client.post(observation_url, data).status_code == 302
    observation = EPAObservation.objects.get()
    assert observation.created_by == assessor
    assert observation.assignment.publication.version == old
    assert observation.level.version == first

    client.force_login(head)
    assert data["feedback"] not in client.get(manage_url).content.decode()
    assert client.post(newer_url, {"action": "publish"}).status_code == 302
    assert client.post(manage_url, assignment_data).status_code == 400
    assert client.post(manage_url, {"action": "publish"}).status_code == 400
    client.force_login(assessor)
    assert data["feedback"] in client.get(observation_url).content.decode()
    assert client.post(observation_url, data).status_code == 409
    assert EPAObservation.objects.count() == 1
