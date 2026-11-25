from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.academics.models import CurriculumStage, StudyProgram
from apps.competencies.models import (
    CompetencyFrameworkVersion,
    CompetencyIndicator,
    CompetencyItem,
)
from apps.evidence.models import EvidenceSourceCapability


class AssessmentBlueprint(models.Model):
    program = models.OneToOneField(StudyProgram, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return str(self.program)


class AssessmentBlueprintVersion(models.Model):
    blueprint = models.ForeignKey(
        AssessmentBlueprint, on_delete=models.PROTECT, related_name="versions"
    )
    framework_version = models.ForeignKey(
        CompetencyFrameworkVersion, on_delete=models.PROTECT, verbose_name="Draf kompetensi"
    )
    number = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["blueprint", "number"], name="unique_assessment_blueprint_version"
            ),
            models.CheckConstraint(condition=Q(number__gt=0), name="positive_blueprint_version"),
        ]

    def __str__(self) -> str:
        return f"{self.blueprint} · {self.number}"


class BlueprintItem(models.Model):
    version = models.ForeignKey(
        AssessmentBlueprintVersion, on_delete=models.PROTECT, related_name="items"
    )
    code = models.SlugField("Kode", max_length=40)
    name = models.CharField("Komponen asesmen", max_length=200)
    method = models.CharField("Metode asesmen", max_length=120)
    purpose = models.CharField("Tujuan asesmen", max_length=250)
    stage = models.ForeignKey(
        CurriculumStage, on_delete=models.PROTECT, verbose_name="Tahap kurikulum"
    )
    timing = models.CharField("Waktu asesmen", max_length=120)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "code"],
                name="unique_blueprint_item_code",
                violation_error_message="Kode komponen sudah digunakan pada draf ini.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class BlueprintItemCompetency(models.Model):
    item = models.ForeignKey(
        BlueprintItem, on_delete=models.PROTECT, verbose_name="Komponen asesmen"
    )
    competency = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, verbose_name="Butir kompetensi"
    )
    indicator = models.ForeignKey(
        CompetencyIndicator,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Indikator kompetensi",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__code", "competency__code", "indicator__code", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "competency"],
                condition=Q(indicator__isnull=True),
                name="unique_blueprint_general_competency",
                violation_error_message="Pemetaan ini sudah tercatat.",
            ),
            models.UniqueConstraint(
                fields=["item", "indicator"],
                condition=Q(indicator__isnull=False),
                name="unique_blueprint_item_indicator",
                violation_error_message="Pemetaan indikator ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} · {self.competency}"

    def clean(self) -> None:
        super().clean()
        indicator = self.indicator
        if indicator is not None and self.competency_id and indicator.item_id != self.competency_id:
            raise ValidationError({"indicator": "Indikator harus berasal dari butir yang dipilih."})


class AssessmentSamplingRule(models.Model):
    item = models.ForeignKey(
        BlueprintItem, on_delete=models.PROTECT, verbose_name="Komponen asesmen"
    )
    context = models.CharField("Konteks sampling", max_length=250)
    minimum_observations = models.PositiveIntegerField("Jumlah minimum observasi")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__code", "context", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(minimum_observations__gt=0), name="positive_sampling_observations"
            ),
            models.UniqueConstraint(
                fields=["item", "context"],
                name="unique_blueprint_item_sampling_context",
                violation_error_message="Rancangan sampling untuk konteks ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} · {self.context}"


class BlueprintItemEvidenceSource(models.Model):
    item = models.ForeignKey(
        BlueprintItem, on_delete=models.PROTECT, verbose_name="Komponen asesmen"
    )
    capability = models.ForeignKey(
        EvidenceSourceCapability,
        on_delete=models.PROTECT,
        related_name="blueprint_links",
        verbose_name="Sumber dan jenis bukti",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__code", "capability__source__code", "capability__evidence_type__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "capability"],
                name="unique_blueprint_item_source_capability",
                violation_error_message="Sumber dan jenis bukti ini sudah tercatat pada komponen.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} · {self.capability}"

    def clean(self) -> None:
        super().clean()
        if self.item_id and self.capability_id:
            program_id = self.item.version.blueprint.program_id
            if (
                self.capability.source.program_id != program_id
                or self.capability.evidence_type.program_id != program_id
            ):
                raise ValidationError(
                    {"capability": "Sumber dan jenis bukti harus berasal dari prodi yang sama."}
                )


class AssessmentEvent(models.Model):
    component = models.ForeignKey(
        BlueprintItem, on_delete=models.PROTECT, related_name="events", verbose_name="Komponen"
    )
    name = models.CharField("Nama pelaksanaan", max_length=200)
    occurred_on = models.DateField("Tanggal pelaksanaan")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_on", "-pk"]

    def __str__(self) -> str:
        return self.name


class AssessmentParticipation(models.Model):
    event = models.ForeignKey(AssessmentEvent, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "enrollment"], name="unique_assessment_event_enrollment"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event} · {self.enrollment}"


class AssessmentAttempt(models.Model):
    participation = models.ForeignKey(
        AssessmentParticipation, on_delete=models.PROTECT, related_name="attempts"
    )
    number = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["participation_id", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["participation", "number"], name="unique_assessment_attempt_number"
            ),
            models.CheckConstraint(condition=Q(number__gt=0), name="positive_attempt_number"),
        ]

    def __str__(self) -> str:
        return f"{self.participation.enrollment.learner} · {self.number}"


class ExamResultImport(models.Model):
    event = models.ForeignKey(AssessmentEvent, on_delete=models.PROTECT)
    adapter = models.SlugField(max_length=40)
    source_label = models.CharField(max_length=120)
    digest = models.CharField(max_length=64)
    row_count = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "adapter", "digest"], name="unique_exam_result_import"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source_label} · {self.event}"


class ImportedExamResult(models.Model):
    batch = models.ForeignKey(ExamResultImport, on_delete=models.PROTECT, related_name="results")
    row_number = models.PositiveIntegerField()
    participant = models.CharField(max_length=254)
    score = models.CharField(max_length=32, blank=True)
    raw_score = models.CharField(max_length=32, blank=True)
    maximum = models.CharField(max_length=32, blank=True)
    session = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_number"], name="unique_exam_import_row_number"
            ),
        ]

    def __str__(self) -> str:
        return self.participant


class ExamImportProtocol(models.Model):
    class Engine(models.TextChoices):
        MOODLE = "moodle", "Moodle XLSX"
        EXAMTOOL = "examtool", "ExamTool CSV"
        CSV = "csv-lain", "CSV dengan pemetaan kolom"

    slug = models.SlugField(max_length=40, unique=True)
    name = models.CharField("Nama aplikasi", max_length=120, unique=True)
    engine = models.CharField("Protokol", max_length=16, choices=Engine.choices)
    options = models.JSONField(default=dict, blank=True)
    active = models.BooleanField("Aktif", default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(engine__in=["moodle", "examtool", "csv-lain"]),
                name="valid_exam_import_engine",
            ),
        ]

    def __str__(self) -> str:
        return self.name
