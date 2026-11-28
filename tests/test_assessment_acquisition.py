from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import (
    AcademicPeriod,
    Cohort,
    Curriculum,
    Institution,
    Learner,
    StudyProgram,
)
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.adaptive.models import (
    AdaptiveAttemptOption,
    AdaptiveEscalation,
    AdaptivePolicyPublication,
    AdaptivePolicyVersion,
    AssessorFinding,
    AssessorFindingAssignment,
    AssessorFindingRevision,
    AttemptFulfillmentCheck,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvaluationRulePublication,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
    ScheduledAssessorAssignment,
)
from apps.assessments.models import (
    AssessmentAttempt,
    AssessmentBlueprint,
    AssessmentEvent,
    AssessmentParticipation,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyFramework, PerformanceStandard
from apps.evidence.models import (
    ArtifactMap,
    ArtifactMapPublication,
    EvidenceArtifact,
    EvidenceImportBatch,
    EvidenceIntegration,
    EvidenceInvalidation,
    EvidencePlacement,
    EvidenceRecord,
    EvidenceSource,
    EvidenceType,
    EvidenceVerification,
    ExternalEvidenceReceipt,
    LearnerEvidenceBaseline,
)
from apps.learning.models import (
    LearningGoalShare,
    ProgressionAppeal,
    ProgressionBallot,
    ProgressionCommitteeMandate,
    ProgressionDecision,
    ProgressionReviewAssignment,
    ReassessmentRequirement,
)
from apps.reflection.models import (
    CoachingRecommendation,
    ReflectionAdvisorAssignment,
    ReflectionShare,
)


@pytest.mark.django_db
def test_assessment_event_attempt_and_reference_permissions_and_scope(
    client: Client, tmp_path: Path
) -> None:
    actor = User.objects.create_user(username="pengelola")
    faculty = Institution.objects.create(name="Fakultas", updated_by=actor)
    entries = []
    for code in ("satu", "dua"):
        program = StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=actor,
        )
        period = AcademicPeriod.objects.create(
            program=program,
            code="2026",
            name="2026",
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
            created_by=actor,
        )
        cohort = Cohort.objects.create(period=period, code="a", name="Kohort", created_by=actor)
        learner = Learner.objects.create(account=User.objects.create_user(username=f"mhs-{code}"))
        enrollment = cohort.enrollments.create(
            learner=learner,
            enrolled_on=date(2026, 1, 1),
            created_by=actor,
        )
        framework = CompetencyFramework.objects.create(program=program)
        framework_version = framework.versions.create(number=1, created_by=actor)
        blueprint = AssessmentBlueprint.objects.create(program=program)
        version = blueprint.versions.create(
            framework_version=framework_version,
            number=1,
            created_by=actor,
        )
        curriculum = Curriculum.objects.create(program=program, code="k", name="Kurikulum")
        curriculum_version = curriculum.versions.create(number=1, created_by=actor)
        stage = curriculum_version.stages.create(code="a", name="Tahap A", created_by=actor)
        item = version.items.create(
            code="a",
            name="Simulasi",
            method="Observasi",
            purpose="Komunikasi",
            stage=stage,
            timing="Akhir tahap",
            created_by=actor,
        )
        source = EvidenceSource.objects.create(
            program=program,
            code="observasi",
            name="Observasi",
            acquisition="Formulir",
            verification="Pemeriksaan dokumen",
            created_by=actor,
        )
        evidence_type = EvidenceType.objects.create(
            program=program, code="catatan", name="Catatan", created_by=actor
        )
        capability = source.evidencesourcecapability_set.create(
            evidence_type=evidence_type, created_by=actor
        )
        link = BlueprintItemEvidenceSource.objects.create(
            item=item,
            capability=capability,
            created_by=actor,
        )
        entries.append((program, enrollment, item, link))

    (program, enrollment, item, link), (foreign, foreign_enrollment, foreign_item, foreign_link) = (
        entries
    )
    ProgramConfigurationGrant.objects.create(
        account=actor, program=program, granted_by=actor, starts_on=timezone.localdate()
    )
    role = AccessRole.objects.create(
        name="Pengelola", scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    UserRoleAssignment.objects.create(account=actor, role=role, program=program, assigned_by=actor)
    client.force_login(actor)
    index = reverse("academics:assessments:events", args=[program.pk])
    assert client.get(index).status_code == 403

    def allow(*codes: str) -> None:
        role.permissions.add(*Permission.objects.filter(codename__in=codes))

    allow("view_assessmentevent")
    event_data = {"component": item.pk, "name": "Pelaksanaan simulasi", "occurred_on": "2026-08-01"}
    assert client.post(index, event_data).status_code == 403
    allow("add_assessmentevent")
    assert client.post(index, {**event_data, "component": foreign_item.pk}).status_code == 200
    assert not AssessmentEvent.objects.exists()
    assert client.post(index, event_data).status_code == 302
    event = AssessmentEvent.objects.get()
    assert event.component == item and event.created_by == actor
    attempts_url = reverse("academics:assessments:attempts", args=[program.pk, event.pk])
    assert client.post(attempts_url, {"enrollment": enrollment.pk}).status_code == 403
    allow("view_assessmentattempt", "add_assessmentattempt", "view_learnerenrollment")
    assert client.post(attempts_url, {"enrollment": foreign_enrollment.pk}).status_code == 200
    assert not AssessmentParticipation.objects.exists()
    for _ in range(2):
        assert client.post(attempts_url, {"enrollment": enrollment.pk}).status_code == 302
    first, second = AssessmentAttempt.objects.all()
    assert (first.number, second.number) == (1, 2)
    assert first.participation == second.participation
    assert first.participation.enrollment == enrollment
    evidence_url = reverse(
        "academics:assessments:attempt_evidence", args=[program.pk, event.pk, first.pk]
    )
    assert client.get(evidence_url).status_code == 403
    allow("view_evidencerecord", "add_evidencerecord")
    record_data = {"source_link": link.pk, "reference": "SIM-2026-01"}
    assert (
        client.post(evidence_url, {**record_data, "source_link": foreign_link.pk}).status_code
        == 200
    )
    assert not EvidenceRecord.objects.exists()
    assert client.post(evidence_url, record_data).status_code == 302
    duplicate = client.post(evidence_url, record_data).content.decode()
    assert "Referensi bukti ini sudah tercatat." in duplicate
    record = EvidenceRecord.objects.get()
    assert record.attempt == first and record.source_link == link and record.created_by == actor
    assert record.reference in client.get(evidence_url).content.decode()
    foreign_url = reverse(
        "academics:assessments:attempt_evidence", args=[foreign.pk, event.pk, first.pk]
    )
    assert client.get(foreign_url).status_code == 404

    assert client.post(evidence_url, {**record_data, "reference": "SIM-2026-02"}).status_code == 302
    other_record = EvidenceRecord.objects.get(reference="SIM-2026-02")

    def verification_url(record_id: int, attempt_id: int = first.pk) -> str:
        return reverse(
            "academics:assessments:verify_evidence",
            args=[program.pk, event.pk, attempt_id, record_id],
        )

    verify_url = verification_url(record.pk)
    decision = {"status": "verified", "reason": "Referensi cocok dengan dokumen."}
    allow("add_evidenceverification")
    assert client.post(verify_url, decision).status_code == 403
    assert not EvidenceVerification.objects.exists()

    reviewer = User.objects.create_user(username="verifikator")
    reviewer.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[
                "view_assessmentevent",
                "view_assessmentattempt",
                "view_learnerenrollment",
                "view_evidencerecord",
                "add_evidenceverification",
            ]
        )
    )
    for scope in (program, foreign):
        ProgramConfigurationGrant.objects.create(
            account=reviewer, program=scope, granted_by=actor, starts_on=timezone.localdate()
        )
    client.force_login(reviewer)
    assert client.post(verify_url, decision).status_code == 403
    UserRoleAssignment.objects.create(
        account=reviewer, role=role, program=foreign, assigned_by=actor
    )
    assert client.post(verify_url, decision).status_code == 403
    UserRoleAssignment.objects.create(
        account=reviewer, role=role, program=program, assigned_by=actor
    )
    assert client.post(verification_url(record.pk, second.pk), decision).status_code == 404
    assert client.post(verify_url, {**decision, "reason": " "}).status_code == 200
    assert client.post(verify_url, {**decision, "status": "invalid"}).status_code == 200
    assert not EvidenceVerification.objects.exists()
    assert client.post(verify_url, decision).headers["Location"] == evidence_url
    assert client.post(verify_url, {"status": "rejected", "reason": "Perubahan"}).status_code == 409
    saved = EvidenceVerification.objects.get(record=record)
    assert saved.status == "verified" and saved.reason == decision["reason"]
    assert saved.created_by == reviewer and saved.created_at is not None
    assert (
        client.post(
            verification_url(other_record.pk),
            {
                "status": "rejected",
                "reason": "Referensi tidak cocok.",
            },
        ).status_code
        == 302
    )
    listing = client.get(evidence_url).content.decode()
    assert "Terverifikasi" in listing and "Ditolak" in listing
    detail = client.get(verify_url).content.decode()
    assert (
        saved.reason in detail and reviewer.username in detail and "Simpan keputusan" not in detail
    )

    assert list(EvidenceRecord.objects.eligible_for_reconciliation()) == [record]
    correction = {
        "action": "correct",
        "correction-source_link": link.pk,
        "correction-reference": record.reference,
        "correction-correction_reason": "Dokumen sumber telah diperbarui.",
    }
    client.force_login(actor)
    assert (
        client.post(verify_url, {**correction, "correction-correction_reason": ""}).status_code
        == 200
    )
    assert client.post(verify_url, correction).headers["Location"] == evidence_url
    assert client.post(verify_url, correction).status_code == 409
    revised = EvidenceRecord.objects.get(supersedes=record)
    assert revised.revision_number == 2 and revised.attempt == record.attempt
    assert revised.correction_reason == correction["correction-correction_reason"]
    assert not EvidenceVerification.objects.filter(record=revised).exists()
    assert EvidenceVerification.objects.filter(pk=saved.pk, status="verified").exists()
    assert not EvidenceRecord.objects.eligible_for_reconciliation().exists()
    history = client.get(verify_url).content.decode()
    assert "Digantikan" in history and saved.reason in history
    revised_url = verification_url(revised.pk)
    assert (
        client.post(
            revised_url, {"action": "invalidate", "cancel-reason": "Pembatalan sendiri"}
        ).status_code
        == 403
    )

    client.force_login(reviewer)
    assert client.post(verify_url, decision).status_code == 409
    assert client.post(revised_url, decision).status_code == 302
    assert list(EvidenceRecord.objects.eligible_for_reconciliation()) == [revised]
    cancel = {"action": "invalidate", "cancel-reason": "Referensi sudah tidak berlaku."}
    assert client.post(revised_url, {**cancel, "cancel-reason": ""}).status_code == 200
    assert not EvidenceInvalidation.objects.exists()
    assert client.post(revised_url, cancel).headers["Location"] == evidence_url
    assert client.post(revised_url, cancel).status_code == 409
    assert client.post(revised_url, decision).status_code == 409
    invalidation = EvidenceInvalidation.objects.get()
    assert invalidation.record == revised and invalidation.created_by == reviewer
    assert invalidation.reason == cancel["cancel-reason"]
    assert EvidenceVerification.objects.filter(record=revised, status="verified").exists()
    assert not EvidenceRecord.objects.eligible_for_reconciliation().exists()
    detail = client.get(revised_url).content.decode()
    assert "Dibatalkan" in detail and invalidation.reason in detail

    manual_type = EvidenceType.objects.create(
        program=program, code="manual", name="Catatan manual", created_by=actor
    )
    manual_cap = link.capability.source.evidencesourcecapability_set.create(
        evidence_type=manual_type, created_by=actor
    )
    manual_link = BlueprintItemEvidenceSource.objects.create(
        item=item, capability=manual_cap, created_by=actor
    )
    artifact_map = ArtifactMap.objects.create(program=program)
    map_version = artifact_map.versions.create(
        blueprint_version=item.version, number=1, created_by=actor, snapshot={}
    )
    target = item.version.framework_version.items.create(
        code="komunikasi", name="Komunikasi", created_by=actor
    )
    standard = PerformanceStandard.objects.create(item=target, code="simulasi")
    standard_version = standard.versions.create(
        number=1, description="Standar komunikasi simulasi", created_by=actor
    )
    base_entry = {
        "targets": [{"competency_id": target.pk}],
        "component": "Simulasi",
        "component_id": item.pk,
        "sources": [{"capability_id": link.capability_id}],
        "minimum_observations": 1,
    }
    publication = ArtifactMapPublication.objects.create(
        artifact_map=artifact_map,
        version=map_version,
        effective_on=date(2026, 1, 1),
        created_by=actor,
        requirements=[
            {"origin": "blueprint", "entry": {**base_entry, "context": context}}
            for context in ("Rawat pagi", "Rawat sore", "Rawat sore")
        ]
        + [
            {
                "origin": "manual",
                "entry": {
                    "label": "Catatan manual",
                    "capability_id": manual_cap.pk,
                    "minimum": 1,
                },
            }
        ],
    )
    baseline = LearnerEvidenceBaseline.objects.create(
        enrollment=enrollment, publication=publication, created_by=actor
    )

    def verified_evidence(reference: str, context: str, source=link) -> EvidenceRecord:
        evidence = EvidenceRecord.objects.create(
            attempt=first,
            source_link=source,
            reference=reference,
            context=context,
            created_by=actor,
        )
        EvidenceVerification.objects.create(
            record=evidence, status="verified", reason="Cocok", created_by=reviewer
        )
        return evidence

    auto = verified_evidence("SIM-PAGI", "rawat pagi")
    ambiguous = verified_evidence("SIM-SORE", "Rawat sore")
    absent_context = verified_evidence("SIM-TANPA-KONTEKS", "")
    unmatched = verified_evidence("SIM-LAIN", "Konteks lain")
    manual = verified_evidence("SIM-MANUAL", "Rawat pagi", source=manual_link)
    student_role = AccessRole.objects.create(
        name="Mahasiswa refleksi", scope="program", updated_by=actor
    )
    student_role.permissions.add(Permission.objects.get(codename="add_reflection"))
    student = enrollment.learner.account
    UserRoleAssignment.objects.create(
        account=student, program=program, role=student_role, assigned_by=actor
    )
    client.force_login(student)
    reflection_url = reverse("reflection_drafts", args=[enrollment.pk])
    assert (
        client.post(
            reflection_url,
            {
                "revision": 0,
                "body": "Draf refleksi",
                "evidence": [other_record.pk],
            },
        ).status_code
        == 200
    )
    created_reflection = client.post(
        reflection_url,
        {
            "revision": 0,
            "body": "Draf refleksi",
            "evidence": [auto.pk, ambiguous.pk],
        },
    )
    assert created_reflection.status_code == 302
    reflection_detail = created_reflection["Location"]
    assert (
        client.post(
            reflection_detail,
            {
                "revision": 1,
                "body": "Draf refleksi",
                "evidence": [ambiguous.pk],
            },
        ).status_code
        == 302
    )
    assert "Versi 2" in client.get(reflection_detail).content.decode()
    with_summary = client.get(reflection_detail)
    summary = with_summary.context["evidence_summary"]
    assert summary.revision == 2 and summary.eligible_count == 1 and summary.attempt_count == 1
    assert summary.rows[0].context == "Rawat sore"
    assert "Ringkasan bukti otomatis" in with_summary.content.decode()
    assert with_summary.context["form"].initial["body"] == "Draf refleksi"
    foreign_competency = foreign_item.version.framework_version.items.create(
        code="khusus", name="Kompetensi lintas prodi", created_by=actor
    )
    competency_change = {
        "revision": 2,
        "body": "Draf refleksi",
        "evidence": [ambiguous.pk],
        "competencies": [foreign_competency.pk],
    }
    rejected = client.post(reflection_detail, competency_change)
    assert rejected.status_code == 200 and "competencies" in rejected.context["form"].errors
    assert "Kompetensi lintas prodi" not in client.get(reflection_detail).content.decode()
    assert (
        client.post(
            reflection_detail, {**competency_change, "competencies": [target.pk]}
        ).status_code
        == 302
    )
    with_prompt = client.get(reflection_detail)
    assert with_prompt.context["evidence_summary"].revision == 3
    assert list(with_prompt.context["prompt_competencies"]) == [target]
    assert f"tentang {target.name}?" in with_prompt.content.decode()
    assert with_prompt.context["form"].initial["body"] == "Draf refleksi"
    learning_url = reverse("learning_plan", args=[enrollment.pk])
    assert client.get(learning_url).status_code == 404
    student_role.permissions.add(Permission.objects.get(codename="add_learninggoal"))
    goal = {
        "competency": target.pk,
        "rationale": "Perlu latihan",
        "activity": "Latihan komunikasi",
        "expected_outcome": "Menjelaskan dengan runtut",
        "improvement_evidence": "Catatan latihan",
        "completion_criteria": "Selesaikan satu latihan",
        "due_on": "2027-01-10",
        "review_on": "2027-01-12",
    }
    assert (
        client.post(learning_url, {**goal, "competency": foreign_competency.pk}).status_code == 200
    )
    assert not client.get(learning_url).context["goals"]
    assert client.post(learning_url, goal).status_code == 302
    assert client.get(learning_url).context["goals"].get().activity == goal["activity"]
    source_revision = with_prompt.context["revisions"][0]
    assert (
        client.get(learning_url, {"reflection_source": source_revision.pk})
        .context["form"]
        .initial["reflection_source"]
        == source_revision.pk
    )
    advisor_assignment = ReflectionAdvisorAssignment.objects.create(
        enrollment=enrollment, advisor=reviewer, assigned_by=actor
    )
    source_share = ReflectionShare.objects.create(
        revision=source_revision, assignment=advisor_assignment
    )
    recommendation = CoachingRecommendation.objects.create(
        share=source_share, author=reviewer, body="Coba latihan dengan umpan balik."
    )
    both = client.post(
        learning_url,
        {
            **goal,
            "reflection_source": source_revision.pk,
            "coaching_source": recommendation.pk,
        },
    )
    assert both.status_code == 200 and both.context["form"].non_field_errors()
    assert (
        client.post(learning_url, {**goal, "reflection_source": source_revision.pk}).status_code
        == 302
    )
    assert (
        client.post(learning_url, {**goal, "coaching_source": recommendation.pk}).status_code == 302
    )
    goals = client.get(learning_url).context["goals"]
    assert goals.get(reflection_source=source_revision).coaching_source is None
    assert goals.get(coaching_source=recommendation).reflection_source is None
    saved_goal = goals.get(reflection_source=source_revision)
    edit_goal = reverse("learning_goal", args=[enrollment.pk, saved_goal.pk])
    assert client.get(edit_goal).status_code == 403
    student_role.permissions.add(Permission.objects.get(codename="change_learninggoal"))
    change = {
        **goal,
        "revision": 1,
        "activity": "Latihan revisi",
        "reflection_source": source_revision.pk,
    }
    assert client.post(edit_goal, change).status_code == 302
    assert client.post(edit_goal, change).status_code == 409
    saved_goal.refresh_from_db()
    assert saved_goal.activity == "Latihan revisi" and saved_goal.revision_number == 2
    assert saved_goal.revisions.get(number=1).snapshot["activity"] == goal["activity"]
    assert client.post(edit_goal, {**change, "revision": 2}).status_code == 302
    assert saved_goal.revisions.count() == 1
    share_goal = reverse("learning_goal_shares", args=[enrollment.pk, saved_goal.pk])
    assert client.get(share_goal).status_code == 404
    student_role.permissions.add(Permission.objects.get(codename="add_learninggoalshare"))
    advisor_role = AccessRole.objects.create(
        name="Pembimbing tujuan", scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    advisor_role.permissions.add(
        *Permission.objects.filter(codename__in=["view_reflectionshare", "add_learninggoalreview"])
    )
    UserRoleAssignment.objects.create(
        account=reviewer, role=advisor_role, program=program, assigned_by=actor
    )
    assert (
        client.post(
            share_goal,
            {
                "action": "share",
                "number": "1",
                "assignment": advisor_assignment.pk,
            },
        ).status_code
        == 302
    )
    goal_share = LearningGoalShare.objects.get(goal=saved_goal)
    assert goal_share.snapshot["activity"] == goal["activity"]
    assert "reflection_source" not in goal_share.snapshot
    review_goal = reverse("learning_goal_review", args=[goal_share.pk])
    client.force_login(reviewer)
    review_page = client.get(review_goal)
    assert review_page.status_code == 200 and "Latihan revisi" not in review_page.content.decode()
    assert review_goal in client.get(reverse("learning_review_queue")).content.decode()
    assert client.post(review_goal, {"note": "Perjelas bukti kemajuan."}).status_code == 302
    client.force_login(student)
    assert "Perjelas bukti kemajuan." in client.get(review_goal).content.decode()
    assert client.post(share_goal, {"action": "revoke", "share": goal_share.pk}).status_code == 302
    assert client.get(review_goal).status_code == 200
    client.force_login(reviewer)
    assert client.get(review_goal).status_code == 404
    client.force_login(reviewer)
    assert client.get(learning_url).status_code == 404
    client.force_login(reviewer)
    reconcile_url = reverse("academics:evidence:reconcile", args=[program.pk, enrollment.pk])
    assert client.get(reconcile_url).status_code == 403
    allow("view_learnerevidenceplan")
    response = client.get(reconcile_url)
    assert response.status_code == 200
    assert [row["record"] for row in response.context["counted"]] == [auto]
    assert {row["record"] for row in response.context["pending"]} == {
        ambiguous,
        absent_context,
        unmatched,
        manual,
    }
    data = {"record_id": ambiguous.pk, "requirement_number": 2, "reason": "Dipilih saat tinjauan."}
    assert client.post(reconcile_url, data).status_code == 403
    allow("add_evidenceplacement")
    assert client.post(reconcile_url, {**data, "requirement_number": 1}).status_code == 400
    assert client.post(reconcile_url, {**data, "record_id": auto.pk}).status_code == 400
    assert client.post(reconcile_url, {**data, "record_id": revised.pk}).status_code == 409
    assert client.post(reconcile_url, data).status_code == 302
    assert client.post(reconcile_url, data).status_code == 302
    assert client.post(reconcile_url, {**data, "requirement_number": 3}).status_code == 409
    placement = EvidencePlacement.objects.get()
    assert placement.record == ambiguous and placement.baseline == baseline
    assert placement.created_by == reviewer and placement.requirement_number == 2
    assert (
        client.post(
            reconcile_url, {**data, "record_id": manual.pk, "requirement_number": 4}
        ).status_code
        == 302
    )
    assert [count for _, count in client.get(reconcile_url).context["progress"]] == [1, 1, 0, 1]
    evaluation_url = reverse("academics:evidence:evaluations", args=[program.pk, enrollment.pk])
    assert client.get(evaluation_url).status_code == 403
    review_url = reverse("academics:evidence:longitudinal_review", args=[program.pk, enrollment.pk])
    assert client.get(review_url).status_code == 403
    allow("view_evidenceevaluation", "add_evidenceevaluation", "add_evaluationruleversion")
    assert evaluation_url in client.get(reconcile_url).content.decode()
    review = client.get(review_url)
    assert review.status_code == 200
    assert not review.context["history"].object_list
    assert list(review.context["shared_reflections"]) == [source_share]
    assert not review.context["shared_goals"]
    assert reverse("shared_reflection", args=[source_share.pk]) in review.content.decode()
    assert reverse("reflection_coaching", args=[source_share.pk]) in review.content.decode()
    active_goal_share = LearningGoalShare.objects.create(
        goal=saved_goal, assignment=advisor_assignment, number=1, snapshot=goal_share.snapshot
    )
    review = client.get(review_url)
    assert list(review.context["shared_goals"]) == [active_goal_share]
    assert "Latihan revisi" not in review.content.decode()
    assert recommendation.body not in review.content.decode()
    LearningGoalShare.objects.filter(pk=active_goal_share.pk).update(revoked_at=timezone.now())
    ReflectionShare.objects.filter(pk=source_share.pk).update(revoked_at=timezone.now())
    review = client.get(review_url)
    assert not review.context["shared_reflections"]
    assert not review.context["shared_goals"]
    assert client.post(review_url).status_code == 403
    foreign_review = reverse(
        "academics:evidence:longitudinal_review", args=[program.pk, foreign_enrollment.pk]
    )
    assert client.get(foreign_review).status_code == 404
    assert review_url in client.get(evaluation_url).content.decode()
    assert client.get(evaluation_url).status_code == 200
    planning_url = reverse("academics:evidence:planning_demonstration", args=[program.pk])
    assert planning_url in client.get(evaluation_url).content.decode()
    scenario = client.post(
        planning_url,
        {
            "sufficiency": "insufficient",
            "performance": "undetermined",
            "context_gap": 1,
            "assessor_gap": 1,
            "combined_slots": 1,
            "context_slots": 1,
            "assessor_slots": 1,
            "pending": 0,
            "maximum_new": 1,
        },
    )
    assert scenario.status_code == 200
    assert "Gabungan · Cakupan konteks, Keberagaman asesor" in scenario.content.decode()
    assert not EvidenceEvaluation.objects.exists()
    demo = client.post(
        evaluation_url,
        {
            "action": "performance-demo",
            "sufficiency": "sufficient",
            "below": 0,
            "meets": 2,
            "minimum_below": 1,
            "minimum_meets": 2,
        },
    )
    assert demo.context["performance_result"].status == "closed"
    assert "Kesenjangan performa: tertutup." in demo.content.decode()
    assert not EvidenceEvaluation.objects.exists()
    rule_data = {
        "action": "new-rule",
        "standard": standard_version.pk,
        "minimum_attempts": 1,
        "minimum_contexts": 2,
        "minimum_verifiers": 1,
    }
    assert client.post(evaluation_url, {**rule_data, "minimum_attempts": 0}).status_code == 200
    assert not EvaluationRuleVersion.objects.exists()
    assert client.post(evaluation_url, rule_data).status_code == 302
    rule = EvaluationRuleVersion.objects.get()
    assert rule.demonstration and rule.number == 1
    preview_data = {"action": "preview", "rule": rule.pk}
    response = client.post(evaluation_url, preview_data)
    findings = response.context["result"]
    token = response.context["preview_token"]
    assert findings["sufficiency"] == "sufficient"
    assert findings["performance"] == "undetermined"
    assert [criterion["count"] for criterion in findings["criteria"]] == [1, 2, 1]
    assert [(row["number"], row["count"], row["pending"]) for row in findings["coverage"]] == [
        (1, 1, 1),
        (2, 1, 1),
        (3, 0, 1),
    ]
    assert "Cakupan persyaratan baseline" in response.content.decode()
    assert not EvidenceEvaluation.objects.exists()
    record_data = {**preview_data, "action": "record"}
    assert client.post(evaluation_url, record_data).status_code == 409
    assert not EvidenceEvaluation.objects.exists()
    assert client.post(evaluation_url, {**record_data, "preview_token": token}).status_code == 302
    evaluation = EvidenceEvaluation.objects.get()
    assert set(evaluation.evidence.all()) == {auto, ambiguous}
    assert evaluation.created_by == reviewer
    assert client.post(evaluation_url, {**rule_data, "minimum_attempts": 2}).status_code == 302
    assert EvaluationRuleVersion.objects.get(number=2).minimum_attempts == 2
    dated_rule_data = {**rule_data, "minimum_sources": 2, "maximum_age_days": 14}
    assert client.post(evaluation_url, dated_rule_data).status_code == 302
    dated_rule = EvaluationRuleVersion.objects.get(number=3)
    dated_preview = {**preview_data, "rule": dated_rule.pk}
    with patch("apps.adaptive.services.timezone") as clock:
        clock.localdate.return_value = event.occurred_on + timedelta(days=14)
        response = client.post(evaluation_url, dated_preview)
        findings = response.context["result"]
        assert findings["criteria"][-1] == {"label": "Sumber unik", "count": 1, "minimum": 2}
        assert not findings["excluded_by_age"]
        assert "SIM-PAGI" in response.content.decode()

        clock.localdate.return_value += timedelta(days=1)
        findings = client.post(evaluation_url, dated_preview).context["result"]
        assert findings["sufficiency"] == "insufficient"
        assert findings["performance"] == "undetermined"
        assert not findings["evidence"]
        assert {row["record"] for row in findings["excluded_by_age"]} == {
            auto.pk,
            ambiguous.pk,
            absent_context.pk,
        }
    assert client.post(verification_url(ambiguous.pk), cancel).status_code == 302
    client.force_login(student)
    history = client.get(reflection_detail)
    assert "SIM-SORE" in history.content.decode()
    summary = history.context["evidence_summary"]
    assert summary.eligible_count == 0 and summary.attempt_count == 0
    assert summary.rows[0].reference == "SIM-SORE" and not summary.rows[0].eligible
    assert "Tidak lagi layak" in history.content.decode()
    assert ambiguous not in history.context["form"].fields["evidence"].queryset
    assert (
        client.post(
            reflection_detail,
            {
                "revision": 2,
                "body": "Draf refleksi",
                "evidence": [ambiguous.pk],
            },
        ).status_code
        == 200
    )
    client.force_login(reviewer)
    stale = client.post(evaluation_url, {**record_data, "preview_token": token})
    assert stale.status_code == 409
    assert stale.context["result"]["sufficiency"] == "review"
    assert stale.context["result"]["coverage"][1]["count"] == 0
    assert stale.context["preview_token"] != token
    assert EvidenceEvaluation.objects.count() == 1
    findings = client.post(evaluation_url, preview_data).context["result"]
    assert findings["sufficiency"] == "review"
    assert [criterion["count"] for criterion in findings["criteria"]] == [1, 1, 1]
    evaluation.refresh_from_db()
    assert evaluation.sufficiency == "sufficient"
    assert evaluation.snapshot["criteria"][1]["count"] == 2
    assert evaluation.snapshot["coverage"][1]["count"] == 1
    retirement = {"action": "retire", "rule": rule.pk, "reason": "Digantikan dalam simulasi."}
    assert client.post(evaluation_url, retirement).status_code == 403
    allow("add_evaluationruleretirement")
    assert client.post(evaluation_url, {**retirement, "reason": " "}).status_code == 200
    assert not EvaluationRuleRetirement.objects.exists()
    assert client.post(evaluation_url, retirement).status_code == 302
    assert client.post(evaluation_url, {**retirement, "reason": "Ulang"}).status_code == 302
    saved_retirement = EvaluationRuleRetirement.objects.get(rule=rule)
    assert saved_retirement.created_by == reviewer
    assert saved_retirement.reason == retirement["reason"]
    assert client.post(evaluation_url, preview_data).context["result"] is None
    assert client.post(evaluation_url, {**preview_data, "action": "record"}).status_code == 200
    assert EvidenceEvaluation.objects.count() == 1
    retired_page = client.get(evaluation_url).content.decode()
    assert "Digantikan dalam simulasi." in retired_page
    assert "SIM-SORE" in retired_page
    assert client.post(evaluation_url, dated_preview).context["result"] is not None
    assert EvidencePlacement.objects.filter(pk=placement.pk).exists()
    assert [count for _, count in client.get(reconcile_url).context["progress"]] == [1, 0, 0, 1]

    production_data = {**rule_data, "action": "new-production-rule", "minimum_contexts": 1}
    publish_permission = Permission.objects.get(codename="add_evaluationrulepublication")
    reviewer.user_permissions.add(publish_permission)
    assert client.post(evaluation_url, production_data).status_code == 403
    kaprodi = AccessRole.objects.create(
        name="Penanggung Jawab Akademik Prodi", scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    kaprodi.permissions.add(publish_permission)
    UserRoleAssignment.objects.create(
        account=reviewer, role=kaprodi, program=program, assigned_by=actor
    )
    assert client.post(evaluation_url, production_data).status_code == 302
    draft = EvaluationRuleVersion.objects.get(demonstration=False)
    production_preview = {**preview_data, "rule": draft.pk}
    assert client.post(evaluation_url, production_preview).context["result"] is None
    publish = {"action": "publish", "rule": draft.pk, "minimum_below": 1, "minimum_meets": 1}
    assert client.post(evaluation_url, {**publish, "rule": dated_rule.pk}).status_code == 200
    assert not EvaluationRulePublication.objects.exists()
    assert client.post(evaluation_url, publish).status_code == 302
    publication = EvaluationRulePublication.objects.get(rule=draft)
    assert publication.created_by == reviewer
    policy_url = reverse("academics:evidence:adaptive_policies", args=[program.pk])
    assert client.get(policy_url).status_code == 403
    allow("view_adaptivepolicyversion")
    assert client.get(policy_url).status_code == 200
    policy_data = {
        "rule_publication": publication.pk,
        "maximum_attempts": 3,
        "review_within_days": 7,
    }
    assert client.post(policy_url, policy_data).status_code == 403
    allow("add_adaptivepolicyversion", "add_adaptiveattemptoption")
    created_policy = client.post(policy_url, policy_data)
    assert created_policy.status_code == 302
    policy = AdaptivePolicyVersion.objects.get()
    detail = created_policy.headers["Location"]
    assert policy.number == 1 and policy.created_by == reviewer
    assert client.post(policy_url, {**policy_data, "maximum_attempts": 0}).status_code == 302
    assert AdaptivePolicyVersion.objects.get(number=2).maximum_attempts == 0
    wrong_program = reverse("academics:evidence:adaptive_policy", args=[foreign.pk, policy.pk])
    assert client.get(wrong_program).status_code == 404
    item.blueprintitemcompetency_set.create(competency=target, created_by=actor)
    sampling = item.assessmentsamplingrule_set.create(
        context="Rawat pagi",
        minimum_observations=1,
        created_by=actor,
    )
    option_data = {
        "sampling": sampling.pk,
        "source_link": link.pk,
        "priority": 1,
        "maximum_per_option": 2,
        "adds_attempt": "on",
        "adds_context": "on",
    }
    assert client.post(detail, {**option_data, "source_link": foreign_link.pk}).status_code == 200
    assert not AdaptiveAttemptOption.objects.exists()
    assert client.post(detail, option_data).status_code == 302
    assert client.post(detail, option_data).status_code == 200
    option = AdaptiveAttemptOption.objects.get()
    assert option.policy == policy and option.adds_attempt and option.adds_context
    assert "Rawat pagi" in client.get(detail).content.decode()
    kaprodi.permissions.remove(publish_permission)
    assert client.post(detail, {"action": "publish"}).status_code == 403
    kaprodi.permissions.add(publish_permission)
    assert client.post(detail, {"action": "publish"}).status_code == 302
    assert AdaptivePolicyPublication.objects.get(policy=policy).created_by == reviewer
    assert client.post(detail, option_data).status_code == 200
    assert AdaptiveAttemptOption.objects.filter(policy=policy).count() == 1
    future_event = AssessmentEvent.objects.create(
        component=item,
        name="Slot sintetis pekan depan",
        occurred_on=timezone.localdate() + timedelta(days=7),
        created_by=actor,
    )
    slot_data = {
        "action": "confirm-slot",
        "option": option.pk,
        "event": future_event.pk,
        "capacity": 1,
    }
    assert client.post(detail, slot_data).status_code == 403
    allow("add_confirmedattemptslot")
    assert client.post(evaluation_url, production_preview).context["result"]["performance"] == (
        "undetermined"
    )

    allow("add_assessorfindingassignment", "add_assessorfinding")
    assignment_data = {
        "action": "assign-finding",
        "record": auto.pk,
        "standard": standard_version.pk,
        "assessor": reviewer.pk,
    }
    assert (
        client.post(evaluation_url, {**assignment_data, "record": ambiguous.pk}).status_code == 200
    )
    assert not AssessorFindingAssignment.objects.exists()
    assert client.post(evaluation_url, assignment_data).status_code == 302
    assignment = AssessorFindingAssignment.objects.get()
    finding_data = {
        "action": "submit-finding",
        "assignment": assignment.pk,
        "outcome": "below",
        "rationale": "Temuan asesor sintetis.",
    }
    client.force_login(actor)
    response = client.post(evaluation_url, finding_data)
    assert response.status_code in {200, 403}
    assert not AssessorFinding.objects.exists()
    assessor_url = reverse("assessor_assignments")
    assert "SIM-PAGI" not in client.get(assessor_url).content.decode()
    client.force_login(reviewer)
    assert "SIM-PAGI" in client.get(assessor_url).content.decode()
    assert client.post(assessor_url, finding_data).status_code == 302
    assert client.post(evaluation_url, finding_data).status_code == 200
    response = client.post(evaluation_url, production_preview)
    assert response.context["result"]["performance"] == "open"
    assert (
        response.context["result"]["assessor_findings"][0]["id"] == AssessorFinding.objects.get().pk
    )
    assert (
        client.post(
            evaluation_url,
            {
                **production_preview,
                "action": "record",
                "preview_token": response.context["preview_token"],
            },
        ).status_code
        == 302
    )
    production_evaluation = EvidenceEvaluation.objects.get(rule=draft)
    assert production_evaluation.performance == "open"
    intervention_url = reverse("intervention_drafts", args=[advisor_assignment.pk])
    assert client.get(intervention_url).status_code == 404
    advisor_role.permissions.add(Permission.objects.get(codename="add_interventiondraft"))
    draft_data = {
        "evaluation": production_evaluation.pk,
        "activity": "Latihan terarah",
        "rationale": "Kesenjangan terbuka",
        "expected_outcome": "Komunikasi lebih runtut",
    }
    assert client.post(intervention_url, draft_data).status_code == 302
    assert client.get(intervention_url).context["drafts"].get().activity == "Latihan terarah"
    pending_draft = client.get(intervention_url).context["drafts"].get()
    approval_url = reverse("intervention_approvals", args=[program.pk, baseline.pk])
    advisor_role.permissions.add(Permission.objects.get(codename="add_interventionapproval"))
    assert client.post(approval_url, {"draft": pending_draft.pk}).status_code == 403
    kaprodi.permissions.add(Permission.objects.get(codename="add_interventionapproval"))
    assert client.post(approval_url, {"draft": pending_draft.pk}).status_code == 302
    assert client.post(approval_url, {"draft": pending_draft.pk}).status_code == 302
    client.force_login(student)
    approval = client.get(learning_url).context["approved_interventions"].get()
    assert approval.draft == pending_draft
    report_url = reverse("intervention_completion_report", args=[enrollment.pk, approval.pk])
    assert client.post(report_url).status_code == 404
    completion_permission = Permission.objects.get(codename="add_interventioncompletionreport")
    student_role.permissions.add(completion_permission)
    assert client.get(report_url).status_code == 405
    wrong_enrollment_url = reverse(
        "intervention_completion_report", args=[enrollment.pk + 1, approval.pk]
    )
    assert client.post(wrong_enrollment_url).status_code == 404
    assert "Laporkan selesai" in client.get(learning_url).content.decode()
    assert client.post(report_url).status_code == 302
    assert client.post(report_url).status_code == 302
    approval.refresh_from_db()
    assert approval.interventioncompletionreport.reported_by == student
    assert "Dilaporkan selesai" in client.get(learning_url).content.decode()
    advisor_role.permissions.add(completion_permission)
    client.force_login(reviewer)
    assert client.post(report_url).status_code == 404
    assert (
        client.post(intervention_url, {**draft_data, "activity": "Draf kedua"}).status_code == 302
    )
    second_draft = client.get(intervention_url).context["drafts"].get(activity="Draf kedua")
    assert client.get(evaluation_url).context["intervention_evaluations"] == {
        production_evaluation.pk
    }
    assert production_evaluation.snapshot["publication"] == publication.pk
    finding_correction = {
        "action": "revise-finding",
        "finding": AssessorFinding.objects.get().pk,
        "previous_number": 1,
        "outcome": "meets",
        "rationale": "Temuan koreksi sintetis.",
        "reason": "Koreksi pencatatan.",
    }
    assert client.post(evaluation_url, {**finding_correction, "reason": " "}).status_code == 200
    assert not AssessorFindingRevision.objects.exists()
    assert client.post(evaluation_url, finding_correction).status_code == 302
    assert client.post(evaluation_url, finding_correction).status_code == 200
    revision = AssessorFindingRevision.objects.get()
    assert revision.number == 2
    assert revision.finding.outcome == "below"
    corrected = client.post(evaluation_url, production_preview).context["result"]
    assert corrected["performance"] == "closed"
    assert corrected["assessor_findings"][0]["revision_id"] == revision.pk
    assert corrected["assessor_findings"][0]["revision_reason"] == finding_correction["reason"]
    reevaluation = EvidenceEvaluation.objects.get(
        rule=draft, trigger=EvidenceEvaluation.Trigger.FINDING_CORRECTION
    )
    assert reevaluation.trigger_record == auto and reevaluation.created_by == reviewer
    assert reevaluation.performance == "closed"
    assert reevaluation.snapshot == corrected
    assert EvidenceEvaluation.objects.filter(rule=draft).count() == 2
    production_evaluation.refresh_from_db()
    stale_intervention = client.post(intervention_url, draft_data)
    assert stale_intervention.status_code == 200
    assert "evaluation" in stale_intervention.context["form"].errors
    assert stale_intervention.context["drafts"].count() == 2
    assert client.post(approval_url, {"draft": second_draft.pk}).status_code == 409
    assert client.get(evaluation_url).context["intervention_evaluations"] == set()
    assert production_evaluation.snapshot["assessor_findings"][0]["outcome"] == "below"
    assert production_evaluation.snapshot["assessor_findings"][0]["revision_number"] == 1
    html = client.get(evaluation_url).content.decode()
    assert "Versi 2" in html
    assert "Temuan koreksi sintetis." in html
    assert client.post(verification_url(auto.pk), cancel).status_code == 302
    invalidated_evaluation = EvidenceEvaluation.objects.get(
        rule=draft, trigger=EvidenceEvaluation.Trigger.INVALIDATION
    )
    assert invalidated_evaluation.trigger_record == auto
    assert invalidated_evaluation.performance == "undetermined"
    assert not invalidated_evaluation.evidence.exists()
    assert client.post(verification_url(auto.pk), cancel).status_code == 409
    assert EvidenceEvaluation.objects.filter(rule=draft).count() == 3
    assert client.post(verification_url(absent_context.pk), cancel).status_code == 302
    prior = EvidenceEvaluation.objects.filter(rule=draft).first()
    assert prior is not None and prior.sufficiency == "insufficient"
    preview_url = reverse(
        "academics:evidence:adaptive_policy_preview", args=[program.pk, enrollment.pk, prior.pk]
    )
    assert preview_url in client.get(evaluation_url).content.decode()
    assert not client.get(preview_url, {"policy": policy.pk}).context["proposal"].additional
    assert client.post(detail, {**slot_data, "event": event.pk}).status_code == 200
    assert not ConfirmedAttemptSlot.objects.exists()
    assert client.post(detail, slot_data).status_code == 302
    assert client.post(detail, slot_data).status_code == 302
    assert ConfirmedAttemptSlot.objects.count() == 1
    proposed = client.get(preview_url, {"policy": policy.pk})
    assert proposed.status_code == 200
    assert "Slot sintetis pekan depan" in proposed.content.decode()
    assert len(proposed.context["proposal"].additional) == 1
    assert proposed.context["proposal"].remaining == {"Verifikator unik": 1}
    reserve_data = {"policy": policy.pk, "slot": ConfirmedAttemptSlot.objects.get().pk}
    assert client.post(preview_url, reserve_data).status_code == 403
    allow("add_attemptreservation")
    assert client.post(preview_url, {**reserve_data, "slot": 999999}).status_code == 409
    assert client.post(preview_url, reserve_data).status_code == 302
    assert client.post(preview_url, reserve_data).status_code == 302
    booking = AttemptReservation.objects.get()
    assert booking.evaluation == prior and booking.event == future_event
    assert booking.created_by == reviewer
    assert booking.gap_targets == ["Konteks unik", "Percobaan unik"]
    after_booking = client.get(preview_url, {"policy": policy.pk})
    assert after_booking.context["proposal"].keep == ("Slot sintetis pekan depan",)
    assert after_booking.context["proposal"].remaining == {"Verifikator unik": 1}
    second_learner = Learner.objects.create(account=User.objects.create_user(username="kandidat"))
    second_enrollment = enrollment.cohort.enrollments.create(
        learner=second_learner, enrolled_on=enrollment.enrolled_on, created_by=actor
    )
    second_baseline, _ = LearnerEvidenceBaseline.objects.get_or_create(
        enrollment=second_enrollment,
        defaults={"publication": baseline.publication, "created_by": actor},
    )
    second_evaluation = EvidenceEvaluation.objects.create(
        baseline=second_baseline,
        rule=draft,
        sufficiency=prior.sufficiency,
        performance=prior.performance,
        snapshot=prior.snapshot,
        engine_version=prior.engine_version,
        created_by=reviewer,
    )
    second_preview = reverse(
        "academics:evidence:adaptive_policy_preview",
        args=[program.pk, second_enrollment.pk, second_evaluation.pk],
    )
    assert client.post(second_preview, reserve_data).status_code == 409
    assert AttemptReservation.objects.count() == 1
    release_data = {
        "action": "release",
        "policy": policy.pk,
        "reservation": booking.pk,
        "reason": "Jadwal kebutuhan berubah.",
    }
    assert client.post(preview_url, release_data).status_code == 403
    allow("release_attemptreservation")
    assert client.post(preview_url, {**release_data, "reason": " "}).status_code == 409
    assert client.post(second_preview, release_data).status_code == 404
    assert client.post(preview_url, release_data).status_code == 302
    assert client.post(preview_url, {**release_data, "reason": "Ulang"}).status_code == 302
    booking.refresh_from_db()
    assert booking.released_at and booking.released_by == reviewer
    assert booking.release_reason == release_data["reason"]
    assert (
        "Jadwal kebutuhan berubah."
        in client.get(preview_url, {"policy": policy.pk}).content.decode()
    )
    assert client.post(second_preview, reserve_data).status_code == 302
    second_booking = AttemptReservation.objects.get(baseline=second_baseline)
    scheduled_data = {
        "action": "schedule-assessor",
        "policy": policy.pk,
        "reservation": second_booking.pk,
        "assessor": reviewer.pk,
        "reason": "Asesor untuk pelaksanaan sintetis.",
    }
    assert client.post(second_preview, scheduled_data).status_code == 403
    allow("add_scheduledassessorassignment")
    assert (
        client.post(
            second_preview, {**scheduled_data, "assessor": second_learner.account_id}
        ).status_code
        == 409
    )
    assert client.post(second_preview, scheduled_data).status_code == 302
    assert client.post(second_preview, scheduled_data).status_code == 302
    assignment = ScheduledAssessorAssignment.objects.get(reservation=second_booking)
    assert assignment.assessor == reviewer and assignment.assigned_by == reviewer
    assert "Slot sintetis pekan depan" in client.get(assessor_url).content.decode()
    stale_assignment = {**scheduled_data, "assessor": actor.pk, "reason": "Asesor berganti."}
    assert client.post(second_preview, stale_assignment).status_code == 409
    assert (
        client.post(second_preview, {**stale_assignment, "previous": assignment.pk}).status_code
        == 302
    )
    assert ScheduledAssessorAssignment.objects.filter(reservation=second_booking).count() == 2
    assert "Slot sintetis pekan depan" not in client.get(assessor_url).content.decode()
    client.force_login(actor)
    assert "Slot sintetis pekan depan" in client.get(assessor_url).content.decode()
    client.force_login(reviewer)
    participation = AssessmentParticipation.objects.create(
        event=future_event, enrollment=second_enrollment
    )
    actual_attempt = AssessmentAttempt.objects.create(
        participation=participation, number=1, created_by=actor
    )
    assert client.post(second_preview, scheduled_data).status_code == 409
    assert ScheduledAssessorAssignment.objects.filter(reservation=second_booking).count() == 2
    link_data = {
        "action": "link-attempt",
        "policy": policy.pk,
        "reservation": second_booking.pk,
        "attempt": actual_attempt.pk,
    }
    assert client.post(second_preview, link_data).status_code == 403
    allow("link_attemptreservation")
    assert client.post(second_preview, {**link_data, "attempt": first.pk}).status_code == 409
    assert client.post(preview_url, link_data).status_code == 404
    assert (
        "Percobaan tercatat" in client.get(second_preview, {"policy": policy.pk}).content.decode()
    )
    attempt_count = AssessmentAttempt.objects.count()
    assert client.post(second_preview, link_data).status_code == 302
    second_booking.refresh_from_db()
    linked_at = second_booking.linked_at
    assert second_booking.attempt == actual_attempt and second_booking.linked_by == reviewer
    assert linked_at is not None
    assert client.post(second_preview, link_data).status_code == 302
    second_booking.refresh_from_db()
    assert second_booking.linked_at == linked_at
    assert AssessmentAttempt.objects.count() == attempt_count
    assert (
        "Percobaan 1 ditautkan"
        in client.get(second_preview, {"policy": policy.pk}).content.decode()
    )
    assert (
        client.post(second_preview, {**release_data, "reservation": second_booking.pk}).status_code
        == 409
    )
    second_booking.refresh_from_db()
    assert second_booking.released_at is None
    assert EvidenceEvaluation.objects.filter(rule=draft, baseline=baseline).count() == 4
    assert second_booking.fulfillment_checks.get().supporting_record is None
    assert (
        "Menunggu bukti yang memenuhi syarat"
        not in client.get(second_preview, {"policy": policy.pk}).content.decode()
    )
    allow("view_attemptfulfillmentcheck")
    assert (
        "Menunggu bukti yang memenuhi syarat"
        in client.get(second_preview, {"policy": policy.pk}).content.decode()
    )

    def verify_adaptive_record(record: EvidenceRecord) -> str:
        url = reverse(
            "academics:assessments:verify_evidence",
            args=[program.pk, future_event.pk, actual_attempt.pk, record.pk],
        )
        assert client.post(url, decision).status_code == 302
        return url

    mismatched = EvidenceRecord.objects.create(
        attempt=actual_attempt,
        source_link=link,
        reference="KONTEKS-LAIN",
        context="Rawat sore",
        created_by=actor,
    )
    verify_adaptive_record(mismatched)
    assert second_booking.fulfillment_checks.count() == 1
    matched = EvidenceRecord.objects.create(
        attempt=actual_attempt,
        source_link=link,
        reference="BUKTI-PERC0BAAN-TAMBAHAN",
        context=" rawat PAGI ",
        created_by=actor,
    )
    matched_url = verify_adaptive_record(matched)
    checks = AttemptFulfillmentCheck.objects.filter(reservation=second_booking)
    assert checks.first().supporting_record == matched
    assert checks.first().trigger_record == matched
    assert checks.count() == 2
    assert "Terpenuhi" in client.get(second_preview, {"policy": policy.pk}).content.decode()
    assert client.post(matched_url, cancel).status_code == 302
    assert checks.count() == 3
    assert checks.first().supporting_record is None
    assert checks.filter(supporting_record=matched).exists()

    extra_event = AssessmentEvent.objects.create(
        component=item,
        name="Slot yang akan dilepas",
        occurred_on=timezone.localdate() + timedelta(days=8),
        created_by=actor,
    )
    assert client.post(detail, {**slot_data, "event": extra_event.pk}).status_code == 302
    extra_slot = ConfirmedAttemptSlot.objects.get(event=extra_event)
    assert (
        client.post(
            preview_url,
            {"policy": policy.pk, "slot": extra_slot.pk},
        ).status_code
        == 302
    )
    pending_booking = AttemptReservation.objects.get(baseline=baseline, event=extra_event)
    protected_event = AssessmentEvent.objects.create(
        component=item,
        name="Slot dengan partisipasi",
        occurred_on=timezone.localdate() + timedelta(days=9),
        created_by=actor,
    )
    protected_slot = ConfirmedAttemptSlot.objects.create(
        option=option,
        event=protected_event,
        capacity=1,
        created_by=reviewer,
    )
    protected_booking = AttemptReservation.objects.create(
        baseline=baseline,
        evaluation=prior,
        event=protected_event,
        slot=protected_slot,
        gap_targets=["Percobaan unik"],
        created_by=reviewer,
    )
    AssessmentParticipation.objects.create(event=protected_event, enrollment=enrollment)
    new_evidence = EvidenceRecord.objects.create(
        attempt=first,
        source_link=link,
        reference="BUKTI-CUKUP-UNTUK-INTERVENSI",
        context="Rawat pagi",
        created_by=actor,
    )
    assert client.post(verification_url(new_evidence.pk), decision).status_code == 302
    pending_booking.refresh_from_db()
    assert pending_booking.released_at is None
    assert (
        client.post(
            evaluation_url,
            {**assignment_data, "record": new_evidence.pk},
        ).status_code
        == 302
    )
    new_assignment = AssessorFindingAssignment.objects.get(record=new_evidence)
    assert (
        client.post(
            assessor_url,
            {**finding_data, "assignment": new_assignment.pk},
        ).status_code
        == 302
    )
    pending_booking.refresh_from_db()
    protected_booking.refresh_from_db()
    assert pending_booking.released_at and pending_booking.released_by == reviewer
    release_evaluation = pending_booking.release_evaluation
    assert release_evaluation is not None
    assert (
        release_evaluation.sufficiency == "sufficient" and release_evaluation.performance == "open"
    )
    assert release_evaluation.trigger == EvidenceEvaluation.Trigger.FINDING
    assert protected_booking.released_at is None
    assert "Dilepas otomatis" in client.get(preview_url, {"policy": policy.pk}).content.decode()
    # Simulate outstanding needs from a prior evaluation with broader gaps.
    pending_by_target = {}
    for days, gap in ((10, "Konteks unik"), (11, "Percobaan unik")):
        scheduled_event = AssessmentEvent.objects.create(
            component=item,
            name=gap,
            occurred_on=timezone.localdate() + timedelta(days=days),
            created_by=actor,
        )
        confirmed_slot = ConfirmedAttemptSlot.objects.create(
            option=option,
            event=scheduled_event,
            capacity=1,
            created_by=reviewer,
        )
        pending_by_target[gap] = AttemptReservation.objects.create(
            baseline=baseline,
            evaluation=prior,
            event=scheduled_event,
            slot=confirmed_slot,
            gap_targets=[gap],
            created_by=reviewer,
        )
    strict_rule = EvaluationRuleVersion.objects.create(
        standard=standard_version,
        number=draft.number + 1,
        demonstration=False,
        minimum_attempts=2,
        minimum_contexts=1,
        minimum_verifiers=1,
        created_by=reviewer,
    )
    EvaluationRulePublication.objects.create(
        rule=strict_rule,
        minimum_below=1,
        minimum_meets=1,
        created_by=reviewer,
    )
    strict_preview = {**production_preview, "rule": strict_rule.pk}
    strict_response = client.post(evaluation_url, strict_preview)
    assert strict_response.context["result"]["sufficiency"] == "insufficient"
    assert (
        client.post(
            evaluation_url,
            {
                **strict_preview,
                "action": "record",
                "preview_token": strict_response.context["preview_token"],
            },
        ).status_code
        == 302
    )
    redundant = pending_by_target["Konteks unik"]
    still_needed = pending_by_target["Percobaan unik"]
    redundant.refresh_from_db()
    still_needed.refresh_from_db()
    assert redundant.release_evaluation.rule == strict_rule
    assert "berlebih" in redundant.release_reason
    assert still_needed.released_at is None
    protected_booking.refresh_from_db()
    assert protected_booking.released_at is None
    auto_rule = EvaluationRuleVersion.objects.create(
        standard=standard_version,
        number=strict_rule.number + 1,
        demonstration=False,
        minimum_attempts=3,
        minimum_contexts=1,
        minimum_verifiers=1,
        created_by=reviewer,
    )
    auto_publication = EvaluationRulePublication.objects.create(
        rule=auto_rule,
        minimum_below=1,
        minimum_meets=1,
        created_by=reviewer,
    )
    auto_policy_response = client.post(
        policy_url,
        {**policy_data, "rule_publication": auto_publication.pk, "maximum_attempts": 4},
    )
    assert auto_policy_response.status_code == 302
    auto_detail = auto_policy_response.headers["Location"]
    auto_policy = AdaptivePolicyVersion.objects.get(rule_publication=auto_publication)
    assert client.post(auto_detail, option_data).status_code == 302
    assert (
        client.post(auto_detail, {"action": "publish", "automatic_reservations": "on"}).status_code
        == 302
    )
    assert AdaptivePolicyPublication.objects.get(policy=auto_policy).automatic_reservations
    auto_payload = {**production_preview, "rule": auto_rule.pk}
    auto_result = client.post(evaluation_url, auto_payload)
    confirmation = {
        **auto_payload,
        "action": "record",
        "preview_token": auto_result.context["preview_token"],
    }
    assert client.post(evaluation_url, confirmation).status_code == 302
    assert not AttemptReservation.objects.filter(automatic=True).exists()
    case = AdaptiveEscalation.objects.get(baseline=baseline, closed_at__isnull=True)
    assert case.remaining == {"Percobaan unik": 1}
    assert case.due_on == timezone.localdate() + timedelta(days=auto_policy.review_within_days)
    escalation_url = reverse(
        "academics:evidence:adaptive_policy_preview",
        args=[program.pk, enrollment.pk, case.latest_evaluation_id],
    )
    review = {
        "policy": auto_policy.pk,
        "action": "review-escalation",
        "escalation": case.pk,
        "note": "Menunggu slot yang dikonfirmasi.",
    }
    assert client.post(escalation_url, review).status_code == 403
    queue = reverse("academics:evidence:adaptive_escalation_queue", args=[program.pk])
    assert client.get(queue).status_code == 403
    allow("view_adaptiveescalation", "change_adaptiveescalation")
    assert client.get(queue).context["page"].object_list[0] == case
    assert f"#eskalasi-{case.pk}" in client.get(queue).content.decode()
    assert not client.get(queue, {"status": "overdue"}).context["page"].object_list
    yesterday = timezone.localdate() - timedelta(days=1)
    AdaptiveEscalation.objects.filter(pk=case.pk).update(due_on=yesterday)
    assert client.get(queue, {"status": "overdue"}).context["totals"]["overdue"] == 1
    assert client.get(policy_url).context["escalation_reminders"] == 1
    foreign_queue = reverse("academics:evidence:adaptive_escalation_queue", args=[foreign.pk])
    foreign_response = client.get(foreign_queue)
    if foreign_response.status_code == 200:
        assert not foreign_response.context["page"].object_list
    else:
        assert foreign_response.status_code in (403, 404)
    assert client.post(escalation_url, review).status_code == 302
    case.refresh_from_db()
    assert case.reviewed_by == reviewer and case.closed_at is None
    auto_event = AssessmentEvent.objects.create(
        component=item,
        name="Slot terkonfirmasi untuk reservasi otomatis",
        occurred_on=timezone.localdate() + timedelta(days=12),
        created_by=actor,
    )
    auto_option = auto_policy.options.get()
    assert (
        client.post(
            auto_detail,
            {
                **slot_data,
                "option": auto_option.pk,
                "event": auto_event.pk,
            },
        ).status_code
        == 302
    )
    assert client.post(evaluation_url, confirmation).status_code == 302
    generated = AttemptReservation.objects.get(automatic=True)
    case.refresh_from_db()
    assert case.closed_at is not None
    assert not client.get(queue).context["page"].object_list
    assert client.get(queue, {"status": "closed"}).context["page"].object_list[0] == case
    assert client.get(policy_url).context["escalation_reminders"] == 0
    assert case.latest_evaluation == generated.evaluation
    assert AdaptiveEscalation.objects.filter(baseline=baseline).count() == 1
    assert generated.event == auto_event and generated.baseline == baseline
    assert generated.evaluation.rule == auto_rule and generated.gap_targets == ["Percobaan unik"]
    assert client.post(evaluation_url, confirmation).status_code == 302
    assert AttemptReservation.objects.filter(automatic=True).count() == 1
    report = approval.interventioncompletionreport
    verify_completion_url = reverse(
        "verify_intervention_completion", args=[advisor_assignment.pk, report.pk]
    )
    assert client.post(verify_completion_url).status_code == 404
    advisor_role.permissions.add(Permission.objects.get(codename="add_reassessmentrequirement"))
    client.force_login(actor)
    assert client.post(verify_completion_url).status_code == 404
    client.force_login(reviewer)
    assert "Verifikasi pelaksanaan" in client.get(intervention_url).content.decode()
    assert client.get(verify_completion_url).status_code == 405
    assert client.post(verify_completion_url).status_code == 302
    assert client.post(verify_completion_url).status_code == 302
    requirement = ReassessmentRequirement.objects.get(completion=report)
    assert requirement.verified_assignment == advisor_assignment
    client.force_login(student)
    assert "Kebutuhan tercatat" in client.get(learning_url).content.decode()
    client.force_login(reviewer)
    cutoff = timezone.localdate(report.reported_at)

    def reassessment_evidence(occurred_on, name):
        assessment = AssessmentEvent.objects.create(
            component=event.component, occurred_on=occurred_on, name=name, created_by=actor
        )
        participation = AssessmentParticipation.objects.create(
            event=assessment, enrollment=enrollment
        )
        attempt = AssessmentAttempt.objects.create(
            participation=participation, number=1, created_by=actor
        )
        record = EvidenceRecord.objects.create(
            attempt=attempt,
            source_link=link,
            context="Rawat pagi",
            reference=name,
            created_by=actor,
        )
        EvidenceVerification.objects.create(
            record=record,
            status=EvidenceVerification.Status.VERIFIED,
            reason="Bukti sintetis",
            created_by=reviewer,
        )
        assessor = AssessorFindingAssignment.objects.create(
            record=record,
            standard=draft.standard,
            assessor=reviewer,
            created_by=actor,
        )
        AssessorFinding.objects.create(assignment=assessor, outcome="meets", rationale=name)
        return record

    historical = reassessment_evidence(cutoff, "Bukti pada tanggal laporan")
    pending = client.post(evaluation_url, production_preview).context["result"]
    assert pending["reassessment"] == requirement.pk
    assert pending["performance"] == "undetermined"
    assert historical.pk in {row["record"] for row in pending["historical_evidence"]}

    next_day = cutoff + timedelta(days=1)
    fresh = reassessment_evidence(next_day, "Bukti setelah intervensi")
    with patch(
        "apps.adaptive.services.timezone.localdate",
        side_effect=lambda value=None: next_day if value is None else value.date(),
    ):
        reassessed = client.post(evaluation_url, production_preview).context["result"]
    assert reassessed["performance"] == "closed"
    assert {row["record"] for row in reassessed["evidence"]} == {fresh.pk}
    assert production_evaluation.snapshot["performance"] == "open"
    review = client.get(review_url)
    assert production_evaluation in review.context["history"].object_list
    assert all(not row.rule.demonstration for row in review.context["history"].object_list)
    assert generated in review.context["reservations"]
    assert approval in review.context["interventions"]
    assert "kebutuhan asesmen ulang tercatat" in review.content.decode()
    kaprodi.permissions.remove(Permission.objects.get(codename="add_interventionapproval"))
    assert not client.get(review_url).context["interventions"]
    client.force_login(student)
    assert client.get(review_url).status_code == 403
    client.force_login(reviewer)
    baseline_count = EvidenceEvaluation.objects.filter(rule=draft, baseline=baseline).count()

    retirement_data = {
        "action": "retire-production",
        "rule": draft.pk,
        "reason": "Versi produksi diganti.",
    }
    kaprodi.permissions.remove(publish_permission)
    assert client.post(evaluation_url, retirement_data).status_code == 403
    assert not EvaluationRuleRetirement.objects.filter(rule=draft).exists()
    kaprodi.permissions.add(publish_permission)
    assert client.post(evaluation_url, {**retirement_data, "action": "retire"}).status_code == 200
    assert client.post(evaluation_url, {**retirement_data, "reason": " "}).status_code == 200
    assert not EvaluationRuleRetirement.objects.filter(rule=draft).exists()
    assert client.post(evaluation_url, retirement_data).status_code == 302
    assert client.post(evaluation_url, {**retirement_data, "reason": "Ulang"}).status_code == 302
    stopped = EvaluationRuleRetirement.objects.get(rule=draft)
    assert stopped.created_by == reviewer
    assert stopped.reason == retirement_data["reason"]
    assert client.post(evaluation_url, production_preview).context["result"] is None
    assert (
        client.post(
            evaluation_url,
            {
                **production_preview,
                "action": "record",
                "preview_token": response.context["preview_token"],
            },
        ).status_code
        == 200
    )
    assert (
        EvidenceEvaluation.objects.filter(rule=draft, baseline=baseline).count() == baseline_count
    )
    page = client.get(evaluation_url).content.decode()
    assert stopped.reason in page
    retired_preview = client.get(preview_url, {"policy": policy.pk})
    assert "Riwayat reservasi tetap tersedia." in retired_preview.content.decode()
    assert "Jadwal kebutuhan berubah." in retired_preview.content.decode()
    assert "Temuan asesor sintetis." in page

    import_url = reverse(
        "academics:assessments:import_evidence", args=[program.pk, event.pk, first.pk]
    )
    other_attempt_url = reverse(
        "academics:assessments:import_evidence", args=[program.pk, event.pk, second.pk]
    )
    header = "kode_sumber,kode_jenis_bukti,referensi,konteks\n"

    def upload(body: str, *, columns: str = header):
        return client.post(
            import_url,
            {
                "action": "preview",
                "file": SimpleUploadedFile("bukti.csv", (columns + body).encode("utf-8-sig")),
            },
        )

    client.force_login(actor)
    assert import_url in client.get(evidence_url).content.decode()
    bad_header = upload("observasi,catatan,REF-A,Rawat pagi\n", columns="kode,nama\n")
    assert "Kepala CSV harus sesuai" in bad_header.content.decode()
    invalid = upload("observasi,catatan,REF-A,Rawat pagi\nluar,catatan,REF-X,\n")
    assert not invalid.context["token"]
    assert "tidak tertaut ke komponen" in invalid.content.decode()
    assert not EvidenceImportBatch.objects.exists()

    preview = upload(
        'observasi,catatan,REF-A,"Rawat pagi, sesi pertama"\n'
        'observasi,catatan,REF-A,"Rawat pagi, sesi pertama"\n'
        "observasi,catatan,REF-B,\n"
    )
    assert [row.status for row in preview.context["rows"]] == ["ready", "duplicate", "ready"]
    assert not EvidenceRecord.objects.filter(reference__in=["REF-A", "REF-B"]).exists()
    payload = {"action": "import", "preview_token": preview.context["token"]}
    assert client.post(other_attempt_url, payload).status_code == 400
    assert client.post(import_url, {**payload, "preview_token": "invalid"}).status_code == 400
    client.force_login(reviewer)
    assert client.post(import_url, payload).status_code == 400
    client.force_login(actor)
    result = client.post(import_url, payload)
    assert result.context["imported"] == 2 and result.context["skipped"] == 1
    batch = EvidenceImportBatch.objects.get()
    assert batch.created_by == actor and batch.attempt == first and len(batch.file_digest) == 64
    assert (batch.created_count, batch.skipped_count) == (2, 1)
    imported_record = EvidenceRecord.objects.get(reference="REF-A")
    assert imported_record.context == "Rawat pagi, sesi pertama"
    assert imported_record.import_batch == batch and imported_record.created_by == actor
    assert not EvidenceVerification.objects.filter(record=imported_record).exists()
    assert "Impor CSV" in client.get(verification_url(imported_record.pk)).content.decode()
    retry = client.post(import_url, payload)
    assert retry.context["imported"] == 0 and retry.context["skipped"] == 3
    assert EvidenceImportBatch.objects.count() == 1

    pending_batch = upload("observasi,catatan,REF-C,Rawat sore\nobservasi,catatan,REF-D,\n")
    assert pending_batch.context["token"]
    assert (
        client.post(
            evidence_url,
            {
                "source_link": link.pk,
                "reference": "REF-C",
                "context": "Konteks berbeda",
            },
        ).status_code
        == 302
    )
    conflict = client.post(
        import_url,
        {
            "action": "import",
            "preview_token": pending_batch.context["token"],
        },
    )
    assert "Referensi sudah ada dengan konteks berbeda." in conflict.content.decode()
    assert not EvidenceRecord.objects.filter(reference="REF-D").exists()
    assert EvidenceImportBatch.objects.count() == 1

    upload_url = reverse(
        "academics:assessments:upload_artifact",
        args=[program.pk, event.pk, first.pk, imported_record.pk],
    )
    pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"

    def upload_pdf(content: bytes = pdf, name: str = "simulasi.pdf"):
        return client.post(
            upload_url, {"file": SimpleUploadedFile(name, content, content_type="application/pdf")}
        )

    with override_settings(EVIDENCE_ARTIFACT_ROOT=tmp_path):
        assert upload_url in client.get(verification_url(imported_record.pk)).content.decode()
        assert upload_pdf(b"not a PDF").status_code == 400
        assert upload_pdf(name="simulasi.txt").status_code == 400
        assert not EvidenceArtifact.objects.exists()
        assert upload_pdf().headers["Location"] == verification_url(imported_record.pk)
        assert upload_pdf().status_code == 302
        artifact = EvidenceArtifact.objects.get(record=imported_record)
        assert artifact.created_by == actor and artifact.size_bytes == len(pdf)
        assert Path(artifact.file.path).is_relative_to(tmp_path)
        assert Path(artifact.file.path).read_bytes() == pdf
        with pytest.raises(NotImplementedError):
            _ = artifact.file.url
        download_url = reverse(
            "academics:assessments:download_artifact",
            args=[program.pk, event.pk, first.pk, imported_record.pk, artifact.pk],
        )
        assert download_url in client.get(verification_url(imported_record.pk)).content.decode()
        response = client.get(download_url)
        assert response.status_code == 200
        assert "attachment" in response["Content-Disposition"]
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Content-Type-Options"] == "nosniff"
        assert b"".join(response) == pdf
        mismatched = reverse(
            "academics:assessments:download_artifact",
            args=[program.pk, event.pk, first.pk, other_record.pk, artifact.pk],
        )
        assert client.get(mismatched).status_code == 404
        client.logout()
        assert client.get(download_url).status_code == 302
        client.force_login(actor)
        assert (
            client.post(
                verification_url(imported_record.pk),
                {
                    **correction,
                    "correction-reference": imported_record.reference,
                },
            ).status_code
            == 302
        )
        latest_import = EvidenceRecord.objects.get(supersedes=imported_record)
        assert not latest_import.artifacts.exists()
        assert upload_pdf().status_code == 409
        assert client.head(download_url).status_code == 200
        client.force_login(reviewer)
        assert client.post(verification_url(latest_import.pk), cancel).status_code == 302
        assert client.head(download_url).status_code == 200
        assert EvidenceArtifact.objects.filter(pk=artifact.pk, record=imported_record).exists()

    account = User.objects.create_user(
        username="sistem-eksternal",
        email="integrasi@example.test",
    )
    command_args = [
        account.email,
        program.code,
        link.capability.source.code,
    ]
    output = StringIO()
    call_command("configure_evidence_integration", *command_args, stdout=output)
    token = output.getvalue().strip()
    credential = EvidenceIntegration.objects.get(account=account)
    assert token.startswith("titeni_") and credential.token_digest != token
    with pytest.raises(CommandError, match="terikat pada sumber"):
        call_command(
            "configure_evidence_integration",
            account.email,
            foreign.code,
            foreign_link.capability.source.code,
            rotate=True,
            stdout=StringIO(),
        )

    endpoint = reverse("receive_external_evidence")
    api = Client(enforce_csrf_checks=True)
    api.force_login(actor)
    payload = {
        "external_id": "external-01",
        "attempt_id": first.pk,
        "evidence_type": link.capability.evidence_type.code,
        "reference": "REF-EXT-01",
        "context": "Rawat jalan",
    }

    def send(data, bearer: str = token):
        return api.post(
            endpoint,
            data,
            content_type="application/json",
            headers={"Authorization": f"Bearer {bearer}"},
        )

    assert api.post(endpoint, payload, content_type="application/json").status_code == 401
    assert send(payload, "invalid").status_code == 401
    assert send({**payload, "attempt_id": True}).status_code == 400
    assert send({**payload, "source": foreign_link.capability.source_id}).status_code == 400
    assert send({**payload, "context": "\ud800"}).status_code == 400
    assert send({**payload, "evidence_type": "jenis-lain"}).status_code == 422
    assert send({**payload, "reference": "REF-A"}).json()["error"] == "reference_conflict"
    foreign_event = AssessmentEvent.objects.create(
        component=foreign_item,
        name="Pelaksanaan lain",
        occurred_on=date(2026, 8, 1),
        created_by=actor,
    )
    foreign_participation = AssessmentParticipation.objects.create(
        event=foreign_event,
        enrollment=foreign_enrollment,
    )
    foreign_attempt = foreign_participation.attempts.create(number=1, created_by=actor)
    assert send({**payload, "attempt_id": foreign_attempt.pk}).status_code == 404
    assert not ExternalEvidenceReceipt.objects.exists()
    created = send(payload)
    assert created.status_code == 201
    receipt = ExternalEvidenceReceipt.objects.get()
    assert receipt.record_id == created.json()["record_id"]
    assert receipt.adapter_version == "v1" and receipt.integration == credential
    assert receipt.source == link.capability.source and receipt.record.created_by == account
    assert not EvidenceVerification.objects.filter(record=receipt.record).exists()
    retry = send(payload)
    assert retry.status_code == 200
    assert retry.json() == {**created.json(), "status": "duplicate"}
    assert send({**payload, "reference": "REF-CHANGED"}).json()["error"] == "external_id_conflict"
    assert send({**payload, "attempt_id": second.pk}).status_code == 409
    assert ExternalEvidenceReceipt.objects.count() == 1

    rotated = StringIO()
    call_command("configure_evidence_integration", *command_args, rotate=True, stdout=rotated)
    new_token = rotated.getvalue().strip()
    assert new_token != token and send(payload).status_code == 401
    assert send(payload, new_token).status_code == 200
    call_command("configure_evidence_integration", *command_args, disable=True, stdout=StringIO())
    assert send(payload, new_token).status_code == 401
    assert ExternalEvidenceReceipt.objects.count() == 1

    # BP-18 must use recorded production results and isolate each reviewer assignment.
    reassessment_evaluation = EvidenceEvaluation.objects.create(
        baseline=baseline,
        rule=draft,
        sufficiency=reassessed["sufficiency"],
        performance=reassessed["performance"],
        snapshot=reassessed,
        engine_version=production_evaluation.engine_version,
        created_by=reviewer,
    )
    progression_reviewer = User.objects.create_user(username="peninjau-progresi")
    progression_role = AccessRole.objects.create(
        name="Peninjau Progresi", scope=AccessRole.Scope.PROGRAM, updated_by=actor
    )
    progression_role.permissions.add(Permission.objects.get(codename="add_progressionreview"))
    UserRoleAssignment.objects.create(
        account=progression_reviewer, role=progression_role, program=program, assigned_by=actor
    )
    kaprodi.permissions.add(Permission.objects.get(codename="add_progressionreviewassignment"))
    assign_progression = reverse(
        "academics:assign_progression_review", args=[program.pk, enrollment.pk]
    )
    foreign_assignment = reverse(
        "academics:assign_progression_review", args=[program.pk, foreign_enrollment.pk]
    )
    reviewer_data = {"reviewer": progression_reviewer.pk}
    client.force_login(student)
    assert client.post(assign_progression, reviewer_data).status_code == 403
    client.force_login(reviewer)
    assert client.post(foreign_assignment, reviewer_data).status_code == 404
    assert client.post(assign_progression, reviewer_data).status_code == 302
    assert client.post(assign_progression, reviewer_data).status_code == 302
    progression = ProgressionReviewAssignment.objects.get()
    draft_url = reverse("progression_review_draft", args=[progression.pk])
    assert client.get(draft_url).status_code == 404
    client.force_login(progression_reviewer)
    assert draft_url in client.get(reverse("progression_review_queue")).content.decode()
    progression_page = client.get(draft_url)
    assert progression_page.status_code == 200
    assert "Hasil asesmen ulang" in progression_page.content.decode()
    assert reassessment_evaluation in progression_page.context["evaluations"]
    demonstration = EvidenceEvaluation.objects.filter(rule__demonstration=True).first()
    assert (
        demonstration is not None and demonstration not in progression_page.context["evaluations"]
    )
    assert not progression_page.context["decisions"]
    recommendation = {
        "recommendation": "Tinjau kesiapan tahap berikutnya.",
        "rationale": "Asesmen ulang menunjukkan kesenjangan tertutup.",
        "evaluations": [reassessment_evaluation.pk],
        "previous": 0,
    }
    assert client.post(draft_url, {**recommendation, "evaluations": []}).status_code == 400
    assert (
        client.post(draft_url, {**recommendation, "evaluations": [demonstration.pk]}).status_code
        == 400
    )
    assert client.post(draft_url, recommendation).status_code == 302
    assert client.post(draft_url, recommendation).status_code == 409
    revision = {**recommendation, "previous": 1, "evaluations": [production_evaluation.pk]}
    assert client.post(draft_url, revision).status_code == 302
    assert progression.drafts.get(number=1).evidence.get().evaluation == reassessment_evaluation
    assert progression.drafts.get(number=2).evidence.get().evaluation == production_evaluation

    kaprodi.permissions.add(Permission.objects.get(codename="view_progressionballot"))
    student_role.name = "Mahasiswa"
    student_role.save(update_fields=["name"])
    student_role.permissions.add(
        *Permission.objects.filter(
            codename__in=["view_progressiondecision", "add_progressionappeal"]
        )
    )
    progression_chair = User.objects.create_user(username="ketua-progresi-uji")
    member = User.objects.create_user(username="anggota-progresi-uji")
    today = timezone.localdate()
    mandate = ProgressionCommitteeMandate.objects.create(
        program=program,
        name="Komite Progresi",
        starts_on=today,
        ends_on=today + timedelta(days=1),
        quorum=2,
        created_by=actor,
    )
    chair = mandate.memberships.create(account=progression_chair, added_by=actor)
    mandate.memberships.create(account=member, added_by=actor)
    mandate.chair, mandate.issued_at, mandate.issued_by = chair, timezone.now(), actor
    mandate.save()
    case = reverse("progression_committee_case", args=[mandate.pk, enrollment.pk])
    outside = reverse("progression_committee_case", args=[mandate.pk, foreign_enrollment.pk])
    client.force_login(progression_reviewer)
    assert client.get(case).status_code == 404
    client.force_login(progression_chair)
    assert client.get(outside).status_code == 404
    assert (
        case
        in client.get(reverse("progression_committee_cases", args=[mandate.pk])).content.decode()
    )
    attend = {"action": "attendance", "present": "1", "conflict": "0"}
    assert client.post(case, attend).status_code == 302
    opened = {
        "action": "open",
        "draft": progression.drafts.get(number=2).pk,
        "outcome": "conditional",
        "conditions": "Selesaikan latihan penguatan.",
    }
    assert client.post(case, opened).status_code == 400
    client.force_login(member)
    assert client.post(case, {**attend, "conflict": "1"}).status_code == 302
    assert client.post(case, {"action": "vote", "choice": "approve"}).status_code == 403
    assert client.post(case, attend).status_code == 302
    assert client.post(case, opened).status_code == 403
    client.force_login(progression_chair)
    assert client.post(case, {**opened, "conditions": ""}).status_code == 400
    assert client.post(case, {**opened, "outcome": "attainment"}).status_code == 400
    assert client.post(case, opened).status_code == 302
    ballot = ProgressionBallot.objects.get()
    approval = {"action": "vote", "ballot": ballot.pk, "choice": "approve"}
    close = {"action": "close", "ballot": ballot.pk}
    publish = {"action": "publish", "ballot": ballot.pk, "rationale": "Komite menyetujui usulan."}
    assert client.post(case, publish).status_code == 409
    assert client.post(case, approval).status_code == 302
    assert client.post(case, approval).status_code == 302
    assert client.post(case, {**approval, "choice": "reject"}).status_code == 409
    client.force_login(member)
    assert client.post(case, {**approval, "choice": "abstain"}).status_code == 302
    assert client.post(case, close).status_code == 403
    client.force_login(progression_chair)
    assert client.post(case, close).status_code == 302
    ballot.refresh_from_db()
    assert ballot.result == ProgressionBallot.Result.RETURNED
    assert ballot.tally["eligible"] == 2 and ballot.tally["approvals"] == 1
    assert client.post(case, opened).status_code == 302
    second_round = ProgressionBallot.objects.first()
    close["ballot"] = second_round.pk
    client.force_login(member)
    assert client.post(case, {**attend, "present": "0"}).status_code == 302
    client.force_login(progression_chair)
    assert client.post(case, close).status_code == 302
    second_round.refresh_from_db()
    assert second_round.result == ProgressionBallot.Result.RETURNED
    assert second_round.tally["eligible"] == 1
    client.force_login(member)
    assert client.post(case, attend).status_code == 302
    client.force_login(progression_chair)
    assert client.post(case, {**opened, "standard": draft.standard_id}).status_code == 302
    final_round = ProgressionBallot.objects.first()
    approval["ballot"] = close["ballot"] = publish["ballot"] = final_round.pk
    assert client.post(case, approval).status_code == 302
    client.force_login(member)
    assert client.post(case, approval).status_code == 302
    client.force_login(progression_chair)
    assert client.post(case, close).status_code == 302
    assert client.post(case, publish).status_code == 409
    faculty_operator = User.objects.create_superuser(username="fakultas-banding-progresi")
    client.force_login(faculty_operator)
    policy_url = reverse("accounts:progression_appeal_policies")
    assert client.post(policy_url, {"program": program.pk, "days": 7}).status_code == 302
    client.force_login(progression_chair)
    assert client.post(case, publish).status_code == 302
    assert client.post(case, publish).status_code == 302
    decision = ProgressionDecision.objects.get()
    assert decision.ballot == final_round and decision.draft_id == opened["draft"]
    assert decision.rationale == publish["rationale"]
    student_detail = reverse("progression_decision", args=[decision.pk])
    assert client.get(student_detail).status_code == 404
    client.force_login(student)
    decision_page = client.get(student_detail).content.decode()
    assert opened["conditions"] in decision_page and publish["rationale"] in decision_page
    assert str(draft.standard) in decision_page

    assert decision.appeal_until == decision.published_at + timedelta(days=7)
    with patch(
        "apps.learning.progression_voting.timezone.now",
        return_value=decision.appeal_until + timedelta(seconds=1),
    ):
        assert client.post(student_detail, {"reason": "Banding terlambat."}).status_code == 409
    assert (
        client.post(student_detail, {"reason": "Mohon pertimbangkan syarat awal."}).status_code
        == 302
    )
    assert client.post(student_detail, {"reason": "Duplikat."}).status_code == 302
    appeal = ProgressionAppeal.objects.get()
    assert appeal.reason == "Mohon pertimbangkan syarat awal."

    independent_chair = User.objects.create_user(username="ketua-banding-progresi")
    independent = ProgressionCommitteeMandate.objects.create(
        program=program,
        name="Komite Banding",
        starts_on=today,
        ends_on=today + timedelta(days=2),
        quorum=1,
        created_by=faculty_operator,
    )
    independent.chair = independent.memberships.create(
        account=independent_chair, added_by=faculty_operator
    )
    duplicate_member = independent.memberships.create(account=member, added_by=faculty_operator)
    independent.issued_at, independent.issued_by = timezone.now(), faculty_operator
    independent.save()
    assign = reverse("accounts:assign_progression_appeal", args=[appeal.pk])
    assert client.post(assign, {"mandate": independent.pk}).status_code == 403
    client.force_login(faculty_operator)
    assert client.post(assign, {"mandate": mandate.pk}).status_code == 400
    assert client.post(assign, {"mandate": independent.pk}).status_code == 400
    duplicate_member.delete()
    assert client.post(assign, {"mandate": independent.pk}).status_code == 302
    assert client.post(policy_url, {"program": program.pk, "days": 14}).status_code == 302
    decision.refresh_from_db()
    assert decision.appeal_until == decision.published_at + timedelta(days=7)

    appeal_case = reverse("progression_committee_case", args=[independent.pk, enrollment.pk])
    client.force_login(independent_chair)
    assert appeal.reason not in client.get(appeal_case).content.decode()
    assert client.post(appeal_case, attend).status_code == 302
    assert appeal.reason in client.get(appeal_case).content.decode()
    reopen = {**opened, "appeal": appeal.pk, "conditions": "Selesaikan latihan dengan pembimbing."}
    assert client.post(appeal_case, reopen).status_code == 302
    appeal_ballot = ProgressionBallot.objects.get(appeal=appeal)
    assert client.post(appeal_case, {**approval, "ballot": appeal_ballot.pk}).status_code == 302
    assert client.post(appeal_case, {**close, "ballot": appeal_ballot.pk}).status_code == 302
    result = {**publish, "ballot": appeal_ballot.pk, "rationale": "Komite mengubah syarat."}
    assert client.post(appeal_case, result).status_code == 302
    assert client.post(appeal_case, {**result, "rationale": "Duplikat."}).status_code == 302
    appeal.refresh_from_db()
    replacement = ProgressionDecision.objects.get(replaces=decision)
    assert appeal.outcome == ProgressionAppeal.Outcome.CHANGED
    assert appeal.resolution == result["rationale"]
    assert replacement.ballot.conditions == reopen["conditions"]
    assert decision.ballot.conditions == opened["conditions"]
    client.force_login(student)
    assert "Keputusan diubah" in client.get(student_detail).content.decode()
    replacement_url = reverse("progression_decision", args=[replacement.pk])
    assert reopen["conditions"] in client.get(replacement_url).content.decode()
    assert client.post(replacement_url, {"reason": "Banding ulang."}).status_code == 409
