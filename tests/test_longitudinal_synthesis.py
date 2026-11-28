from datetime import date

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Institution, Learner, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.assessments.models import AssessmentBlueprint
from apps.competencies.models import CompetencyFramework
from apps.evidence.models import ArtifactMap, LearnerEvidenceBaseline
from apps.learning.models import LongitudinalSynthesis
from apps.reflection.models import Reflection, ReflectionAdvisorAssignment, ReflectionShare


@pytest.mark.django_db
def test_longitudinal_synthesis_authorization_and_source_revocation(client: Client) -> None:
    admin = User.objects.create_superuser(username="admin-sintesis")
    synchronize_roles(admin, apply=True)
    today = date(2026, 1, 1)
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program = StudyProgram.objects.create(
        institution=faculty,
        code="a",
        name="Prodi A",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=admin,
    )
    foreign = StudyProgram.objects.create(
        institution=faculty,
        code="b",
        name="Prodi B",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=admin,
    )
    period = AcademicPeriod.objects.create(
        program=program,
        code="2026",
        name="2026",
        starts_on=today,
        ends_on=date(2026, 12, 31),
        created_by=admin,
    )
    cohort = Cohort.objects.create(period=period, code="a", name="Kohort", created_by=admin)
    student = User.objects.create_user(username="mahasiswa-sintesis")
    learner = Learner.objects.create(account=student)
    enrollment = cohort.enrollments.create(learner=learner, enrolled_on=today, created_by=admin)
    other_learner = Learner.objects.create(account=User.objects.create_user(username="mhs-lain"))
    other_enrollment = cohort.enrollments.create(
        learner=other_learner, enrolled_on=today, created_by=admin
    )
    framework = CompetencyFramework.objects.create(program=program)
    framework_version = framework.versions.create(number=1, created_by=admin)
    blueprint = AssessmentBlueprint.objects.create(program=program)
    blueprint_version = blueprint.versions.create(
        framework_version=framework_version, number=1, created_by=admin
    )
    artifact_map = ArtifactMap.objects.create(program=program)
    version = artifact_map.versions.create(
        blueprint_version=blueprint_version, number=1, snapshot={}, created_by=admin
    )
    publication = artifact_map.publications.create(
        version=version, effective_on=today, requirements={}, created_by=admin
    )
    for enrolled in (enrollment, other_enrollment):
        LearnerEvidenceBaseline.objects.create(
            enrollment=enrolled, publication=publication, created_by=admin
        )
    review = "academics:evidence:longitudinal_review"
    review_url = reverse(review, args=[program.pk, enrollment.pk])
    other_review = reverse(review, args=[program.pk, other_enrollment.pk])
    foreign_review = reverse(review, args=[foreign.pk, enrollment.pk])
    academic_advisor = User.objects.create_user(username="dosen-pa")
    head = User.objects.create_user(username="kaprodi-sintesis")
    for account, name in (
        (academic_advisor, "Peninjau Sintesis"),
        (head, "Penanggung Jawab Akademik Prodi"),
    ):
        UserRoleAssignment.objects.create(
            account=account,
            role=AccessRole.objects.get(name=name),
            program=program,
            assigned_by=admin,
        )
    ProgramConfigurationGrant.objects.create(
        account=head, program=program, starts_on=timezone.localdate(), granted_by=admin
    )
    assignment_url = reverse("academics:academic_advisors", args=[program.pk, enrollment.pk])
    advisor_client, head_client = Client(), Client()
    advisor_client.force_login(academic_advisor)
    head_client.force_login(head)
    assert advisor_client.get(review_url).status_code == 403
    assert advisor_client.get(assignment_url).status_code == 403
    assignment_data = {"action": "assign", "advisor": academic_advisor.pk}
    assert head_client.post(assignment_url, assignment_data).status_code == 302
    assert head_client.post(assignment_url, assignment_data).status_code == 302
    queue = advisor_client.get(reverse("academic_review_queue"))
    assert review_url in queue.content.decode()
    assert advisor_client.get(review_url).status_code == 200
    assert advisor_client.post(review_url, {"body": " "}).status_code == 400
    assert advisor_client.get(other_review).status_code == 403
    assert advisor_client.post(other_review, {"body": "Di luar penugasan"}).status_code == 403
    assert head_client.get(foreign_review).status_code == 403
    UserRoleAssignment.objects.create(
        account=academic_advisor,
        role=AccessRole.objects.get(name="Pembimbing Refleksi"),
        program=program,
        assigned_by=admin,
    )
    reflection_assignment = ReflectionAdvisorAssignment.objects.create(
        advisor=academic_advisor, enrollment=enrollment, assigned_by=head
    )
    revision = Reflection.objects.create(enrollment=enrollment).revisions.create(
        number=1, body="Materi refleksi pribadi"
    )
    share = ReflectionShare.objects.create(revision=revision, assignment=reflection_assignment)
    shared_url = reverse("shared_reflection", args=[share.pk])
    assert shared_url in advisor_client.get(review_url).content.decode()
    synthesis_body = "Tindak lanjut kompetensi dari Peninjau Sintesis."
    assert advisor_client.post(review_url, {"body": synthesis_body}).status_code == 302
    synthesis = LongitudinalSynthesis.objects.get()
    assert synthesis.assignment.advisor == academic_advisor
    assert synthesis_body in head_client.get(review_url).content.decode()
    assert head_client.post(review_url, {"body": synthesis_body}).status_code == 403
    client.force_login(student)
    assert client.get(review_url).status_code == 403
    ReflectionShare.objects.filter(pk=share.pk).update(revoked_at=timezone.now())
    assert advisor_client.get(shared_url).status_code == 404
    assert shared_url not in advisor_client.get(review_url).content.decode()
    assert synthesis_body in advisor_client.get(review_url).content.decode()
    assert synthesis_body in head_client.get(review_url).content.decode()
    assert (
        head_client.post(
            assignment_url, {"action": "revoke", "assignment": synthesis.assignment_id}
        ).status_code
        == 302
    )
    assert advisor_client.get(review_url).status_code == 403
    assert advisor_client.post(review_url, {"body": synthesis_body}).status_code == 403
    assert synthesis_body in head_client.get(review_url).content.decode()
