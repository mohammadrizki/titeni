from importlib import import_module
from io import StringIO
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection

from apps.academics.models import Institution, StudyProgram
from apps.accounts.access import program_role_permissions
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import ROLE_CATALOG


@pytest.mark.django_db
def test_catalog_reconciles_only_managed_roles_and_keeps_assignments(client):
    admin = User.objects.create_superuser(username="administrator")
    local = User.objects.create_user(username="operator")
    student_role = AccessRole.objects.create(
        name="Mahasiswa", scope=AccessRole.Scope.PROGRAM, updated_by=admin
    )
    publication = Permission.objects.get(codename="add_evaluationrulepublication")
    student_role.permissions.add(publication)
    unrelated = AccessRole.objects.create(
        name="Peran lokal", scope=AccessRole.Scope.OTHER, updated_by=admin
    )
    unrelated.permissions.add(publication)
    output = StringIO()
    call_command("sync_access_roles", stdout=output)
    assert "Mahasiswa (ada) +11 -1" in output.getvalue()
    assert AccessRole.objects.count() == 2
    assert student_role.permissions.exists()

    call_command("sync_access_roles", apply=True, stdout=StringIO())
    assert set(AccessRole.objects.values_list("name", flat=True)) == {*ROLE_CATALOG, "Peran lokal"}
    assert set(student_role.permissions.values_list("codename", flat=True)) == {
        "add_reflection",
        "view_entrustmentdecision",
        "add_epaappeal",
        "view_progressiondecision",
        "add_progressionappeal",
        "add_learninggoal",
        "change_learninggoal",
        "add_learninggoalshare",
        "add_interventioncompletionreport",
        "add_reflectioncoachingmessage",
        "complete_coachingrecommendation",
    }
    assert unrelated.permissions.get() == publication
    assert (
        AccessRole.objects.get(name="Penanggung Jawab Akademik Prodi")
        .permissions.filter(pk=publication.pk)
        .exists()
    )
    assert not AccessRole.objects.get(name="Asesor").permissions.filter(pk=publication.pk).exists()
    assert (
        not AccessRole.objects.get(name="Pengelola Adaptasi")
        .permissions.filter(pk=publication.pk)
        .exists()
    )

    role = AccessRole.objects.get(name="Administrator Fakultas")
    UserRoleAssignment.objects.create(account=local, role=role, assigned_by=admin)
    client.force_login(local)
    assert client.get("/administrasi/").status_code == 200
    assert client.get("/akademik/fakultas/").status_code == 200
    assert not local.has_perm("adaptive.add_evaluationrulepublication")
    assert program_role_permissions(local, 1) == set()
    output = StringIO()
    call_command("sync_access_roles", apply=True, stdout=output)
    assert all(line.endswith("+0 -0") for line in output.getvalue().splitlines())
    assert role.assignments.get().account == local


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("migration_name", "app_label", "codename"),
    [
        ("0006_rename_synthesis_reviewer_role", "learning", "add_longitudinalsynthesis"),
        ("0007_rename_program_lead_role", "adaptive", "add_evaluationrulepublication"),
    ],
)
def test_role_rename_preserves_permission_and_assignment(migration_name, app_label, codename):
    migration = import_module(f"apps.accounts.migrations.{migration_name}")
    editor = SimpleNamespace(connection=connection)
    operator = User.objects.create_user(username="operator-rename")
    reviewer = User.objects.create_user(username="peninjau-rename")
    institution = Institution.objects.create(name="Fakultas", updated_by=operator)
    program = StudyProgram.objects.create(
        institution=institution,
        code="a",
        name="A",
        education_stage=StudyProgram.Stage.UNDERGRADUATE,
        created_by=operator,
    )
    role = AccessRole.objects.create(
        name=migration.FORMER_NAME, scope=AccessRole.Scope.PROGRAM, updated_by=operator
    )
    permission = Permission.objects.get(content_type__app_label=app_label, codename=codename)
    role.permissions.add(permission)
    assignment = UserRoleAssignment.objects.create(
        account=reviewer, role=role, program=program, assigned_by=operator
    )

    migration.rename_forward(apps, editor)
    migration.rename_forward(apps, editor)
    role.refresh_from_db()
    assignment.refresh_from_db()
    assert role.name == migration.NEW_NAME
    assert role.permissions.get() == permission
    assert assignment.role_id == role.pk and assignment.program_id == program.pk

    migration.rename_backward(apps, editor)
    role.refresh_from_db()
    assert role.name == migration.FORMER_NAME
    AccessRole.objects.create(
        name=migration.NEW_NAME, scope=AccessRole.Scope.PROGRAM, updated_by=operator
    )
    with pytest.raises(RuntimeError, match="Resolve the role duplication"):
        migration.rename_forward(apps, editor)
    role.refresh_from_db()
    assert role.name == migration.FORMER_NAME
    assert role.assignments.get() == assignment
