from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.academics.models import StudyProgram
from apps.competencies.models import CompetencyItem
from apps.evidence.artifact_storage import artifact_upload_path, evidence_artifact_storage


class RegistryRecord(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class EvidenceSource(RegistryRecord):
    program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT)
    code = models.SlugField("Kode sumber", max_length=40)
    name = models.CharField("Nama sumber", max_length=200)
    acquisition = models.CharField("Cara memperoleh bukti", max_length=400)
    verification = models.CharField("Cara memverifikasi bukti", max_length=400)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["program", "code"], name="unique_evidence_source_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class EvidenceType(RegistryRecord):
    program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT)
    code = models.SlugField("Kode jenis", max_length=40)
    name = models.CharField("Nama jenis bukti", max_length=200)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["program", "code"], name="unique_evidence_type_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class EvidenceSourceCapability(RegistryRecord):
    source = models.ForeignKey(
        EvidenceSource, on_delete=models.PROTECT, verbose_name="Sumber bukti"
    )
    evidence_type = models.ForeignKey(
        EvidenceType, on_delete=models.PROTECT, verbose_name="Jenis bukti"
    )

    class Meta:
        ordering = ["source__code", "evidence_type__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "evidence_type"],
                name="unique_evidence_source_capability",
                violation_error_message="Kapabilitas ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source} · {self.evidence_type}"


class EvidenceSourceCompetency(RegistryRecord):
    source = models.ForeignKey(
        EvidenceSource, on_delete=models.PROTECT, verbose_name="Sumber bukti"
    )
    competency = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, verbose_name="Butir kompetensi"
    )

    class Meta:
        ordering = ["source__code", "competency__version__number", "competency__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "competency"],
                name="unique_evidence_source_competency",
                violation_error_message="Pemetaan sumber ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source} · {self.competency}"


class ArtifactMap(models.Model):
    program = models.OneToOneField(StudyProgram, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return str(self.program)


class ArtifactMapVersion(RegistryRecord):
    artifact_map = models.ForeignKey(ArtifactMap, on_delete=models.PROTECT, related_name="versions")
    blueprint_version = models.ForeignKey(
        "assessments.AssessmentBlueprintVersion",
        on_delete=models.PROTECT,
        verbose_name="Draf blueprint asesmen",
    )
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["artifact_map", "number"], name="unique_artifact_map_version"
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0), name="positive_artifact_map_version"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.artifact_map} · {self.number}"


class EvidenceRequirementTemplate(RegistryRecord):
    blueprint_version = models.ForeignKey(
        "assessments.AssessmentBlueprintVersion",
        on_delete=models.PROTECT,
        related_name="manual_evidence_requirements",
    )
    competency = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, verbose_name="Butir kompetensi"
    )
    capability = models.ForeignKey(
        EvidenceSourceCapability,
        on_delete=models.PROTECT,
        related_name="evidence_requirements",
        verbose_name="Sumber dan jenis bukti",
    )
    code = models.SlugField("Kode persyaratan", max_length=40)
    name = models.CharField("Nama persyaratan", max_length=200)
    minimum_count = models.PositiveIntegerField("Jumlah minimum bukti")
    context = models.CharField("Konteks bukti", max_length=250, blank=True)

    class Meta:
        ordering = ["code", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["blueprint_version", "code"],
                name="unique_manual_evidence_requirement_code",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_count__gt=0), name="positive_evidence_requirement_count"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    def clean(self) -> None:
        super().clean()
        if not self.blueprint_version_id:
            return
        if (
            self.competency_id
            and self.competency.version_id != self.blueprint_version.framework_version_id
        ):
            raise ValidationError(
                {"competency": "Butir harus berasal dari versi kerangka blueprint."}
            )
        if self.capability_id:
            program_id = self.blueprint_version.blueprint.program_id
            if (
                self.capability.source.program_id != program_id
                or self.capability.evidence_type.program_id != program_id
            ):
                raise ValidationError(
                    {"capability": "Sumber dan jenis bukti harus berasal dari prodi yang sama."}
                )


class LearnerEvidencePlan(RegistryRecord):
    enrollment = models.ForeignKey(
        "academics.LearnerEnrollment", on_delete=models.PROTECT, related_name="evidence_plan_drafts"
    )
    artifact_map_version = models.ForeignKey(
        ArtifactMapVersion, on_delete=models.PROTECT, verbose_name="Versi peta artefak"
    )

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["enrollment", "artifact_map_version"],
                name="unique_enrollment_artifact_map_draft",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.artifact_map_version.number}"

    def clean(self) -> None:
        super().clean()
        if (
            self.enrollment_id
            and self.artifact_map_version_id
            and self.enrollment.cohort.period.program_id
            != self.artifact_map_version.artifact_map.program_id
        ):
            raise ValidationError(
                {"artifact_map_version": "Peta harus berasal dari prodi mahasiswa."}
            )


class ArtifactMapPublication(RegistryRecord):
    artifact_map = models.ForeignKey(
        ArtifactMap, on_delete=models.PROTECT, related_name="publications"
    )
    version = models.OneToOneField(
        ArtifactMapVersion, on_delete=models.PROTECT, related_name="publication"
    )
    effective_on = models.DateField("Tanggal efektif")
    requirements = models.JSONField()

    class Meta:
        ordering = ["-effective_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["artifact_map", "effective_on"], name="unique_artifact_map_effective_date"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.version} · {self.effective_on}"


class LearnerEvidenceBaseline(RegistryRecord):
    enrollment = models.OneToOneField(
        "academics.LearnerEnrollment", on_delete=models.PROTECT, related_name="evidence_baseline"
    )
    publication = models.ForeignKey(ArtifactMapPublication, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.publication}"


class EvidenceImportBatch(RegistryRecord):
    attempt = models.ForeignKey("assessments.AssessmentAttempt", on_delete=models.PROTECT)
    file_digest = models.CharField(max_length=64)
    created_count = models.PositiveIntegerField()
    skipped_count = models.PositiveIntegerField()

    def __str__(self) -> str:
        return f"Impor bukti {self.pk}"


class EvidenceRecordQuerySet(models.QuerySet):
    def eligible_for_reconciliation(self):
        return self.filter(
            superseded_by__isnull=True,
            invalidation__isnull=True,
            verification__status=EvidenceVerification.Status.VERIFIED,
        )


class EvidenceRecord(RegistryRecord):
    attempt = models.ForeignKey(
        "assessments.AssessmentAttempt", on_delete=models.PROTECT, related_name="evidence_records"
    )
    source_link = models.ForeignKey(
        "assessments.BlueprintItemEvidenceSource",
        on_delete=models.PROTECT,
        related_name="acquired_records",
        verbose_name="Sumber dan jenis bukti",
    )
    reference = models.CharField("Referensi bukti", max_length=160)
    context = models.CharField("Konteks pengamatan", max_length=250, blank=True)
    import_batch = models.ForeignKey(
        EvidenceImportBatch, on_delete=models.PROTECT, null=True, blank=True
    )
    supersedes = models.OneToOneField(
        "self", on_delete=models.PROTECT, related_name="superseded_by", null=True, blank=True
    )
    revision_number = models.PositiveIntegerField(default=1)
    correction_reason = models.CharField("Alasan koreksi", max_length=500, blank=True)
    objects = EvidenceRecordQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "source_link", "reference"],
                condition=models.Q(supersedes__isnull=True),
                name="unique_original_evidence_attempt_ref",
                violation_error_message="Referensi bukti ini sudah tercatat.",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(supersedes__isnull=True, revision_number=1, correction_reason="")
                    | (
                        models.Q(supersedes__isnull=False, revision_number__gt=1)
                        & ~models.Q(correction_reason="")
                    )
                ),
                name="valid_evidence_revision_metadata",
            ),
        ]

    def __str__(self) -> str:
        return self.reference

    def clean(self) -> None:
        super().clean()
        predecessor = self.supersedes
        if predecessor is not None and (
            predecessor.attempt_id != self.attempt_id
            or predecessor.revision_number + 1 != self.revision_number
        ):
            raise ValidationError("Versi koreksi harus mengikuti bukti pada percobaan yang sama.")


class EvidenceVerification(RegistryRecord):
    class Status(models.TextChoices):
        VERIFIED = "verified", "Terverifikasi"
        REJECTED = "rejected", "Ditolak"

    record = models.OneToOneField(
        EvidenceRecord, on_delete=models.PROTECT, related_name="verification"
    )
    status = models.CharField("Keputusan", max_length=12, choices=Status.choices)
    reason = models.CharField("Alasan", max_length=500)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["verified", "rejected"]),
                name="valid_evidence_verification_status",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="required_evidence_verification_reason"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.record} · {self.get_status_display()}"

    def clean(self) -> None:
        super().clean()
        if self.record_id and self.created_by_id == self.record.created_by_id:
            raise ValidationError("Pencatat bukti tidak dapat memverifikasi catatannya sendiri.")


class EvidenceInvalidation(RegistryRecord):
    record = models.OneToOneField(
        EvidenceRecord, on_delete=models.PROTECT, related_name="invalidation"
    )
    reason = models.CharField("Alasan pembatalan", max_length=500)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="required_evidence_invalidation_reason"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.record} · Dibatalkan"

    def clean(self) -> None:
        super().clean()
        if self.record_id and self.created_by_id == self.record.created_by_id:
            raise ValidationError("Pencatat bukti tidak dapat membatalkan catatannya sendiri.")


class EvidencePlacement(RegistryRecord):
    baseline = models.ForeignKey(
        LearnerEvidenceBaseline, on_delete=models.PROTECT, related_name="evidence_placements"
    )
    record = models.OneToOneField(
        EvidenceRecord, on_delete=models.PROTECT, related_name="placement"
    )
    requirement_number = models.PositiveIntegerField()
    reason = models.CharField("Alasan penempatan", max_length=500)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(requirement_number__gt=0), name="positive_placement_requirement"
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="required_evidence_placement_reason"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.record} · {self.requirement_number}"


class EvidenceArtifact(RegistryRecord):
    record = models.ForeignKey(EvidenceRecord, on_delete=models.PROTECT, related_name="artifacts")
    file = models.FileField(
        upload_to=artifact_upload_path, storage=evidence_artifact_storage, max_length=255
    )
    original_name = models.CharField("Nama berkas", max_length=255)
    size_bytes = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["record", "sha256"], name="unique_pdf_on_evidence"),
            models.CheckConstraint(condition=models.Q(size_bytes__gt=0), name="positive_pdf_size"),
        ]

    def __str__(self) -> str:
        return self.original_name


class EvidenceIntegration(models.Model):
    account = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.ForeignKey(EvidenceSource, on_delete=models.PROTECT)
    token_digest = models.CharField(max_length=64, unique=True)
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.account} · {self.source}"


class ExternalEvidenceReceipt(models.Model):
    integration = models.ForeignKey(EvidenceIntegration, on_delete=models.PROTECT)
    source = models.ForeignKey(EvidenceSource, on_delete=models.PROTECT)
    record = models.OneToOneField(
        EvidenceRecord, on_delete=models.PROTECT, related_name="external_receipt"
    )
    external_id = models.CharField(max_length=160)
    payload_digest = models.CharField(max_length=64)
    adapter_version = models.CharField(max_length=12)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "external_id"], name="unique_external_evidence_source_id"
            ),
        ]

    def __str__(self) -> str:
        return self.external_id
