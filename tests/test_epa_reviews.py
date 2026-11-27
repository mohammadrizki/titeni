from datetime import date

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
    EntrustmentReview,
    EPAAssessorAssignment,
    EPAObservation,
    EPAPublication,
    EPAReviewAssignment,
    SupervisionScale,
)


@pytest.mark.django_db
def test_epa_review_versions_preserve_selected_observations_and_restrict_access(client: Client):
    admin = User.objects.create_superuser(username="admin-tinjauan-epa")
    head = User.objects.create_user(username="kaprodi-tinjauan-epa")
    reviewer = User.objects.create_user(username="peninjau-epa")
    other = User.objects.create_user(username="peninjau-lain-epa")
    assessor = User.objects.create_user(username="asesor-tinjauan-epa")
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
        (reviewer, "Peninjau EPA", program),
        (other, "Peninjau EPA", foreign),
    ):
        UserRoleAssignment.objects.create(
            account=account,
            role=AccessRole.objects.get(name=role),
            program=scope,
            assigned_by=admin,
        )
    today = timezone.localdate()
    ProgramConfigurationGrant.objects.create(
        account=head, program=program, starts_on=today, granted_by=admin
    )

    enrollments = []
    for index, study_program in enumerate((program, program, foreign)):
        period, _ = AcademicPeriod.objects.get_or_create(
            program=study_program,
            code=str(today.year),
            defaults={
                "name": "Periode",
                "starts_on": date(today.year, 1, 1),
                "ends_on": date(today.year, 12, 31),
                "created_by": admin,
            },
        )
        cohort, _ = Cohort.objects.get_or_create(
            period=period, code="1", defaults={"name": "Kohort", "created_by": admin}
        )
        learner = Learner.objects.create(
            account=User.objects.create_user(username=f"mahasiswa-tinjauan-{index}")
        )
        enrollments.append(
            cohort.enrollments.create(learner=learner, enrolled_on=today, created_by=admin)
        )
    enrollment, other_enrollment, foreign_enrollment = enrollments
    framework = CompetencyFramework.objects.create(program=program).versions.create(
        number=1, created_by=admin
    )
    scale = SupervisionScale.objects.create(program=program, code="klinis", created_by=admin)
    activity = EntrustableProfessionalActivity.objects.create(
        program=program, code="visite", created_by=admin
    )
    publications = []
    for number in (1, 2):
        scale_version = scale.versions.create(
            number=number, name=f"Skala {number}", created_by=admin
        )
        level = scale_version.levels.create(
            position=1, label="Supervisi langsung", description="Pembimbing hadir", created_by=admin
        )
        version = activity.versions.create(
            number=number,
            title="Visite",
            description="Kunjungan klinis",
            framework=framework,
            scale=scale_version,
            created_by=admin,
        )
        publications.append(
            (EPAPublication.objects.create(version=version, created_by=head), level)
        )
    (old, old_level), (current, current_level) = publications

    def observe(publication, enrolled, level, feedback):
        assignment, _ = EPAAssessorAssignment.objects.get_or_create(
            publication=publication,
            enrollment=enrolled,
            assessor=assessor,
            defaults={"created_by": head},
        )
        return EPAObservation.objects.create(
            assignment=assignment,
            occurred_on=today,
            context="Rawat inap",
            case_complexity="Multipel",
            level=level,
            feedback=feedback,
            created_by=assessor,
        )

    first = observe(old, enrollment, old_level, "Catatan riwayat versi 1")
    second = observe(current, enrollment, current_level, "Catatan versi 2")
    hidden = observe(current, other_enrollment, current_level, "Catatan mahasiswa lain")
    assign_url = reverse(
        "academics:epa:review_assignments", args=[program.pk, activity.pk, current.version_id]
    )
    old_url = reverse(
        "academics:epa:review_assignments", args=[program.pk, activity.pk, old.version_id]
    )
    assign = {"enrollment": enrollment.pk, "reviewer": reviewer.pk}

    client.force_login(reviewer)
    assert client.post(assign_url, assign).status_code == 403
    client.force_login(head)
    assert client.post(old_url, assign).status_code == 409
    assert (
        client.post(assign_url, {**assign, "enrollment": foreign_enrollment.pk}).status_code == 400
    )
    assert client.post(assign_url, {**assign, "reviewer": other.pk}).status_code == 400
    assert client.post(assign_url, assign).status_code == 302
    assert client.post(assign_url, assign).status_code == 302
    assignment = EPAReviewAssignment.objects.get()
    review_url = reverse("epa_review_draft", args=[assignment.pk])
    assert client.get(review_url).status_code == 404
    client.force_login(other)
    assert client.get(review_url).status_code == 404
    client.force_login(reviewer)
    assert review_url in client.get(reverse("epa_review_queue")).content.decode()
    page = client.get(review_url).content.decode()
    assert first.feedback in page and second.feedback in page and hidden.feedback not in page
    proposal = {
        "level": current_level.pk,
        "rationale": "Rekomendasi supervisi langsung.",
        "observations": [first.pk, second.pk],
        "previous": 0,
    }
    assert client.post(review_url, {**proposal, "observations": [hidden.pk]}).status_code == 400
    assert client.post(review_url, {**proposal, "level": old_level.pk}).status_code == 400
    assert client.post(review_url, proposal).status_code == 302
    assert client.post(review_url, proposal).status_code == 409
    revision = {
        **proposal,
        "previous": 1,
        "observations": [second.pk],
        "rationale": "Revisi alasan.",
    }
    assert client.post(review_url, revision).status_code == 302
    first_draft, second_draft = EntrustmentReview.objects.order_by("number")
    assert first_draft.created_by == reviewer
    assert set(first_draft.evidence.all()) == {first, second}
    assert list(second_draft.evidence.all()) == [second]
    assert second_draft.rationale in client.get(review_url).content.decode()
    client.force_login(head)
    assert second_draft.rationale not in client.get(assign_url).content.decode()
    UserRoleAssignment.objects.filter(account=reviewer, program=program).delete()
    client.force_login(reviewer)
    assert client.get(review_url).status_code == 404
