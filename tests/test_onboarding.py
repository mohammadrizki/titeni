import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains, assertNotContains

from apps.academics.enrollment import enroll_account
from apps.academics.models import AcademicPeriod, Cohort, Institution, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import (
    ACADEMIC_MANAGER_ROLE,
    CURRICULUM_MANAGER_ROLE,
    PROGRAM_LEAD_ROLE,
    STUDENT_ROLE,
    synchronize_roles,
)
from apps.assessments.models import AssessmentBlueprint, AssessmentBlueprintVersion
from apps.competencies.models import CompetencyFramework, CompetencyFrameworkVersion
from apps.evidence.models import ArtifactMap, ArtifactMapPublication, ArtifactMapVersion


@pytest.mark.django_db
def test_home_dims_steps_as_readiness_changes_in_the_selected_program(client: Client) -> None:
    home = reverse("home")
    actor = User.objects.create_superuser(username="operator")
    synchronize_roles(actor, apply=True)
    student = User.objects.create_user(
        username="private-student", email="private@example.test", password="example"
    )
    client.force_login(actor)
    initial = client.get(home)
    assertNotContains(initial, "onboarding-step-complete")
    assertContains(
        initial,
        f'<a href="{reverse("academics:faculty")}">Isi profil fakultas</a>',
        html=True,
    )

    faculty = Institution.objects.create(name="Fakultas", updated_by=actor)
    programs = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=name,
            education_stage="undergraduate",
            created_by=actor,
        )
        for code, name in (("a", "Prodi Alfa"), ("b", "Prodi Beta"))
    ]
    first, second = programs
    today = timezone.localdate()
    for program in programs:
        ProgramConfigurationGrant.objects.create(
            account=actor, program=program, starts_on=today, granted_by=actor
        )
    for program in programs:
        UserRoleAssignment.objects.create(
            account=actor,
            role=AccessRole.objects.get(name=PROGRAM_LEAD_ROLE),
            program=program,
            assigned_by=actor,
        )
    assertContains(client.get(home), "onboarding-step-complete", count=3)
    role = AccessRole.objects.get(name=STUDENT_ROLE)
    UserRoleAssignment.objects.create(account=student, role=role, program=first, assigned_by=actor)
    period = AcademicPeriod.objects.create(
        program=first,
        code="tahun",
        name="Tahun",
        starts_on=today,
        ends_on=today,
        created_by=actor,
    )
    cohort = Cohort.objects.create(period=period, code="awal", name="Awal", created_by=actor)
    framework = CompetencyFramework.objects.create(program=first)
    competency = CompetencyFrameworkVersion.objects.create(
        framework=framework, number=1, created_by=actor
    )
    blueprint = AssessmentBlueprint.objects.create(program=first)
    version = AssessmentBlueprintVersion.objects.create(
        blueprint=blueprint, framework_version=competency, number=1, created_by=actor
    )
    artifact_map = ArtifactMap.objects.create(program=first)
    map_version = ArtifactMapVersion.objects.create(
        artifact_map=artifact_map,
        blueprint_version=version,
        number=1,
        snapshot={},
        created_by=actor,
    )
    ArtifactMapPublication.objects.create(
        artifact_map=artifact_map,
        version=map_version,
        effective_on=today,
        requirements=[{"origin": "manual"}],
        created_by=actor,
    )

    selected = {"prodi": first.pk}
    assert [item.done for item in client.get(home, selected).context["program_steps"]][-3:] == [
        True,
        False,
        False,
    ]
    client.force_login(student)
    waiting = client.get(home)
    assertContains(waiting, "Pendaftaran kohort belum tersedia.")
    assertNotContains(waiting, "Mulai Refleksi Pribadi")
    client.force_login(actor)
    enrollment = enroll_account(cohort, email=student.email, enrolled_on=today, actor=actor)
    response = client.get(home, selected)
    assert [item.done for item in response.context["program_steps"]][-3:] == [True, True, True]
    assertContains(response, "onboarding-step-complete", count=9)
    assertNotContains(response, f'<a href="{reverse("academics:faculty")}">Isi profil fakultas</a>')
    assertContains(
        response,
        f'<a href="{reverse("academics:curricula", args=[first.pk])}">Siapkan tahap kurikulum</a>',
        html=True,
    )
    assertNotContains(response, student.email)
    assertNotContains(response, student.username)
    assert all(
        item.done is False
        for item in client.get(home, {"prodi": second.pk}).context["program_steps"]
    )

    manager = User.objects.create_user(username="scoped-manager")
    ProgramConfigurationGrant.objects.create(
        account=manager, program=first, starts_on=today, granted_by=actor
    )
    UserRoleAssignment.objects.create(
        account=manager,
        role=AccessRole.objects.get(name=ACADEMIC_MANAGER_ROLE),
        program=first,
        assigned_by=actor,
    )
    client.force_login(manager)
    cohorts_url = reverse("academics:cohorts", args=[first.pk])
    enrollments_url = reverse("academics:enrollments", args=[first.pk, cohort.pk])
    assertContains(client.get(cohorts_url), f'href="{enrollments_url}"')
    assert client.get(enrollments_url).status_code == 200

    client.logout()
    assert (
        client.post(
            reverse("login"), {"username": student.email, "password": "example"}
        ).status_code
        == 302
    )
    response = client.get(home, {"prodi": second.pk})
    assertContains(response, "Rekap penyiapan Mahasiswa")
    assertContains(response, "Baseline bukti sudah tersedia.")
    assertNotContains(response, "Buat periode akademik")
    assertNotContains(response, second.name)
    for route in ("reflection_drafts", "learning_plan"):
        assertContains(response, reverse(route, args=[enrollment.pk]))
        assert client.get(reverse(route, args=[enrollment.pk])).status_code == 200
    assertNotContains(client.get(reverse("onboarding_guide")), "Terbitkan peta artefak")
    for route in ("reflection_index", "learning_index"):
        assert list(client.get(reverse(route)).context["enrollments"]) == [enrollment]
    client.force_login(actor)

    student.set_unusable_password()
    student.save(update_fields=["password"])
    assert [item.done for item in client.get(home, selected).context["program_steps"]][-3:] == [
        False,
        True,
        False,
    ]


@pytest.mark.django_db
def test_checklist_respects_configuration_scope_and_enrollment_read_permission(
    client: Client,
) -> None:
    home = reverse("home")
    guide = reverse("onboarding_guide")
    assert client.get(guide).status_code == 302
    assertNotContains(client.get(home), "checklist-memulai")
    actor = User.objects.create_user(username="pengelola")
    faculty = Institution.objects.create(name="Fakultas", updated_by=actor)
    visible = StudyProgram.objects.create(
        institution=faculty,
        code="a",
        name="Prodi terlihat",
        education_stage="undergraduate",
        created_by=actor,
    )
    hidden = StudyProgram.objects.create(
        institution=faculty,
        code="b",
        name="Prodi tersembunyi",
        education_stage="undergraduate",
        created_by=actor,
    )
    client.force_login(actor)
    assertContains(client.get(guide), "Belum ada langkah memulai untuk peran Anda.")
    assertNotContains(client.get(home), "Penyiapan prodi")
    ProgramConfigurationGrant.objects.create(
        account=actor, program=visible, starts_on=timezone.localdate(), granted_by=actor
    )
    assertNotContains(client.get(home), "Penyiapan prodi")
    role = AccessRole.objects.create(
        name=CURRICULUM_MANAGER_ROLE, scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    UserRoleAssignment.objects.create(account=actor, role=role, program=visible, assigned_by=actor)
    academic = AccessRole.objects.create(
        name=ACADEMIC_MANAGER_ROLE, scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    UserRoleAssignment.objects.create(
        account=actor, role=academic, program=hidden, assigned_by=actor
    )
    response = client.get(home, {"prodi": hidden.pk})
    assertContains(response, visible.name)
    assertNotContains(response, hidden.name)
    assertNotContains(response, "Penyiapan fakultas")
    assertContains(response, "Siapkan tahap kurikulum")
    assertNotContains(response, "Buat periode akademik")
    assertNotContains(response, "Daftarkan mahasiswa ke kohort")

    UserRoleAssignment.objects.create(
        account=actor, role=academic, program=visible, assigned_by=actor
    )
    response = client.get(home)
    assertContains(response, "Siapkan tahap kurikulum")
    assertContains(response, "Buat periode akademik")
    assertNotContains(response, "Daftarkan mahasiswa ke kohort")
