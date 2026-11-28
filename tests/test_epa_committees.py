from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.epa.committees import eligible_mandates
from apps.epa.models import EntrustableProfessionalActivity, EPACommitteeMandate


@pytest.mark.django_db
def test_faculty_mandate_requires_scoped_activities_and_quorum_before_issuance(client: Client):
    admin = User.objects.create_superuser(username="superuser-komite")
    operator = User.objects.create_user(username="operator-komite")
    head = User.objects.create_user(username="kaprodi-komite")
    member = User.objects.create_user(username="anggota-komite")
    second = User.objects.create_user(username="anggota-kedua-komite")
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program, foreign = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=admin,
        )
        for code in ("a", "b")
    ]
    activity, another, outside = [
        EntrustableProfessionalActivity.objects.create(program=owner, code=code, created_by=admin)
        for owner, code in ((program, "visite"), (program, "konseling"), (foreign, "lain"))
    ]
    synchronize_roles(admin, apply=True)
    UserRoleAssignment.objects.create(
        account=operator,
        role=AccessRole.objects.get(name="Administrator Fakultas"),
        assigned_by=admin,
    )
    UserRoleAssignment.objects.create(
        account=head,
        role=AccessRole.objects.get(name="Penanggung Jawab Akademik Prodi"),
        program=program,
        assigned_by=admin,
    )
    today = timezone.localdate()
    url = reverse("accounts:epa_committees")
    data = {
        "program": program.pk,
        "name": "Komite supervisi klinis",
        "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=7)).isoformat(),
        "quorum": 2,
    }

    client.force_login(head)
    assert client.get(url).status_code == 403
    assert client.post(url, data).status_code == 403
    client.force_login(operator)
    assert client.get(url).status_code == 200
    assert client.post(url, {**data, "quorum": 0}).status_code == 400
    assert (
        client.post(url, {**data, "ends_on": (today - timedelta(days=1)).isoformat()}).status_code
        == 400
    )
    detail = client.post(url, data).headers["Location"]
    mandate = EPACommitteeMandate.objects.get()
    assert client.post(detail, {"action": "issue"}).status_code == 400
    edit = {f"mandate-{key}": value for key, value in data.items()}
    edit.update({"action": "update", "mandate-program": foreign.pk, "mandate-name": "Komite EPA"})
    assert client.post(detail, edit).status_code == 302
    mandate.refresh_from_db()
    assert mandate.program == program
    assert mandate.name == "Komite EPA"
    assert client.post(detail, {"action": "scope", "scope-activity": outside.pk}).status_code == 400
    scope = {"action": "scope", "scope-activity": activity.pk}
    assert client.post(detail, scope).status_code == 302
    assert client.post(detail, scope).status_code == 302
    assert mandate.scopes.count() == 1
    assert client.post(detail, {"action": "member", "member-account": member.pk}).status_code == 302
    assert client.post(detail, {"action": "issue"}).status_code == 400
    assert not eligible_mandates(member, activity).exists()
    assert client.post(detail, {"action": "member", "member-account": second.pk}).status_code == 302
    second_membership = mandate.memberships.get(account=second)
    remove = {"action": "remove-member", "row": second_membership.pk}
    assert client.post(detail, remove).status_code == 302
    assert client.post(detail, {"action": "issue"}).status_code == 400
    assert client.post(detail, {"action": "member", "member-account": second.pk}).status_code == 302
    assert client.post(detail, {"action": "issue"}).status_code == 302
    assert client.post(detail, {"action": "issue"}).status_code == 302
    mandate.refresh_from_db()
    assert mandate.issued_by == operator
    assert eligible_mandates(member, activity).get() == mandate
    assert not eligible_mandates(member, another).exists()
    assert not eligible_mandates(member, outside).exists()
    assert not eligible_mandates(head, activity).exists()
    with patch("apps.epa.committees.timezone.localdate", return_value=today - timedelta(days=1)):
        assert not eligible_mandates(member, activity).exists()
    with patch("apps.epa.committees.timezone.localdate", return_value=today + timedelta(days=8)):
        assert not eligible_mandates(member, activity).exists()
    second.is_active = False
    second.save(update_fields=["is_active"])
    assert not eligible_mandates(second, activity).exists()
    assert client.post(detail, {"action": "member", "member-account": head.pk}).status_code == 409
    assert client.post(detail, edit).status_code == 409
    assert client.post(detail, {"action": "revoke"}).status_code == 302
    mandate.refresh_from_db()
    assert mandate.revoked_by == operator
    assert not eligible_mandates(member, activity).exists()
    assert mandate.memberships.count() == 2
    assert "Dicabut" in client.get(detail).content.decode()
