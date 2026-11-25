import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from apps.academics.models import Institution
from apps.accounts.models import User


@pytest.mark.django_db
def test_superuser_manages_local_accounts(client: Client) -> None:
    admin = User.objects.create_superuser(username="operator")
    client.force_login(admin)
    directory = reverse("accounts:directory")
    original = "Synthetic!Credential123"
    new = "Another!SyntheticCredential456"
    assert (
        client.post(
            directory,
            {
                "username": "learner",
                "email": "learner@example.test",
                "password1": original,
                "password2": "mismatch",
            },
        ).status_code
        == 200
    )
    assert not User.objects.filter(username="learner").exists()
    assert (
        client.post(
            directory,
            {
                "username": "learner",
                "email": "learner@example.test",
                "is_active": "on",
                "password1": original,
                "password2": original,
            },
        ).status_code
        == 302
    )
    learner = User.objects.get(username="learner")
    assert learner.is_active and not learner.is_superuser and learner.check_password(original)
    learner.groups.add(Group.objects.create(name="Pembimbing"))
    assert "Pembimbing" in client.get(directory).content.decode()
    duplicate = client.post(
        directory,
        {
            "username": "second",
            "email": "LEARNER@example.test",
            "password1": original,
            "password2": original,
        },
    )
    assert "Email sudah digunakan." in duplicate.content.decode()
    edit = f"{directory}?sunting={learner.pk}"
    reset = reverse("accounts:reset_account_password", args=[learner.pk])
    delete = reverse("accounts:delete_account", args=[learner.pk])
    assert (
        client.post(
            edit, {"username": "student", "email": "student@example.test", "is_active": "on"}
        ).status_code
        == 302
    )
    learner.refresh_from_db()
    assert learner.username == "student" and learner.email == "student@example.test"
    assert client.post(reset, {"new_password1": new, "new_password2": new}).status_code == 302
    learner.refresh_from_db()
    assert learner.check_password(new) and not learner.check_password(original)
    client.force_login(learner)
    assert client.post(edit, {"username": "changed"}).status_code == 403
    assert client.post(reset, {"new_password1": new, "new_password2": new}).status_code == 403
    assert client.post(delete).status_code == 403
    client.force_login(admin)
    assert client.get(delete).status_code == 200
    faculty = Institution.objects.create(name="Fakultas Kedokteran", updated_by=learner)
    assert client.post(delete).status_code == 409
    faculty.delete()
    assert client.post(delete).status_code == 302
    assert not User.objects.filter(pk=learner.pk).exists()
    assert client.post(reverse("accounts:delete_account", args=[admin.pk])).status_code == 403
