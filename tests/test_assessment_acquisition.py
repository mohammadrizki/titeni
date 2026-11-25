from datetime import date
from pathlib import Path

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
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
from apps.assessments.models import (
    AssessmentAttempt,
    AssessmentBlueprint,
    AssessmentEvent,
    AssessmentParticipation,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyFramework
from apps.evidence.models import (
    ArtifactMap,
    ArtifactMapPublication,
    EvidenceArtifact,
    EvidenceImportBatch,
    EvidenceInvalidation,
    EvidencePlacement,
    EvidenceRecord,
    EvidenceSource,
    EvidenceType,
    EvidenceVerification,
    LearnerEvidenceBaseline,
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
    base_entry = {
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
    assert client.post(verification_url(ambiguous.pk), cancel).status_code == 302
    assert EvidencePlacement.objects.filter(pk=placement.pk).exists()
    assert [count for _, count in client.get(reconcile_url).context["progress"]] == [1, 0, 0, 1]

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
