import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import AccessRole, User


@pytest.mark.django_db
def test_superuser_can_configure_scoped_role_without_granting_access(client: Client) -> None:
    operator = User.objects.create_user(username="operator")
    admin = User.objects.create_superuser(username="admin")
    url = reverse("accounts:roles")
    permissions = Permission.objects.filter(
        content_type__app_label="academics",
        codename__in=["add_academicperiod", "change_studyprogram"],
    )
    data = {
        "name": "Pengelola Prodi",
        "scope": "program",
        "permissions": [p.pk for p in permissions],
    }
    client.force_login(operator)
    assert client.get(url).status_code == 403
    assert client.post(url, data).status_code == 403
    client.force_login(admin)
    response = client.get(url)
    page = response.content.decode()
    assert response.status_code == 200
    assert 'type="checkbox"' in page
    assert 'aria-label="Pilih semua izin Academic"' in page
    assert 'aria-label="Pilih semua izin Accounts"' in page
    assert 'name="permissions"' in page
    assert '<details class="permission-details">' in page
    assert "role-name-cell" in page
    assert all(label in page for label in ["Profil Fakultas", "Program Studi", "Penugasan"])
    assert client.post(url, data).status_code == 302
    role = AccessRole.objects.get()
    assert role.updated_by == admin
    assert role.scope == AccessRole.Scope.PROGRAM
    assert list(role.permissions.order_by("pk")) == list(permissions.order_by("pk"))
    assert client.post(f"{url}?sunting={role.pk}", {**data, "permissions": []}).status_code == 302
    assert not role.permissions.exists()
    assert not operator.has_perm("academics.change_studyprogram")
    delete = reverse("accounts:delete_role", args=[role.pk])
    matrix = client.get(url).content.decode()
    assert all(f'title="{action}"' in matrix for action in ["Sunting", "Simpan", "Hapus"])
    assert client.get(delete).status_code == 200
    assert AccessRole.objects.filter(pk=role.pk).exists()
    client.force_login(operator)
    assert client.post(delete).status_code == 403
    client.force_login(admin)
    assert client.post(delete).status_code == 302
    assert not AccessRole.objects.filter(pk=role.pk).exists()


@pytest.mark.django_db
def test_superuser_assigns_multiple_roles_with_explicit_scope(client: Client) -> None:
    admin = User.objects.create_superuser(username="admin")
    member = User.objects.create_user(username="member")
    system = AccessRole.objects.create(name="System operator", scope="system", updated_by=admin)
    scoped = AccessRole.objects.create(name="Pengelola prodi", scope="program", updated_by=admin)
    faculty = Institution.objects.create(name="Fakultas Kedokteran", updated_by=admin)
    program = StudyProgram.objects.create(
        institution=faculty,
        name="Kedokteran",
        code="med",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=admin,
    )
    url = reverse("accounts:assign_roles", args=[member.pk])
    data = {"roles": [system.pk, scoped.pk]}
    client.force_login(member)
    assert client.post(url, {**data, "program": program.pk}).status_code == 403
    client.force_login(admin)
    response = client.post(url, data)
    assert "Pilih program studi" in response.content.decode()
    assert not member.role_assignments.exists()
    assert client.post(url, {**data, "program": program.pk}).status_code == 302
    assert client.post(url, {**data, "program": program.pk}).status_code == 302
    assert member.role_assignments.count() == 2
    assert member.role_assignments.get(role=system).program is None
    assert member.role_assignments.get(role=scoped).program == program
    assert member.role_assignments.get(role=scoped).assigned_by == admin
    directory = client.get(reverse("accounts:directory")).content.decode()
    assert "System operator" in directory and "Pengelola prodi · Kedokteran" in directory
    matrix = reverse("accounts:roles")
    assert (
        client.post(
            f"{matrix}?sunting={scoped.pk}", {"name": scoped.name, "scope": "system"}
        ).status_code
        == 200
    )
    scoped.refresh_from_db()
    assert scoped.scope == "program"
    assert client.post(reverse("accounts:delete_role", args=[scoped.pk])).status_code == 409
