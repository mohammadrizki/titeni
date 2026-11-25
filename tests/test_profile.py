import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_user_edits_own_profile_and_changes_password(client: Client) -> None:
    old = "Original!SyntheticCredential123"
    new = "Replacement!SyntheticCredential456"
    member = User.objects.create_user(username="member", email="member@example.test", password=old)
    other = User.objects.create_user(username="other", email="other@example.test")
    profile = reverse("profile:edit")
    password = reverse("profile:change_password")
    assert client.get(profile).status_code == client.get(password).status_code == 302
    client.force_login(member)
    assert "Profil saya" in client.get(profile).content.decode()
    data = {"username": "updated", "email": "new@example.test"}
    invalid = client.post(profile, data)
    assert "Masukkan kata sandi saat ini" in invalid.content.decode()
    member.refresh_from_db()
    assert member.email == "member@example.test"
    duplicate = client.post(profile, {**data, "email": other.email, "current_password": old})
    assert "Email sudah digunakan." in duplicate.content.decode()
    response = client.post(
        profile,
        {**data, "current_password": old, "is_superuser": True, "id": other.pk},
        follow=True,
    )
    assert "Profil Anda berhasil disimpan." in response.content.decode()
    member.refresh_from_db()
    other.refresh_from_db()
    assert (member.username, member.email, member.is_superuser) == (
        "updated",
        "new@example.test",
        False,
    )
    assert other.email == "other@example.test"

    assert (
        client.post(
            password, {"old_password": "wrong", "new_password1": new, "new_password2": new}
        ).status_code
        == 200
    )
    member.refresh_from_db()
    assert member.check_password(old)
    changed = client.post(
        password, {"old_password": old, "new_password1": new, "new_password2": new}, follow=True
    )
    assert "Kata sandi Anda berhasil diubah." in changed.content.decode()
    member.refresh_from_db()
    assert member.check_password(new) and not member.check_password(old)
    assert client.get(profile).status_code == 200
