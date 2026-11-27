from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Institution, Learner, StudyProgram
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.competencies.models import CompetencyFramework
from apps.epa.models import (
    EntrustableProfessionalActivity,
    EntrustmentDecision,
    EntrustmentReview,
    EPAAppeal,
    EPACommitteeBallot,
    EPACommitteeMandate,
    EPACommitteeParticipation,
    EPAPublication,
    EPAReviewAssignment,
    SupervisionScale,
)
from apps.epa.participation import quorum_count
from apps.learning.models import ProgressionReviewAssignment


@pytest.mark.django_db
def test_quorum_counts_only_the_latest_eligible_declaration_for_each_case(client: Client):
    admin = User.objects.create_superuser(username="admin-kehadiran")
    operator = User.objects.create_user(username="operator-riwayat")
    first = User.objects.create_user(username="anggota-kehadiran-a")
    second = User.objects.create_user(username="anggota-kehadiran-b")
    outsider = User.objects.create_user(username="nonanggota-kehadiran")
    synchronize_roles(admin, apply=True)
    UserRoleAssignment.objects.create(
        account=operator,
        role=AccessRole.objects.get(name="Administrator Fakultas"),
        assigned_by=admin,
    )
    today = timezone.localdate()
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program = StudyProgram.objects.create(
        institution=faculty,
        code="a",
        name="A",
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        created_by=admin,
    )
    period = AcademicPeriod.objects.create(
        program=program,
        code=str(today.year),
        name="Periode",
        starts_on=date(today.year, 1, 1),
        ends_on=date(today.year, 12, 31),
        created_by=admin,
    )
    cohort = Cohort.objects.create(period=period, code="1", name="Kohort", created_by=admin)
    learner = Learner.objects.create(
        account=User.objects.create_user(username="mahasiswa-kehadiran")
    )
    enrollment = cohort.enrollments.create(learner=learner, enrolled_on=today, created_by=admin)
    framework = CompetencyFramework.objects.create(program=program).versions.create(
        number=1, created_by=admin
    )
    scale = SupervisionScale.objects.create(program=program, code="skala", created_by=admin)
    scale_version = scale.versions.create(number=1, name="Skala", created_by=admin)
    level = scale_version.levels.create(
        position=1, label="Supervisi langsung", description="Pendamping hadir", created_by=admin
    )

    def publication(code):
        activity = EntrustableProfessionalActivity.objects.create(
            program=program, code=code, created_by=admin
        )
        version = activity.versions.create(
            number=1,
            title=code,
            description="Deskripsi EPA",
            framework=framework,
            scale=scale_version,
            created_by=admin,
        )
        return EPAPublication.objects.create(version=version, created_by=admin)

    current = publication("visite")
    outside = publication("lain")
    mandate = EPACommitteeMandate.objects.create(
        program=program,
        name="Komite",
        quorum=2,
        starts_on=today,
        ends_on=today + timedelta(days=2),
        issued_at=timezone.now(),
        issued_by=admin,
        created_by=admin,
    )
    mandate.scopes.create(activity=current.version.activity, created_by=admin)
    for member in (first, second):
        mandate.memberships.create(account=member, created_by=admin)

    def make_draft(published, reviewer):
        review = EPAReviewAssignment.objects.create(
            publication=published, enrollment=enrollment, reviewer=reviewer, created_by=admin
        )
        review.drafts.create(
            number=1, level=level, rationale="Alasan privat peninjau.", created_by=reviewer
        )

    detail = reverse("epa_participate", args=[mandate.pk, current.pk, enrollment.pk])
    outside_url = reverse("epa_participate", args=[mandate.pk, outside.pk, enrollment.pk])
    case_list = reverse("epa_participation_cases", args=[mandate.pk])
    audit = reverse("accounts:epa_participation_audit", args=[mandate.pk])
    chair = reverse("accounts:epa_committee_chair", args=[mandate.pk])
    discussion = reverse("epa_committee_discussion", args=[mandate.pk, current.pk, enrollment.pk])
    ballot_audit = reverse("accounts:epa_ballot_audit", args=[mandate.pk])
    client.force_login(first)
    assert client.get(detail).status_code == 404
    make_draft(current, first)
    make_draft(current, second)
    make_draft(outside, second)
    listing = client.get(case_list).content.decode()
    assert listing.count(detail) == 1
    assert outside_url not in listing
    assert client.get(outside_url).status_code == 404
    assert "Alasan privat peninjau" not in client.get(detail).content.decode()
    client.force_login(outsider)
    assert client.post(detail, {"present": "1", "conflict": "0"}).status_code == 404
    client.force_login(first)
    assert client.get(audit).status_code == 403
    assert client.post(detail, {"present": "1"}).status_code == 400
    eligible = {"present": "1", "conflict": "0"}
    assert client.post(detail, eligible).status_code == 302
    assert client.post(detail, eligible).status_code == 302
    assert EPACommitteeParticipation.objects.count() == 1
    assert quorum_count(mandate, current.pk, enrollment.pk) == 1
    chair_data = {"member": mandate.memberships.get(account=first).pk}
    assert client.post(chair, chair_data).status_code == 403
    client.force_login(operator)
    assert client.post(chair, chair_data).status_code == 302
    client.force_login(first)
    draft = EntrustmentReview.objects.get(
        assignment__reviewer=first, assignment__publication=current
    )
    opening = {"action": "open", "draft": draft.pk}
    assert client.post(discussion, opening).status_code == 400

    client.force_login(second)
    assert client.post(detail, {"present": "1", "conflict": "1"}).status_code == 302
    assert client.get(discussion).status_code == 403
    assert client.post(discussion, {"action": "comment", "body": "Tolak."}).status_code == 403
    assert quorum_count(mandate, current.pk, enrollment.pk) == 1
    assert client.post(detail, {"present": "0", "conflict": "0"}).status_code == 302
    assert quorum_count(mandate, current.pk, enrollment.pk) == 1
    assert client.post(detail, eligible).status_code == 302
    assert quorum_count(mandate, current.pk, enrollment.pk) == 2
    assert "Kuorum 2 dari 2" in client.get(detail).content.decode()
    assert quorum_count(mandate, outside.pk, enrollment.pk) == 0

    assert client.post(discussion, opening).status_code == 403
    client.force_login(first)
    foreign_draft = EntrustmentReview.objects.get(assignment__publication=outside)
    assert client.post(discussion, {**opening, "draft": foreign_draft.pk}).status_code == 400
    assert client.post(discussion, opening).status_code == 302
    assert client.post(discussion, opening).status_code == 409
    ballot = EPACommitteeBallot.objects.get()
    assert draft.rationale in client.get(discussion).content.decode()
    assert (
        client.post(
            discussion, {"action": "comment", "ballot": ballot.pk, "body": "Tinjau konteks klinis."}
        ).status_code
        == 302
    )
    approve = {"action": "vote", "ballot": ballot.pk, "choice": "approve"}
    assert client.post(discussion, approve).status_code == 302
    assert client.post(discussion, approve).status_code == 302
    assert client.post(discussion, {**approve, "choice": "reject"}).status_code == 409
    close = {"action": "close", "ballot": ballot.pk}
    second.is_active = False
    second.save(update_fields=["is_active"])
    assert client.post(discussion, close).status_code == 400
    second.is_active = True
    second.save(update_fields=["is_active"])
    client.force_login(second)
    assert client.post(discussion, close).status_code == 403
    assert client.post(discussion, {**approve, "choice": "abstain"}).status_code == 302
    client.force_login(first)
    assert client.post(discussion, close).status_code == 302
    ballot.refresh_from_db()
    assert ballot.outcome == EPACommitteeBallot.Outcome.RETURNED
    assert ballot.result["eligible"] == 2 and ballot.result["approvals"] == 1
    assert {item["vote"] for item in ballot.result["participants"]} == {"approve", "abstain"}
    assert client.post(discussion, opening).status_code == 302
    later = EPACommitteeBallot.objects.first()
    assert client.post(discussion, approve).status_code == 409
    approve["ballot"] = later.pk
    assert client.post(discussion, approve).status_code == 302
    client.force_login(second)
    assert client.post(discussion, approve).status_code == 302
    client.force_login(first)
    assert client.post(discussion, {**close, "ballot": later.pk}).status_code == 302
    later.refresh_from_db()
    assert later.outcome == EPACommitteeBallot.Outcome.ADVANCED
    assert client.post(discussion, opening).status_code == 409
    assert client.get(ballot_audit).status_code == 403
    client.force_login(operator)
    results = client.get(ballot_audit).content.decode()
    assert "Pembahasan lanjutan" in results and "Usulan lolos" in results
    verify_decision_and_appeal(client, admin, operator, first, outsider, later, draft)

    second.is_active = False
    second.save(update_fields=["is_active"])
    assert quorum_count(mandate, current.pk, enrollment.pk) == 1
    revoke = reverse("accounts:epa_committee", args=[mandate.pk])
    client.force_login(operator)
    assert client.post(revoke, {"action": "revoke"}).status_code == 302
    assert quorum_count(mandate, current.pk, enrollment.pk) == 0
    assert EPACommitteeParticipation.objects.filter(mandate=mandate).count() == 4
    history = client.get(audit)
    assert history.status_code == 200 and len(history.context["page"]) == 4
    client.force_login(first)
    assert client.get(detail).status_code == 404
    assert client.post(detail, eligible).status_code == 404


def verify_decision_and_appeal(
    client, admin, operator, original_chair, appeal_chair, ballot, draft
):
    program = ballot.mandate.program
    student = ballot.enrollment.learner.account
    UserRoleAssignment.objects.create(
        account=student,
        role=AccessRole.objects.get(name="Mahasiswa"),
        program=program,
        assigned_by=admin,
    )
    publish = reverse("epa_publish_decision", args=[ballot.pk])
    client.force_login(original_chair)
    assert client.post(publish).status_code == 409
    client.force_login(operator)
    policy = reverse("accounts:epa_appeal_policies")
    assert client.post(policy, {"program": program.pk, "days": 7}).status_code == 302
    assert client.post(publish).status_code == 404
    client.force_login(original_chair)
    assert client.post(publish).status_code == 302
    assert client.post(publish).status_code == 302
    decision = EntrustmentDecision.objects.get()
    assert decision.ballot == ballot and decision.created_by == original_chair
    detail = reverse("epa_student_decision", args=[decision.pk])
    assert client.get(detail).status_code == 404
    client.force_login(student)
    assert draft.rationale in client.get(detail).content.decode()
    assert detail in client.get(reverse("epa_student_decisions")).content.decode()
    with patch(
        "apps.epa.decisions.timezone.now", return_value=decision.appeal_until + timedelta(seconds=1)
    ):
        assert client.post(detail, {"reason": "Terlambat."}).status_code == 409
    assert client.post(detail, {"reason": "Mohon tinjau bukti ini."}).status_code == 302
    assert client.post(detail, {"reason": "Duplikat."}).status_code == 302
    appeal = EPAAppeal.objects.get()
    assert appeal.reason == "Mohon tinjau bukti ini."

    today = timezone.localdate()
    independent = EPACommitteeMandate.objects.create(
        program=program,
        name="Komite banding",
        quorum=1,
        starts_on=today,
        ends_on=today + timedelta(days=2),
        issued_at=timezone.now(),
        issued_by=admin,
        created_by=admin,
    )
    independent.scopes.create(activity=ballot.publication.version.activity, created_by=admin)
    member = independent.memberships.create(account=appeal_chair, created_by=admin)
    overlap = independent.memberships.create(account=original_chair, created_by=admin)
    client.force_login(operator)
    chair_url = reverse("accounts:epa_committee_chair", args=[independent.pk])
    assert client.post(chair_url, {"member": member.pk}).status_code == 302
    assign = reverse("accounts:epa_assign_appeal", args=[appeal.pk])
    assert client.post(assign, {"mandate": ballot.mandate_id}).status_code == 400
    assert client.post(assign, {"mandate": independent.pk}).status_code == 400
    overlap.delete()
    assert client.post(assign, {"mandate": independent.pk}).status_code == 302
    # A later policy changes only future decisions.
    assert client.post(policy, {"program": program.pk, "days": 14}).status_code == 302
    original_deadline = decision.appeal_until
    decision.refresh_from_db()
    assert decision.appeal_until == original_deadline

    case = [independent.pk, ballot.publication_id, ballot.enrollment_id]
    participation = reverse("epa_participate", args=case)
    discussion = reverse("epa_committee_discussion", args=case)
    client.force_login(appeal_chair)
    assert client.post(participation, {"present": "1", "conflict": "0"}).status_code == 302
    assert appeal.reason in client.get(discussion).content.decode()
    second_level = draft.level.version.levels.create(
        position=2,
        label="Supervisi tidak langsung",
        description="Pembimbing dapat dihubungi",
        created_by=admin,
    )
    opening = {
        "action": "open",
        "draft": draft.pk,
        "level": second_level.pk,
        "rationale": "Usulan komite banding.",
    }
    assert client.post(discussion, opening).status_code == 302
    appeal_ballot = EPACommitteeBallot.objects.get(mandate=independent)
    result_url = reverse("epa_resolve_appeal", args=[appeal_ballot.pk])
    assert client.post(result_url, {"reason": "Prematur."}).status_code == 404
    assert (
        client.post(
            discussion, {"action": "vote", "ballot": appeal_ballot.pk, "choice": "approve"}
        ).status_code
        == 302
    )
    assert (
        client.post(discussion, {"action": "close", "ballot": appeal_ballot.pk}).status_code == 302
    )
    assert client.post(result_url, {"reason": "Bukti mendukung perubahan."}).status_code == 302
    assert client.post(result_url, {"reason": "Duplikat."}).status_code == 302
    appeal.refresh_from_db()
    assert appeal.outcome == EPAAppeal.Outcome.CHANGED
    assert appeal.resolution == "Bukti mendukung perubahan."
    replacement = EntrustmentDecision.objects.get(replaces=decision)
    assert replacement.ballot.level == second_level
    assert decision.ballot.level != second_level
    client.force_login(student)
    original_page = client.get(detail).content.decode()
    assert "Keputusan diubah" in original_page
    assert appeal.resolution in original_page
    replacement_url = reverse("epa_student_decision", args=[replacement.pk])
    assert replacement_url in original_page
    assert client.post(replacement_url, {"reason": "Banding ulang."}).status_code == 409

    UserRoleAssignment.objects.create(
        account=original_chair,
        program=program,
        assigned_by=admin,
        role=AccessRole.objects.get(name="Peninjau Progresi"),
    )
    progression = ProgressionReviewAssignment.objects.create(
        enrollment=ballot.enrollment, reviewer=original_chair, assigned_by=admin
    )
    progression_url = reverse("progression_review_draft", args=[progression.pk])
    client.force_login(original_chair)
    assert "Digantikan" in client.get(progression_url).content.decode()
    assert (
        client.post(
            progression_url,
            {
                "recommendation": "Pertimbangkan hasil EPA terbaru.",
                "rationale": "Hasil banding tercatat.",
                "decisions": [replacement.pk],
                "previous": 0,
            },
        ).status_code
        == 302
    )
    assert progression.drafts.get().evidence.get().decision == replacement
