from io import StringIO

import pytest
from django.contrib.auth.models import Permission
from django.core.management import call_command

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
    assert AccessRole.objects.get(name="Kaprodi").permissions.filter(pk=publication.pk).exists()
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
