from django.db import models


class LearningPlan(models.Model):
    enrollment = models.OneToOneField("academics.LearnerEnrollment", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Rencana belajar {self.pk}"


class LearningGoal(models.Model):
    revision_number = models.PositiveIntegerField(default=1)
    plan = models.ForeignKey(LearningPlan, on_delete=models.PROTECT, related_name="goals")
    competency = models.ForeignKey("competencies.CompetencyItem", on_delete=models.PROTECT)
    reflection_source = models.ForeignKey(
        "reflection.ReflectionRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Versi refleksi asal",
    )
    coaching_source = models.ForeignKey(
        "reflection.CoachingRecommendation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Rekomendasi coaching asal",
    )
    rationale = models.CharField("Alasan", max_length=500)
    activity = models.CharField("Kegiatan belajar", max_length=500)
    expected_outcome = models.CharField("Hasil yang diharapkan", max_length=500)
    improvement_evidence = models.CharField("Bukti kemajuan", max_length=500)
    completion_criteria = models.CharField("Kriteria penyelesaian", max_length=500)
    due_on = models.DateField("Tenggat kegiatan")
    review_on = models.DateField("Tanggal tinjauan")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_on", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(reflection_source__isnull=True)
                | models.Q(coaching_source__isnull=True),
                name="single_learning_goal_source",
            ),
        ]

    def __str__(self) -> str:
        return self.activity


class LearningGoalRevision(models.Model):
    goal = models.ForeignKey(LearningGoal, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["goal", "number"], name="unique_learning_goal_revision")
        ]

    def __str__(self) -> str:
        return f"Versi {self.number}"


class LearningGoalShare(models.Model):
    goal = models.ForeignKey(LearningGoal, on_delete=models.PROTECT)
    assignment = models.ForeignKey(
        "reflection.ReflectionAdvisorAssignment", on_delete=models.PROTECT
    )
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    shared_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["goal", "assignment", "number"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_learning_goal_share",
            ),
        ]

    def __str__(self) -> str:
        return f"Tujuan belajar · Versi {self.number}"


class LearningGoalReview(models.Model):
    share = models.ForeignKey(LearningGoalShare, on_delete=models.PROTECT, related_name="reviews")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    note = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"Tinjauan {self.pk}"


class InterventionDraft(models.Model):
    evaluation = models.ForeignKey("adaptive.EvidenceEvaluation", on_delete=models.PROTECT)
    assignment = models.ForeignKey(
        "reflection.ReflectionAdvisorAssignment", on_delete=models.PROTECT
    )
    activity = models.CharField("Kegiatan intervensi", max_length=500)
    rationale = models.CharField("Alasan", max_length=500)
    expected_outcome = models.CharField("Hasil yang diharapkan", max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.activity


class InterventionApproval(models.Model):
    draft = models.OneToOneField(InterventionDraft, on_delete=models.PROTECT)
    approved_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    approved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Persetujuan {self.draft}"


class InterventionCompletionReport(models.Model):
    approval = models.OneToOneField(InterventionApproval, on_delete=models.PROTECT)
    reported_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    reported_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Laporan pelaksanaan intervensi {self.approval_id}"


class ReassessmentRequirement(models.Model):
    completion = models.OneToOneField(
        InterventionCompletionReport, on_delete=models.PROTECT, related_name="reassessment"
    )
    verified_assignment = models.ForeignKey(
        "reflection.ReflectionAdvisorAssignment", on_delete=models.PROTECT
    )
    verified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Kebutuhan asesmen ulang {self.pk}"


class AcademicAdvisorAssignment(models.Model):
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    advisor = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    assigned_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "advisor"),
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_academic_advisor",
            )
        ]

    def __str__(self) -> str:
        return str(self.advisor)


class LongitudinalSynthesis(models.Model):
    assignment = models.ForeignKey(AcademicAdvisorAssignment, on_delete=models.PROTECT)
    body = models.TextField("Sintesis", max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=~models.Q(body=""), name="nonempty_synthesis")
        ]

    def __str__(self) -> str:
        return f"Sintesis longitudinal {self.pk}"


class ProgressionReviewAssignment(models.Model):
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    reviewer = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    assigned_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "reviewer"), name="unique_progression_review_assignment"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.reviewer}"


class ProgressionReview(models.Model):
    assignment = models.ForeignKey(
        ProgressionReviewAssignment, on_delete=models.PROTECT, related_name="drafts"
    )
    number = models.PositiveIntegerField()
    recommendation = models.CharField("Rekomendasi", max_length=500)
    rationale = models.TextField("Alasan rekomendasi", max_length=4000)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "number"), name="unique_progression_review_version"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assignment} · Draf {self.number}"


class ProgressionReviewEvidence(models.Model):
    review = models.ForeignKey(ProgressionReview, on_delete=models.PROTECT, related_name="evidence")
    evaluation = models.ForeignKey(
        "adaptive.EvidenceEvaluation", on_delete=models.PROTECT, null=True
    )
    decision = models.ForeignKey("epa.EntrustmentDecision", on_delete=models.PROTECT, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(evaluation__isnull=False, decision__isnull=True)
                    | models.Q(evaluation__isnull=True, decision__isnull=False)
                ),
                name="progression_evidence_one_source",
            ),
            models.UniqueConstraint(
                fields=("review", "evaluation"), name="unique_progression_eval_evidence"
            ),
            models.UniqueConstraint(
                fields=("review", "decision"), name="unique_progression_epa_evidence"
            ),
        ]

    def __str__(self) -> str:
        return str(self.evaluation or self.decision)


class ProgressionCommitteeMandate(models.Model):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    name = models.CharField("Nama komite", max_length=180)
    starts_on = models.DateField("Mulai berlaku")
    ends_on = models.DateField("Berakhir pada")
    quorum = models.PositiveIntegerField("Kuorum minimum")
    chair = models.ForeignKey(
        "ProgressionCommitteeMembership", on_delete=models.PROTECT, null=True, related_name="+"
    )
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    issued_at = models.DateTimeField(null=True)
    issued_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )
    revoked_at = models.DateTimeField(null=True)
    revoked_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        ordering = ("-starts_on", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__gte=models.F("starts_on")),
                name="valid_progression_mandate_dates",
            ),
            models.CheckConstraint(
                condition=models.Q(quorum__gt=0), name="positive_progression_mandate_quorum"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(issued_at__isnull=True, issued_by__isnull=True, chair__isnull=True)
                    | models.Q(
                        issued_at__isnull=False, issued_by__isnull=False, chair__isnull=False
                    )
                ),
                name="progression_mandate_issuance_attribution",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(revoked_at__isnull=True, revoked_by__isnull=True)
                    | models.Q(
                        revoked_at__isnull=False, revoked_by__isnull=False, issued_at__isnull=False
                    )
                ),
                name="progression_mandate_revocation_attribution",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} · {self.program}"


class ProgressionCommitteeMembership(models.Model):
    mandate = models.ForeignKey(
        ProgressionCommitteeMandate, on_delete=models.PROTECT, related_name="memberships"
    )
    account = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    added_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("mandate", "account"), name="unique_progression_committee_member"
            ),
        ]

    def __str__(self) -> str:
        return str(self.account)


class ProgressionCommitteeParticipation(models.Model):
    mandate = models.ForeignKey(ProgressionCommitteeMandate, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    member = models.ForeignKey(ProgressionCommitteeMembership, on_delete=models.PROTECT)
    present = models.BooleanField()
    conflict = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)
        indexes = [
            models.Index(
                fields=("mandate", "enrollment", "member", "-id"), name="progression_presence_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.member}"


class ProgressionBallot(models.Model):
    class ProposedOutcome(models.TextChoices):
        ATTAINMENT = "attainment", "Capaian kompetensi disahkan"
        APPROVED = "approved", "Kelanjutan studi disetujui"
        CONDITIONAL = "conditional", "Kelanjutan studi disetujui bersyarat"
        DEFERRED = "deferred", "Ditunda untuk bukti tambahan"

    class Result(models.TextChoices):
        ADVANCED = "advanced", "Usulan lolos"
        RETURNED = "returned", "Kembali ke pembahasan"

    mandate = models.ForeignKey(ProgressionCommitteeMandate, on_delete=models.PROTECT)
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    draft = models.ForeignKey(ProgressionReview, on_delete=models.PROTECT)
    appeal = models.ForeignKey("ProgressionAppeal", on_delete=models.PROTECT, null=True)
    proposed_outcome = models.CharField("Usulan", max_length=12, choices=ProposedOutcome.choices)
    standard = models.ForeignKey(
        "competencies.PerformanceStandardVersion", on_delete=models.PROTECT, null=True
    )
    conditions = models.TextField("Syarat atau kebutuhan bukti", max_length=4000, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )
    closed_at = models.DateTimeField(null=True)
    result = models.CharField(max_length=8, choices=Result.choices, blank=True)
    tally = models.JSONField(default=dict)

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("mandate", "enrollment"),
                condition=models.Q(closed_at__isnull=True),
                name="unique_open_progression_ballot",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(closed_at__isnull=True, closed_by__isnull=True, result="")
                    | models.Q(
                        closed_at__isnull=False,
                        closed_by__isnull=False,
                        result__in=("advanced", "returned"),
                    )
                ),
                name="valid_progression_ballot_closure",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.enrollment} · {self.get_proposed_outcome_display()}"


class ProgressionBallotComment(models.Model):
    ballot = models.ForeignKey(ProgressionBallot, on_delete=models.PROTECT, related_name="comments")
    member = models.ForeignKey(ProgressionCommitteeMembership, on_delete=models.PROTECT)
    body = models.TextField("Catatan pembahasan", max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("pk",)

    def __str__(self) -> str:
        return f"Catatan {self.pk}"


class ProgressionVote(models.Model):
    class Choice(models.TextChoices):
        APPROVE = "approve", "Setuju"
        REJECT = "reject", "Tidak setuju"
        ABSTAIN = "abstain", "Abstain"

    ballot = models.ForeignKey(ProgressionBallot, on_delete=models.PROTECT, related_name="votes")
    member = models.ForeignKey(ProgressionCommitteeMembership, on_delete=models.PROTECT)
    choice = models.CharField("Suara", max_length=7, choices=Choice.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("ballot", "member"), name="unique_progression_vote"),
        ]

    def __str__(self) -> str:
        return self.get_choice_display()


class ProgressionDecision(models.Model):
    ballot = models.OneToOneField(
        ProgressionBallot, on_delete=models.PROTECT, related_name="decision"
    )
    draft = models.ForeignKey(ProgressionReview, on_delete=models.PROTECT)
    appeal_until = models.DateTimeField(null=True)
    replaces = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, related_name="replacement"
    )
    rationale = models.TextField("Alasan keputusan", max_length=4000)
    published_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-published_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("draft",),
                condition=models.Q(replaces__isnull=True),
                name="unique_original_progression_draft",
            )
        ]

    def __str__(self) -> str:
        return str(self.ballot)


class ProgressionAppealPolicy(models.Model):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    days = models.PositiveIntegerField("Tenggat banding (hari)")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(days__gt=0), name="positive_progression_appeal_days"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.program} · {self.days} hari"


class ProgressionAppeal(models.Model):
    class Outcome(models.TextChoices):
        UPHELD = "upheld", "Keputusan dikuatkan"
        CHANGED = "changed", "Keputusan diubah"

    decision = models.OneToOneField(ProgressionDecision, on_delete=models.PROTECT)
    reason = models.TextField("Alasan banding", max_length=4000)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    mandate = models.ForeignKey(ProgressionCommitteeMandate, on_delete=models.PROTECT, null=True)
    assigned_at = models.DateTimeField(null=True)
    assigned_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )
    result_ballot = models.OneToOneField(
        ProgressionBallot, on_delete=models.PROTECT, null=True, related_name="appeal_result"
    )
    outcome = models.CharField(max_length=7, choices=Outcome.choices, blank=True)
    resolution = models.TextField("Alasan hasil banding", max_length=4000, blank=True)
    resolved_at = models.DateTimeField(null=True)
    resolved_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, related_name="+"
    )

    class Meta:
        ordering = ("-pk",)

    def __str__(self) -> str:
        return f"Banding progresi · {self.decision}"
