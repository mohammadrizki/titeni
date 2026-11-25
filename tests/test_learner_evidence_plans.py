from datetime import date

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import (
    AcademicPeriod,
    Cohort,
    Institution,
    Learner,
    LearnerEnrollment,
    StudyProgram,
)
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.assessments.models import AssessmentBlueprint
from apps.competencies.models import CompetencyFramework
from apps.evidence.models import (
    ArtifactMap,
    ArtifactMapPublication,
    LearnerEvidenceBaseline,
    LearnerEvidencePlan,
)


@pytest.mark.django_db
def test_plan_draft_pins_saved_map_requires_permission_and_cannot_cross_programs(
    client: Client,
) -> None:
    manager = User.objects.create_user(username="pengelola")
    faculty = Institution.objects.create(name="Fakultas", updated_by=manager)
    learner = Learner.objects.create(account=User.objects.create_user(username="mahasiswa"))
    enrollments = []
    maps = []
    for code in ("satu", "dua"):
        program = StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=manager,
        )
        ProgramConfigurationGrant.objects.create(
            account=manager, program=program, granted_by=manager, starts_on=timezone.localdate()
        )
        period = AcademicPeriod.objects.create(
            program=program,
            code="2026",
            name="2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=manager,
        )
        cohort = Cohort.objects.create(period=period, code="a", name="Kohort A", created_by=manager)
        enrollments.append(
            LearnerEnrollment.objects.create(
                learner=learner,
                cohort=cohort,
                enrolled_on=date(2026, 2, 1),
                created_by=manager,
            )
        )
        framework = CompetencyFramework.objects.create(program=program)
        framework_version = framework.versions.create(number=1, created_by=manager)
        blueprint = AssessmentBlueprint.objects.create(program=program)
        version = blueprint.versions.create(
            framework_version=framework_version,
            number=1,
            created_by=manager,
        )
        artifact_map = ArtifactMap.objects.create(program=program)
        maps.append(
            artifact_map.versions.create(
                blueprint_version=version,
                number=1,
                created_by=manager,
                snapshot={
                    "requirements": [
                        {
                            "label": f"Persyaratan prodi {code}",
                            "minimum": 1,
                            "source": "Observasi",
                            "competency": "Komunikasi",
                            "context": "Klinis",
                        }
                    ],
                    "blueprint_proposals": [],
                },
            )
        )
    enrollment, other_enrollment = enrollments
    own_map, other_map = maps
    program_id = own_map.artifact_map.program_id
    other_program_id = other_map.artifact_map.program_id
    url = reverse("academics:evidence:plan_drafts", args=[program_id, enrollment.pk])
    assert client.get(url).status_code == 302
    client.force_login(manager)
    assert client.get(url).status_code == 403
    manager.user_permissions.add(Permission.objects.get(codename="view_learnerenrollment"))
    role = AccessRole.objects.create(
        name="Pengelola prodi",
        scope=AccessRole.Scope.PROGRAM,
        updated_by=manager,
    )
    UserRoleAssignment.objects.create(
        account=manager,
        role=role,
        program_id=program_id,
        assigned_by=manager,
    )
    role.permissions.add(Permission.objects.get(codename="view_learnerevidenceplan"))
    assert client.get(url).status_code == 200
    enrollment_url = reverse("academics:enrollments", args=[program_id, enrollment.cohort_id])
    assert url in client.get(enrollment_url).content.decode()
    assert client.post(url, {"artifact_map_version": own_map.pk}).status_code == 403

    role.permissions.add(Permission.objects.get(codename="add_learnerevidenceplan"))
    assert client.post(url, {"artifact_map_version": other_map.pk}).status_code == 200
    assert not LearnerEvidencePlan.objects.exists()
    data = {"artifact_map_version": own_map.pk}
    plan_url = client.post(url, data).headers["Location"]
    assert client.post(url, data).headers["Location"] == plan_url
    plan = LearnerEvidencePlan.objects.get()
    assert plan.created_by == manager and plan.artifact_map_version == own_map
    assert plan.enrollment == enrollment
    page = client.get(plan_url).content.decode()
    assert "Persyaratan prodi satu" in page and "Persyaratan prodi dua" not in page
    assert "belum menjadi baseline aktif" in page
    assert client.post(plan_url).status_code == 405
    forged = reverse("academics:evidence:plan_drafts", args=[program_id, other_enrollment.pk])
    assert client.get(forged).status_code == 404
    denied = reverse("academics:evidence:plan_drafts", args=[other_program_id, other_enrollment.pk])
    assert client.get(denied).status_code == 403

    publish_url = reverse("academics:evidence:publish_artifact_map", args=[program_id, own_map.pk])
    assert client.get(publish_url).status_code == 403
    role.permissions.add(Permission.objects.get(codename="add_artifactmappublication"))
    foreign_publish = reverse(
        "academics:evidence:publish_artifact_map", args=[program_id, other_map.pk]
    )
    assert client.get(foreign_publish).status_code == 404

    publication_data = {
        "effective_on": "2026-03-01",
        "manual-0-selected": "on",
        "manual-0-due_on": "2026-05-01",
        "manual-0-responsible": "Pembimbing akademik",
    }
    assert client.post(publish_url, {"effective_on": "2026-03-01"}).status_code == 200
    assert not ArtifactMapPublication.objects.exists()
    assert client.post(publish_url, publication_data).status_code == 302
    assert client.post(publish_url, publication_data).status_code == 302
    first_publication = ArtifactMapPublication.objects.get()
    assert first_publication.created_by == manager
    assert first_publication.requirements[0]["origin"] == "manual"
    assert first_publication.requirements[0]["due_on"] == "2026-05-01"
    assert first_publication.requirements[0]["responsible"] == "Pembimbing akademik"
    assert not LearnerEvidenceBaseline.objects.exists()

    second_map = own_map.artifact_map.versions.create(
        blueprint_version=own_map.blueprint_version,
        number=2,
        created_by=manager,
        snapshot={
            **own_map.snapshot,
            "blueprint_proposals": [
                {
                    "component": "Asesmen klinis",
                    "context": "Rawat jalan",
                    "minimum_observations": 3,
                    "targets": [],
                    "sources": [],
                }
            ],
        },
    )
    publish_next = reverse(
        "academics:evidence:publish_artifact_map", args=[program_id, second_map.pk]
    )
    assert client.post(publish_next, publication_data).status_code == 200
    assert ArtifactMapPublication.objects.count() == 1
    manager.user_permissions.add(Permission.objects.get(codename="add_learnerenrollment"))

    def enroll(username: str, enrolled_on: str) -> LearnerEnrollment:
        email = f"{username}@example.test"
        account = User.objects.create_user(username=username, email=email)
        assert (
            client.post(enrollment_url, {"email": email, "enrolled_on": enrolled_on}).status_code
            == 302
        )
        return LearnerEnrollment.objects.get(learner__account=account)

    before = enroll("awal", "2026-02-28")
    assert not LearnerEvidenceBaseline.objects.filter(enrollment=before).exists()
    active = enroll("aktif", "2026-03-01")
    assert active.evidence_baseline.publication == first_publication
    assert (
        client.post(
            publish_next,
            {**publication_data, "effective_on": "2026-04-01", "blueprint-0-selected": "on"},
        ).status_code
        == 302
    )
    second_publication = ArtifactMapPublication.objects.get(version=second_map)
    assert [row["origin"] for row in second_publication.requirements] == ["manual", "blueprint"]
    in_between = enroll("antara", "2026-03-31")
    assert in_between.evidence_baseline.publication == first_publication
    later = enroll("berikut", "2026-04-01")
    assert later.evidence_baseline.publication == second_publication
    active.refresh_from_db()
    assert active.evidence_baseline.publication == first_publication
    baseline_url = reverse("academics:evidence:plan_drafts", args=[program_id, later.pk])
    baseline_page = client.get(baseline_url).content.decode()
    assert "Baseline rencana bukti" in baseline_page and "Asesmen klinis" in baseline_page
    assert "Pembimbing akademik" in baseline_page
