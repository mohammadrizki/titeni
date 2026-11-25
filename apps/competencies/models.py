from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.academics.models import CurriculumStage, StudyProgram


class DraftRecord(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class CompetencyFramework(models.Model):
    program = models.OneToOneField(StudyProgram, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return str(self.program)


class CompetencyFrameworkVersion(DraftRecord):
    framework = models.ForeignKey(
        CompetencyFramework, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["framework", "number"], name="unique_framework_version"
            ),
            models.CheckConstraint(condition=Q(number__gt=0), name="positive_framework_version"),
        ]

    def __str__(self) -> str:
        return f"{self.framework} · {self.number}"


class CompetencyItem(DraftRecord):
    version = models.ForeignKey(
        CompetencyFrameworkVersion, on_delete=models.PROTECT, related_name="items"
    )
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, verbose_name="Butir induk"
    )
    code = models.SlugField("Kode butir", max_length=40)
    name = models.CharField("Nama butir", max_length=200)

    class Meta:
        ordering = ["code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["version", "code"], name="unique_version_item_code"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    def clean(self) -> None:
        super().clean()
        ancestor = self.parent
        visited = {self.pk}
        while ancestor is not None:
            if ancestor.pk in visited or ancestor.version_id != self.version_id:
                raise ValidationError({"parent": "Butir induk harus satu versi dan bebas siklus."})
            visited.add(ancestor.pk)
            ancestor = ancestor.parent


class CompetencyMilestone(DraftRecord):
    item = models.ForeignKey(CompetencyItem, on_delete=models.PROTECT, verbose_name="Butir")
    stage = models.ForeignKey(
        CurriculumStage, on_delete=models.PROTECT, verbose_name="Tahap kurikulum"
    )
    expectation = models.CharField("Ekspektasi perkembangan", max_length=400)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.item} · {self.stage}"

    def clean(self) -> None:
        super().clean()
        if (
            self.item_id is not None
            and self.stage_id is not None
            and self.stage.version.curriculum.program_id != self.item.version.framework.program_id
        ):
            raise ValidationError({"stage": "Tahap kurikulum harus berasal dari prodi yang sama."})


class CompetencyIndicator(DraftRecord):
    item = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, related_name="indicators", verbose_name="Butir"
    )
    code = models.SlugField("Kode indikator", max_length=40)
    description = models.CharField("Deskripsi indikator", max_length=400)

    class Meta:
        ordering = ["item__code", "code", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "code"],
                name="unique_item_indicator_code",
                violation_error_message="Kode indikator sudah digunakan pada butir ini.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.description}"


class CompetencyRelationship(DraftRecord):
    source = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, related_name="+", verbose_name="Butir asal"
    )
    target = models.ForeignKey(
        CompetencyItem, on_delete=models.PROTECT, related_name="+", verbose_name="Butir tujuan"
    )
    description = models.CharField("Relasi perkembangan", max_length=400)

    class Meta:
        ordering = ["source__code", "target__code", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(source=models.F("target")),
                name="distinct_competency_relationship_items",
                violation_error_message="Butir asal dan tujuan harus berbeda.",
            ),
            models.UniqueConstraint(
                fields=["source", "target", "description"],
                name="unique_competency_relationship_description",
                violation_error_message="Relasi ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source} → {self.target}"

    def clean(self) -> None:
        super().clean()
        if (
            self.source_id is not None
            and self.target_id is not None
            and self.source.version_id != self.target.version_id
        ):
            raise ValidationError({"target": "Butir tujuan harus berasal dari draf yang sama."})


class PerformanceStandard(models.Model):
    item = models.ForeignKey(CompetencyItem, on_delete=models.PROTECT, verbose_name="Butir")
    code = models.SlugField("Kode standar", max_length=40)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["item", "code"], name="unique_item_standard_code"),
        ]

    def __str__(self) -> str:
        return f"{self.item} · {self.code}"


class PerformanceStandardVersion(DraftRecord):
    standard = models.ForeignKey(
        PerformanceStandard, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    description = models.CharField("Deskripsi standar performa", max_length=400)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["standard", "number"], name="unique_performance_standard_version"
            ),
            models.CheckConstraint(
                condition=Q(number__gt=0), name="positive_performance_standard_version"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.standard} · {self.number}"
