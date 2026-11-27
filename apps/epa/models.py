from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ConfigurationRecord(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class EntrustableProfessionalActivity(ConfigurationRecord):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    code = models.SlugField("Kode EPA", max_length=40)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(fields=("program", "code"), name="unique_epa_program_code"),
        ]

    def __str__(self) -> str:
        return self.code


class SupervisionScale(ConfigurationRecord):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    code = models.SlugField("Kode skala", max_length=40)

    class Meta:
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=("program", "code"), name="unique_supervision_scale_program_code"
            ),
        ]

    def __str__(self) -> str:
        return self.code


class SupervisionScaleVersion(ConfigurationRecord):
    scale = models.ForeignKey(SupervisionScale, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    name = models.CharField("Nama skala", max_length=200)

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(
                fields=("scale", "number"), name="unique_supervision_scale_version"
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0), name="positive_supervision_scale_version"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.scale} · {self.name} · v{self.number}"


class SupervisionLevel(ConfigurationRecord):
    version = models.ForeignKey(
        SupervisionScaleVersion, on_delete=models.PROTECT, related_name="levels"
    )
    position = models.PositiveIntegerField("Urutan")
    label = models.CharField("Tingkat supervisi", max_length=120)
    description = models.CharField("Deskripsi", max_length=400)

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("version", "position"), name="unique_supervision_level_position"
            ),
            models.CheckConstraint(
                condition=models.Q(position__gt=0), name="positive_supervision_level_position"
            ),
        ]

    def __str__(self) -> str:
        return self.label


class EPAVersion(ConfigurationRecord):
    activity = models.ForeignKey(
        EntrustableProfessionalActivity, on_delete=models.PROTECT, related_name="versions"
    )
    number = models.PositiveIntegerField()
    title = models.CharField("Nama kegiatan", max_length=200)
    description = models.CharField("Deskripsi kegiatan", max_length=600)
    practice_scope = models.CharField("Cakupan praktik", max_length=400, blank=True)
    limitations = models.CharField("Batasan praktik", max_length=400, blank=True)
    framework = models.ForeignKey(
        "competencies.CompetencyFrameworkVersion",
        on_delete=models.PROTECT,
        verbose_name="Versi kerangka kompetensi",
    )
    scale = models.ForeignKey(
        SupervisionScaleVersion, on_delete=models.PROTECT, verbose_name="Versi skala supervisi"
    )

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(fields=("activity", "number"), name="unique_epa_version"),
            models.CheckConstraint(condition=models.Q(number__gt=0), name="positive_epa_version"),
        ]

    def __str__(self) -> str:
        return f"{self.activity} · {self.title} · v{self.number}"

    def clean(self) -> None:
        super().clean()
        if self.activity_id is None:
            return
        program_id = self.activity.program_id
        if self.framework_id is not None and self.framework.framework.program_id != program_id:
            raise ValidationError({"framework": "Kerangka kompetensi harus satu prodi."})
        if self.scale_id is not None and self.scale.scale.program_id != program_id:
            raise ValidationError({"scale": "Skala supervisi harus satu prodi."})


class EPACompetencyLink(ConfigurationRecord):
    class Kind(models.TextChoices):
        CORE = "core", "Inti"
        SUPPORTING = "supporting", "Pendukung"

    version = models.ForeignKey(EPAVersion, on_delete=models.PROTECT, related_name="competencies")
    item = models.ForeignKey(
        "competencies.CompetencyItem", on_delete=models.PROTECT, verbose_name="Butir kompetensi"
    )
    kind = models.CharField("Peran kompetensi", max_length=12, choices=Kind.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("version", "item"), name="unique_epa_competency"),
        ]

    def __str__(self) -> str:
        return str(self.item)

    def clean(self) -> None:
        super().clean()
        if (
            self.version_id is not None
            and self.item_id is not None
            and self.item.version_id != self.version.framework_id
        ):
            raise ValidationError({"item": "Butir harus berasal dari versi kerangka EPA."})


class EPAPublication(ConfigurationRecord):
    version = models.OneToOneField(EPAVersion, on_delete=models.PROTECT, related_name="publication")

    class Meta:
        ordering = ("-version__number",)

    def __str__(self) -> str:
        return str(self.version)


class EPAAssessorAssignment(ConfigurationRecord):
    publication = models.ForeignKey(EPAPublication, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("publication", "enrollment", "assessor"),
                name="unique_epa_assessor_assignment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.publication}"

    def clean(self) -> None:
        super().clean()
        if (
            self.publication_id is not None
            and self.enrollment_id is not None
            and self.enrollment.cohort.period.program_id
            != self.publication.version.activity.program_id
        ):
            raise ValidationError({"enrollment": "Pendaftaran harus berasal dari prodi EPA."})
        if (
            self.enrollment_id is not None
            and self.assessor_id == self.enrollment.learner.account_id
        ):
            raise ValidationError({"assessor": "Asesor harus berbeda dari mahasiswa."})


class EPAObservation(ConfigurationRecord):
    assignment = models.ForeignKey(
        EPAAssessorAssignment, on_delete=models.PROTECT, related_name="observations"
    )
    occurred_on = models.DateField("Tanggal observasi")
    context = models.CharField("Konteks", max_length=400)
    case_complexity = models.CharField("Kompleksitas kasus", max_length=300)
    level = models.ForeignKey(
        SupervisionLevel, on_delete=models.PROTECT, verbose_name="Tingkat supervisi teramati"
    )
    feedback = models.TextField("Umpan balik", max_length=4000)

    class Meta:
        ordering = ("-occurred_on", "-pk")

    def __str__(self) -> str:
        return f"{self.assignment} · {self.occurred_on}"

    def clean(self) -> None:
        super().clean()
        if (
            self.assignment_id is not None
            and self.level_id is not None
            and self.level.version_id != self.assignment.publication.version.scale_id
        ):
            raise ValidationError({"level": "Tingkat harus berasal dari versi skala EPA."})


class EPAReviewAssignment(ConfigurationRecord):
    publication = models.ForeignKey(EPAPublication, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("publication", "enrollment", "reviewer"),
                name="unique_epa_review_assignment",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.publication}"


class EntrustmentReview(ConfigurationRecord):
    assignment = models.ForeignKey(
        EPAReviewAssignment, on_delete=models.PROTECT, related_name="drafts"
    )
    number = models.PositiveIntegerField()
    level = models.ForeignKey(
        SupervisionLevel, on_delete=models.PROTECT, verbose_name="Tingkat supervisi rekomendasi"
    )
    rationale = models.TextField("Alasan rekomendasi", max_length=4000)
    evidence = models.ManyToManyField(EPAObservation, through="EntrustmentReviewEvidence")

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "number"), name="unique_entrustment_review_revision"
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0), name="positive_entrustment_review_revision"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assignment} · Draf {self.number}"


class EntrustmentReviewEvidence(models.Model):
    review = models.ForeignKey(EntrustmentReview, on_delete=models.PROTECT)
    observation = models.ForeignKey(EPAObservation, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("review", "observation"), name="unique_entrustment_review_evidence"
            ),
        ]

    def __str__(self) -> str:
        return str(self.observation)


class EPACommitteeMandate(ConfigurationRecord):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    name = models.CharField("Nama komite", max_length=180)
    starts_on = models.DateField("Mulai berlaku")
    ends_on = models.DateField("Berakhir pada")
    quorum = models.PositiveIntegerField("Kuorum minimum")
    issued_at = models.DateTimeField(null=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        ordering = ("-starts_on", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="valid_epa_committee_dates",
            ),
            models.CheckConstraint(condition=models.Q(quorum__gt=0), name="positive_epa_quorum"),
            models.CheckConstraint(
                condition=(
                    models.Q(issued_at__isnull=True, issued_by__isnull=True)
                    | models.Q(issued_at__isnull=False, issued_by__isnull=False)
                ),
                name="epa_mandate_issuance_attribution",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(revoked_at__isnull=True, revoked_by__isnull=True)
                    | models.Q(
                        revoked_at__isnull=False, revoked_by__isnull=False, issued_at__isnull=False
                    )
                ),
                name="epa_mandate_revocation_attribution",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} · {self.program}"

    def clean(self) -> None:
        super().clean()
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Tanggal berakhir harus pada atau setelah awal."})


class EPACommitteeScope(ConfigurationRecord):
    mandate = models.ForeignKey(
        EPACommitteeMandate, on_delete=models.PROTECT, related_name="scopes"
    )
    activity = models.ForeignKey(EntrustableProfessionalActivity, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("mandate", "activity"), name="unique_epa_committee_scope"
            ),
        ]

    def __str__(self) -> str:
        return str(self.activity)

    def clean(self) -> None:
        super().clean()
        if (
            self.activity_id is not None
            and self.mandate_id is not None
            and self.activity.program_id != self.mandate.program_id
        ):
            raise ValidationError({"activity": "EPA harus berasal dari prodi mandat."})


class EPACommitteeMembership(ConfigurationRecord):
    mandate = models.ForeignKey(
        EPACommitteeMandate, on_delete=models.PROTECT, related_name="memberships"
    )
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("mandate", "account"), name="unique_epa_committee_member"
            ),
        ]

    def __str__(self) -> str:
        return str(self.account)


class EPACommitteeParticipation(ConfigurationRecord):
    mandate = models.ForeignKey(EPACommitteeMandate, on_delete=models.PROTECT)
    publication = models.ForeignKey(EPAPublication, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    present = models.BooleanField("Hadir")
    conflict = models.BooleanField("Memiliki konflik kepentingan")

    class Meta:
        ordering = ("-pk",)
        indexes = [
            models.Index(
                fields=("mandate", "publication", "enrollment", "created_by", "-id"),
                name="epa_participation_case_actor",
            )
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.created_by}"


class EPACommitteeChair(ConfigurationRecord):
    mandate = models.OneToOneField(
        EPACommitteeMandate, on_delete=models.PROTECT, related_name="chair"
    )
    member = models.ForeignKey(EPACommitteeMembership, on_delete=models.PROTECT)

    def __str__(self) -> str:
        return str(self.member)


class EPACommitteeBallot(ConfigurationRecord):
    class Outcome(models.TextChoices):
        ADVANCED = "advanced", "Usulan lolos"
        RETURNED = "returned", "Pembahasan lanjutan"

    mandate = models.ForeignKey(EPACommitteeMandate, on_delete=models.PROTECT)
    publication = models.ForeignKey(EPAPublication, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    draft = models.ForeignKey(EntrustmentReview, on_delete=models.PROTECT)
    proposed_level = models.ForeignKey(SupervisionLevel, on_delete=models.PROTECT, null=True)
    proposed_rationale = models.TextField(max_length=4000, blank=True)
    closed_at = models.DateTimeField(null=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    outcome = models.CharField(max_length=10, choices=Outcome.choices, blank=True)
    result = models.JSONField(default=dict)

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("mandate", "publication", "enrollment"),
                condition=models.Q(closed_at__isnull=True),
                name="unique_open_epa_case_ballot",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(closed_at__isnull=True, closed_by__isnull=True, outcome="")
                    | models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        outcome__in=("advanced", "returned"),
                    )
                ),
                name="valid_epa_ballot_closure",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.publication}"

    @property
    def level(self) -> SupervisionLevel:
        return self.proposed_level or self.draft.level

    @property
    def rationale(self) -> str:
        return self.proposed_rationale or self.draft.rationale


class EPACommitteeComment(ConfigurationRecord):
    ballot = models.ForeignKey(
        EPACommitteeBallot, on_delete=models.PROTECT, related_name="comments"
    )
    body = models.TextField("Catatan pembahasan", max_length=4000)

    class Meta:
        ordering = ("pk",)

    def __str__(self) -> str:
        return f"Catatan {self.pk}"


class EPACommitteeVote(ConfigurationRecord):
    class Choice(models.TextChoices):
        APPROVE = "approve", "Setuju"
        REJECT = "reject", "Tidak setuju"
        ABSTAIN = "abstain", "Abstain"

    ballot = models.ForeignKey(EPACommitteeBallot, on_delete=models.PROTECT, related_name="votes")
    choice = models.CharField("Suara", max_length=7, choices=Choice.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("ballot", "created_by"), name="unique_epa_ballot_vote"),
        ]

    def __str__(self) -> str:
        return self.get_choice_display()


class EPAAppealPolicy(ConfigurationRecord):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    days = models.PositiveIntegerField("Tenggat banding (hari)")

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.CheckConstraint(condition=models.Q(days__gt=0), name="positive_epa_appeal_days"),
        ]

    def __str__(self) -> str:
        return f"{self.program} · {self.days} hari"


class EntrustmentDecision(ConfigurationRecord):
    ballot = models.OneToOneField(
        EPACommitteeBallot, on_delete=models.PROTECT, related_name="decision"
    )
    appeal_until = models.DateTimeField(null=True)
    replaces = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="replacement"
    )

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return str(self.ballot)


class EPAAppeal(ConfigurationRecord):
    class Outcome(models.TextChoices):
        UPHELD = "upheld", "Keputusan dikuatkan"
        CHANGED = "changed", "Keputusan diubah"

    decision = models.OneToOneField(EntrustmentDecision, on_delete=models.PROTECT)
    reason = models.TextField("Alasan banding", max_length=4000)
    mandate = models.ForeignKey(EPACommitteeMandate, on_delete=models.PROTECT, null=True)
    assigned_at = models.DateTimeField(null=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    result_ballot = models.OneToOneField(
        EPACommitteeBallot, on_delete=models.PROTECT, null=True, related_name="appeal_result"
    )
    outcome = models.CharField(max_length=7, choices=Outcome.choices, blank=True)
    resolution = models.TextField("Alasan hasil banding", max_length=4000, blank=True)
    resolved_at = models.DateTimeField(null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        ordering = ("-pk",)

    def __str__(self) -> str:
        return f"Banding · {self.decision}"
