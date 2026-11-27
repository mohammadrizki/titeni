from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.epa.models import EntrustableProfessionalActivity
from apps.learning.models import ProgressionCommitteeMandate


@pytest.mark.django_db
def test_faculty_can_issue_and_revoke_progression_mandate_without_epa(client: Client):
    admin = User.objects.create_superuser(username="admin-komite-progresi")
    operator = User.objects.create_user(username="operator-komite-progresi")
    head = User.objects.create_user(username="kaprodi-komite-progresi")
    first = User.objects.create_user(username="ketua-komite-progresi")
    second = User.objects.create_user(username="anggota-komite-progresi")
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program, other_program = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.UNDERGRADUATE,
            created_by=admin,
        )
        for code in ("a", "b")
    ]
    synchronize_roles(admin, apply=True)
    for account, role, scope in (
        (operator, "Administrator Fakultas", None),
        (head, "Kaprodi", program),
    ):
        UserRoleAssignment.objects.create(
            account=account,
            role=AccessRole.objects.get(name=role),
            program=scope,
            assigned_by=admin,
        )
    today = timezone.localdate()
    data = {
        "program": program.pk,
        "name": "Komite Progresi Sarjana",
        "starts_on": today.isoformat(),
        "ends_on": (today + timedelta(days=7)).isoformat(),
        "quorum": 2,
    }
    index = reverse("accounts:progression_committees")
    client.force_login(head)
    assert client.get(index).status_code == 403
    assert client.post(index, data).status_code == 403
    client.force_login(operator)
    assert client.get(index).status_code == 200
    assert client.post(index, {**data, "quorum": 0}).status_code == 400
    assert (
        client.post(index, {**data, "ends_on": (today - timedelta(days=1)).isoformat()}).status_code
        == 400
    )
    detail = client.post(index, data).headers["Location"]
    mandate = ProgressionCommitteeMandate.objects.get()
    assert "Capaian kompetensi dan kelanjutan studi" in client.get(detail).content.decode()
    assert client.post(detail, {"action": "issue"}).status_code == 400
    assert client.post(detail, {"action": "revoke"}).status_code == 409
    changed = {**data, "action": "update", "program": other_program.pk, "name": "Komite Progresi A"}
    assert client.post(detail, changed).status_code == 302
    mandate.refresh_from_db()
    assert mandate.program == program and mandate.name == changed["name"]

    member = {"action": "member", "account": first.pk}
    assert client.post(detail, member).status_code == 302
    assert client.post(detail, member).status_code == 302
    chair = mandate.memberships.get(account=first)
    issue = {"action": "issue", "chair": chair.pk}
    assert client.post(detail, issue).status_code == 400
    assert client.post(detail, {**member, "account": second.pk}).status_code == 302
    other_mandate = ProgressionCommitteeMandate.objects.create(
        program=other_program,
        name="Komite B",
        starts_on=today,
        ends_on=today,
        quorum=1,
        created_by=operator,
    )
    other_membership = other_mandate.memberships.create(account=second, added_by=operator)
    assert client.post(detail, {**issue, "chair": other_membership.pk}).status_code == 400
    assert (
        client.post(detail, {"action": "remove-member", "row": other_membership.pk}).status_code
        == 404
    )
    first.is_active = False
    first.save(update_fields=["is_active"])
    assert client.post(detail, issue).status_code == 400
    first.is_active = True
    first.save(update_fields=["is_active"])
    assert client.post(detail, issue).status_code == 302
    assert client.post(detail, issue).status_code == 302
    mandate.refresh_from_db()
    assert mandate.chair == chair and mandate.issued_by == operator
    assert not EntrustableProfessionalActivity.objects.filter(program=program).exists()
    assert client.post(detail, changed).status_code == 409
    assert client.post(detail, {"action": "remove-member", "row": chair.pk}).status_code == 409
    assert client.post(detail, {"action": "revoke"}).status_code == 302
    assert client.post(detail, {"action": "revoke"}).status_code == 302
    mandate.refresh_from_db()
    assert mandate.revoked_by == operator and mandate.memberships.count() == 2
    assert "Dicabut" in client.get(detail).content.decode()
