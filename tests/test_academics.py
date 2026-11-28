from datetime import date, timedelta

import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Curriculum, Institution, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment

pytestmark = pytest.mark.django_db


def test_configure_single_faculty_and_register_program(client: Client) -> None:
    actor = User.objects.create_user(username="operator")
    client.force_login(actor)
    faculty = reverse("academics:faculty")
    register = reverse("academics:register_program")
    assert client.get(faculty).status_code == 403
    assert client.get(register).status_code == 403
    actor.user_permissions.add(
        *Permission.objects.filter(
            codename__in=["access_system_workspace", "change_institution", "add_studyprogram"]
        )
    )
    data = {"code": "medicine", "name": "Kedokteran", "education_stage": "professional"}
    assert client.post(register, data).status_code == 200
    assert StudyProgram.objects.count() == 0
    assert client.post(faculty, {"name": "Fakultas Kedokteran"}).status_code == 302
    response = client.post(faculty, {"name": "Fakultas Kedokteran Titeni"}, follow=True)
    assert response.redirect_chain == [(faculty, 302)]
    assert "Profil fakultas berhasil disimpan." in response.content.decode()
    assert "Fakultas Kedokteran Titeni" in response.content.decode()
    assert "Profil fakultas berhasil disimpan." not in client.get(faculty).content.decode()
    institution = Institution.objects.get()
    assert institution.name == "Fakultas Kedokteran Titeni"
    assert institution.updated_by == actor
    with pytest.raises(IntegrityError), transaction.atomic():
        Institution.objects.create(pk=2, name="Fakultas Kedua", updated_by=actor)
    assert client.post(register, data).status_code == 302
    program = StudyProgram.objects.get()
    assert program.institution == institution
    assert program.created_by == actor
    assert client.post(register, data).status_code == 200
    assert StudyProgram.objects.count() == 1

    edit = f"{register}?sunting={program.pk}"
    delete = reverse("academics:delete_program", args=[program.pk])
    assert client.get(edit).status_code == 403
    assert client.post(delete).status_code == 403
    actor.user_permissions.add(
        *Permission.objects.filter(codename__in=["change_studyprogram", "delete_studyprogram"])
    )
    assert client.get(edit).status_code == 200
    assert client.post(edit, {**data, "name": "Pendidikan Dokter"}).status_code == 302
    program.refresh_from_db()
    assert program.name == "Pendidikan Dokter"
    assert client.get(delete).status_code == 200
    assert StudyProgram.objects.filter(pk=program.pk).exists()
    period = AcademicPeriod.objects.create(
        program=program,
        code="semester-a",
        name="Semester A",
        created_by=actor,
        starts_on=timezone.localdate(),
        ends_on=timezone.localdate(),
    )
    assert client.post(delete).status_code == 409
    assert StudyProgram.objects.filter(pk=program.pk).exists()
    period.delete()
    assert client.post(delete).status_code == 302
    assert not StudyProgram.objects.filter(pk=program.pk).exists()


def test_scoped_periods_and_revocable_grants(client: Client) -> None:
    operator = User.objects.create_user(username="operator")
    manager = User.objects.create_user(username="manager")
    institution = Institution.objects.create(name="Fakultas Kedokteran", updated_by=operator)
    first = StudyProgram.objects.create(
        institution=institution,
        name="Program Satu",
        code="first",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=operator,
    )
    second = StudyProgram.objects.create(
        institution=institution,
        name="Program Dua",
        code="second",
        education_stage=StudyProgram.Stage.SPECIALIST,
        created_by=operator,
    )
    grants = reverse("accounts:program_grants")
    dates = {"starts_on": timezone.localdate().isoformat()}
    client.force_login(operator)
    assert client.get(grants).status_code == 403
    operator.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[
                "access_system_workspace",
                "add_programconfigurationgrant",
                "change_programconfigurationgrant",
            ]
        )
    )
    assert (
        client.post(grants, {"account": operator.pk, "program": first.pk, **dates}).status_code
        == 200
    )
    assert ProgramConfigurationGrant.objects.count() == 0
    assert (
        client.post(grants, {"account": manager.pk, "program": first.pk, **dates}).status_code
        == 302
    )
    grant = ProgramConfigurationGrant.objects.get()
    assert grant.granted_by == operator
    ProgramConfigurationGrant.objects.create(
        account=manager,
        program=second,
        granted_by=operator,
        starts_on=timezone.localdate() + timedelta(days=1),
    )
    client.force_login(manager)
    listing = client.get(reverse("academics:programs")).content.decode()
    assert "Program Satu" in listing and "Program Dua" not in listing
    periods = reverse("academics:periods", args=[first.pk])
    other = reverse("academics:periods", args=[second.pk])
    data = {
        "code": "2026-a",
        "name": "Semester A",
        "starts_on": "2026-01-01",
        "ends_on": "2026-06-30",
    }
    assert client.get(other).status_code == client.post(other, data).status_code == 404
    assert client.post(periods, data).status_code == 403
    manager.user_permissions.add(Permission.objects.get(codename="add_academicperiod"))
    assert client.post(periods, {**data, "ends_on": "2025-06-30"}).status_code == 200
    assert client.post(periods, {**data, "program": second.pk}).status_code == 302
    period = AcademicPeriod.objects.get()
    assert period.program == first and period.created_by == manager
    assert client.post(periods, data).status_code == 200
    assert AcademicPeriod.objects.count() == 1

    revoke = reverse("accounts:revoke_program_grant", args=[grant.pk])
    assert client.post(revoke).status_code == 403
    client.force_login(operator)
    assert client.get(revoke).status_code == 405
    assert client.post(revoke).status_code == 302
    grant.refresh_from_db()
    assert grant.revoked_by == operator and grant.revoked_at is not None
    client.force_login(manager)
    assert client.get(periods).status_code == 404
    assert client.post(periods, data).status_code == 404


def test_curriculum_drafts_are_versioned_and_program_scoped(client: Client) -> None:
    operator = User.objects.create_user(username="operator")
    manager = User.objects.create_user(username="manager")
    faculty = Institution.objects.create(name="Fakultas Kedokteran", updated_by=operator)
    program = StudyProgram.objects.create(
        institution=faculty,
        name="Kedokteran",
        code="med",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=operator,
    )
    other = StudyProgram.objects.create(
        institution=faculty,
        name="Anak",
        code="peds",
        education_stage=StudyProgram.Stage.SPECIALIST,
        created_by=operator,
    )
    ProgramConfigurationGrant.objects.create(
        account=manager,
        program=program,
        starts_on=timezone.localdate(),
        granted_by=operator,
    )
    client.force_login(manager)
    list_url = reverse("academics:curricula", args=[program.pk])
    data = {"code": "2026", "name": "Kurikulum 2026"}
    assert client.post(reverse("academics:curricula", args=[other.pk]), data).status_code == 404
    manager.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[
                "add_curriculum",
                "add_curriculumversion",
                "add_curriculumstage",
            ]
        )
    )
    result = client.post(list_url, data, follow=True)
    assert "Draf versi 1" in result.content.decode()
    curriculum = Curriculum.objects.get(program=program)
    first = curriculum.versions.get(number=1)
    first_url = reverse("academics:curriculum_version", args=[program.pk, first.pk])
    wrong_scope = reverse("academics:curriculum_version", args=[other.pk, first.pk])
    stage = {"code": "klinik", "name": "Klinik"}
    assert client.post(wrong_scope, stage).status_code == 404
    assert client.post(first_url, stage).status_code == 302
    duplicate = client.post(first_url, stage)
    assert "Kode tahap sudah digunakan" in duplicate.content.decode()
    new_url = reverse("academics:new_curriculum_version", args=[program.pk, curriculum.pk])
    assert client.get(new_url).status_code == 405
    assert client.post(new_url, follow=True).status_code == 200
    assert curriculum.versions.get(number=2).stages.count() == 0
    assert first.stages.get().name == "Klinik"


def test_period_row_actions_require_scope_permissions_and_confirmation(client: Client) -> None:

    manager = User.objects.create_user(username="row-manager")
    institution = Institution.objects.create(name="Fakultas", updated_by=manager)
    program, other = [
        StudyProgram.objects.create(
            institution=institution,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=manager,
        )
        for code in ("one", "two")
    ]
    period, foreign = [
        AcademicPeriod.objects.create(
            program=scope,
            code="2026",
            name="Periode awal",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=manager,
        )
        for scope in (program, other)
    ]
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, granted_by=manager, starts_on=timezone.localdate()
    )
    client.force_login(manager)

    def row(action: str, row_id: int = period.pk) -> str:
        return reverse("academics:row_action", args=[program.pk, "periode", row_id, action])

    index = reverse("academics:periods", args=[program.pk])
    preview = client.get(row("lihat"))
    assert preview.status_code == 200 and "Periode awal" in preview.content.decode()
    assert client.post(row("lihat")).status_code == 405
    assert client.get(row("lihat", foreign.pk)).status_code == 404
    assert client.get(row("sunting")).status_code == 403
    assert client.post(row("hapus")).status_code == 403
    manager.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="academics",
            codename__in=["change_academicperiod", "delete_academicperiod"],
        )
    )
    page = client.get(index).content.decode()
    for action in ("lihat", "sunting", "hapus"):
        assert f'href="{row(action)}"' in page
    assert 'aria-label="Simpan"' in client.get(row("sunting")).content.decode()
    changes = {
        "code": "2026",
        "name": "Periode revisi",
        "starts_on": "2026-01-01",
        "ends_on": "2026-12-31",
    }
    assert client.post(row("sunting", foreign.pk), changes).status_code == 404
    invalid = client.post(row("sunting"), {**changes, "ends_on": "2025-01-01"})
    assert invalid.status_code == 200
    period.refresh_from_db()
    assert period.name == "Periode awal"
    assert client.post(row("sunting"), changes).headers["Location"] == index
    period.refresh_from_db()
    assert period.name == "Periode revisi" and period.created_by == manager
    assert client.get(row("hapus")).status_code == 200
    assert AcademicPeriod.objects.filter(pk=period.pk).exists()
    cohort = Cohort.objects.create(period=period, code="a", name="A", created_by=manager)
    assert client.post(row("hapus")).status_code == 409
    cohort.delete()
    assert client.post(row("hapus")).headers["Location"] == index
    assert not AcademicPeriod.objects.filter(pk=period.pk).exists()


def test_program_role_can_manage_curriculum_only_in_assigned_program(client: Client) -> None:
    manager = User.objects.create_user(username="kaprodi")
    faculty = Institution.objects.create(name="Fakultas", updated_by=manager)
    programs = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=manager,
        )
        for code in ("satu", "dua")
    ]
    for program in programs:
        ProgramConfigurationGrant.objects.create(
            account=manager, program=program, granted_by=manager, starts_on=timezone.localdate()
        )
    role = AccessRole.objects.create(
        name="Penanggung Jawab Akademik Prodi", scope=AccessRole.Scope.PROGRAM, updated_by=manager
    )
    role.permissions.add(
        *Permission.objects.filter(
            content_type__app_label="academics",
            codename__in=["change_curriculum", "delete_curriculum"],
        )
    )
    UserRoleAssignment.objects.create(
        account=manager, role=role, program=programs[0], assigned_by=manager
    )
    client.force_login(manager)
    for program, allowed in zip(programs, (True, False), strict=True):
        curriculum = Curriculum.objects.create(program=program, code="2026", name="Kurikulum 2026")
        draft = curriculum.versions.create(number=1, created_by=manager)
        arguments = [program.pk, "kurikulum", curriculum.pk]
        edit = reverse("academics:row_action", args=[*arguments, "sunting"])
        delete = reverse("academics:row_action", args=[*arguments, "hapus"])
        index = reverse("academics:curricula", args=[program.pk])
        page = client.get(index).content.decode()
        assert (edit in page) == allowed
        assert (delete in page) == allowed
        data = {"code": "2026", "name": "Kurikulum revisi"}
        if allowed:
            assert client.post(edit, data).headers["Location"] == index
            curriculum.refresh_from_db()
            assert curriculum.name == data["name"]
            stage = draft.stages.create(code="a", name="Tahap A", created_by=manager)
            assert client.post(delete).status_code == 409
            assert draft.stages.filter(pk=stage.pk).exists()
            stage.delete()
            assert client.post(delete).headers["Location"] == index
            assert not Curriculum.objects.filter(pk=curriculum.pk).exists()
        else:
            assert client.post(edit, data).status_code == 403
            assert client.post(delete).status_code == 403
