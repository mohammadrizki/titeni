from uuid import UUID

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


def test_public_shell(client: Client) -> None:
    home = client.get(reverse("home"))
    login = client.get(reverse("login"))

    assert home.status_code == login.status_code == 200
    assert "Titeni" in home.content.decode()
    assert "csrfmiddlewaretoken" in login.content.decode()
    assert "admin/js" not in login.content.decode()
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_system_workspace_requires_explicit_permissions(client: Client) -> None:
    account = User.objects.create_user(
        username="operator", email="operator@example.test", password="synthetic-test-password"
    )
    inactive = User.objects.create_user(username="inactive-user", is_active=False)
    assert isinstance(account.pk, UUID)
    assert isinstance(inactive.pk, UUID)

    workspace = reverse("accounts:system")
    directory = reverse("accounts:directory")
    response = client.get(workspace)
    assert response.status_code == 302
    assert response.headers["Location"] == f"{reverse('login')}?next={workspace}"

    wrong_identifier = client.post(
        reverse("login"), {"username": account.username, "password": "synthetic-test-password"}
    )
    assert wrong_identifier.status_code == 200
    assert client.get(workspace).status_code == 302

    response = client.post(
        reverse("login"), {"username": account.email.upper(), "password": "synthetic-test-password"}
    )
    assert response.status_code == 302
    assert client.get(workspace).status_code == 403
    assert client.get(directory).status_code == 403

    access_workspace = Permission.objects.get(
        content_type__app_label="accounts", codename="access_system_workspace"
    )
    account.user_permissions.add(access_workspace)
    assert client.get(workspace).status_code == 200
    assert client.get(directory).status_code == 403

    view_accounts = Permission.objects.get(content_type__app_label="accounts", codename="view_user")
    account.user_permissions.add(view_accounts)
    response = client.get(directory)
    assert response.status_code == 200
    assert "inactive-user" in response.content.decode()
    assert "Nonaktif" in response.content.decode()
    assert client.post(directory).status_code == 405

    account.user_permissions.remove(access_workspace)
    assert client.get(directory).status_code == 403
    assert client.get(reverse("logout")).status_code == 405
    assert client.post(reverse("logout")).status_code == 302
    assert client.get(workspace).status_code == 302
