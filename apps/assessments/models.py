from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.academics.models import CurriculumStage, StudyProgram
from apps.competencies.models import CompetencyFrameworkVersion, CompetencyItem


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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item__code", "competency__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "competency"],
                name="unique_blueprint_item_competency",
                violation_error_message="Pemetaan ini sudah tercatat.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.item} · {self.competency}"
