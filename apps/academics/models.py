from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Institution(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField("Nama fakultas", max_length=200)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(pk=1), name="single_faculty")]

    def __str__(self) -> str:
        return self.name


class StudyProgram(models.Model):
    class Stage(models.TextChoices):
        UNDERGRADUATE = "undergraduate", "Sarjana"
        PROFESSIONAL = "professional", "Profesi"
        SPECIALIST = "specialist", "Spesialis"
        SUBSPECIALIST = "subspecialist", "Subspesialis"

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    code = models.SlugField("Kode", max_length=40, unique=True)
    name = models.CharField("Nama program studi", max_length=200)
    education_stage = models.CharField("Jenjang", max_length=20, choices=Stage.choices)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    education_stage__in=[
                        "undergraduate",
                        "professional",
                        "specialist",
                        "subspecialist",
                    ]
                ),
                name="valid_program_education_stage",
            )
        ]

    def __str__(self) -> str:
        return self.name


class AcademicPeriod(models.Model):
    program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT)
    code = models.SlugField("Kode", max_length=40)
    name = models.CharField("Nama periode", max_length=200)
    starts_on = models.DateField("Mulai")
    ends_on = models.DateField("Selesai")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_on", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["program", "code"], name="unique_program_period_code"),
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")), name="period_date_order"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Curriculum(models.Model):
    program = models.ForeignKey(StudyProgram, on_delete=models.PROTECT)
    code = models.SlugField("Kode kurikulum", max_length=40)
    name = models.CharField("Nama kurikulum", max_length=200)

    class Meta:
        ordering = ["code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["program", "code"], name="unique_program_curriculum"),
        ]

    def __str__(self) -> str:
        return self.name


class CurriculumVersion(models.Model):
    curriculum = models.ForeignKey(Curriculum, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["curriculum", "number"], name="unique_curriculum_version"
            ),
            models.CheckConstraint(condition=Q(number__gt=0), name="positive_curriculum_version"),
        ]

    def __str__(self) -> str:
        return f"{self.curriculum} · {self.number}"


class CurriculumStage(models.Model):
    version = models.ForeignKey(CurriculumVersion, on_delete=models.PROTECT, related_name="stages")
    code = models.SlugField("Kode tahap", max_length=40)
    name = models.CharField("Nama tahap", max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "code"], name="unique_curriculum_stage_code"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Cohort(models.Model):
    period = models.ForeignKey(AcademicPeriod, on_delete=models.PROTECT, related_name="cohorts")
    code = models.SlugField("Kode kohort", max_length=40)
    name = models.CharField("Nama kohort", max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period__starts_on", "code", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["period", "code"], name="unique_period_cohort_code"),
        ]

    def __str__(self) -> str:
        return self.name


class Learner(models.Model):
    account = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="learner"
    )

    def __str__(self) -> str:
        return self.account.get_username()


class LearnerEnrollment(models.Model):
    learner = models.ForeignKey(Learner, on_delete=models.PROTECT, related_name="enrollments")
    cohort = models.ForeignKey(Cohort, on_delete=models.PROTECT, related_name="enrollments")
    enrolled_on = models.DateField("Tanggal pendaftaran")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-enrolled_on", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["learner", "cohort"], name="unique_learner_cohort"),
        ]

    def __str__(self) -> str:
        return f"{self.learner} · {self.cohort}"
