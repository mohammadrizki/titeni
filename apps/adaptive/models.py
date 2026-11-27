from django.conf import settings
from django.db import models
from django.db.models import Q


class EvaluationRuleVersion(models.Model):
    standard = models.ForeignKey(
        "competencies.PerformanceStandardVersion", on_delete=models.PROTECT
    )
    number = models.PositiveIntegerField()
    minimum_attempts = models.PositiveIntegerField()
    minimum_contexts = models.PositiveIntegerField()
    minimum_verifiers = models.PositiveIntegerField()
    minimum_sources = models.PositiveIntegerField(null=True, blank=True)
    maximum_age_days = models.PositiveIntegerField(null=True, blank=True)
    demonstration = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["standard_id", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["standard", "number"], name="unique_evaluation_rule_version"
            ),
            models.CheckConstraint(
                condition=Q(
                    number__gt=0,
                    minimum_attempts__gt=0,
                    minimum_contexts__gt=0,
                    minimum_verifiers__gt=0,
                ),
                name="positive_evaluation_rule_parameters",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(minimum_sources__isnull=True) | Q(minimum_sources__gt=0))
                    & (Q(maximum_age_days__isnull=True) | Q(maximum_age_days__gt=0))
                ),
                name="positive_optional_evaluation_parameters",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.standard} · Aturan {self.number}"


class EvidenceEvaluation(models.Model):
    class Sufficiency(models.TextChoices):
        INSUFFICIENT = "insufficient", "Belum cukup"
        SUFFICIENT = "sufficient", "Cukup"
        REVIEW = "review", "Perlu ditinjau"

    class Performance(models.TextChoices):
        UNDETERMINED = "undetermined", "Belum ditentukan"
        OPEN = "open", "Terbuka"
        CLOSED = "closed", "Tertutup"

    class Trigger(models.TextChoices):
        MANUAL = "manual", "Dicatat manual"
        VERIFICATION = "verification", "Verifikasi bukti"
        EVIDENCE_CORRECTION = "evidence_correction", "Koreksi bukti"
        INVALIDATION = "invalidation", "Pembatalan bukti"
        PLACEMENT = "placement", "Penempatan bukti"
        FINDING = "finding", "Temuan asesor"
        FINDING_CORRECTION = "finding_correction", "Koreksi temuan asesor"

    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.MANUAL)
    trigger_record = models.ForeignKey(
        "evidence.EvidenceRecord",
        on_delete=models.PROTECT,
        null=True,
        related_name="triggered_evaluations",
    )
    baseline = models.ForeignKey("evidence.LearnerEvidenceBaseline", on_delete=models.PROTECT)
    rule = models.ForeignKey(EvaluationRuleVersion, on_delete=models.PROTECT)
    evidence = models.ManyToManyField("evidence.EvidenceRecord", through="EvaluationEvidence")
    sufficiency = models.CharField(max_length=12, choices=Sufficiency.choices)
    performance = models.CharField(max_length=12, choices=Performance.choices)
    snapshot = models.JSONField()
    engine_version = models.PositiveSmallIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(sufficiency__in=["insufficient", "sufficient", "review"]),
                name="valid_evaluation_sufficiency",
            ),
            models.CheckConstraint(
                condition=Q(performance="undetermined")
                | Q(sufficiency="sufficient", performance__in=["open", "closed"]),
                name="evaluation_performance_requires_sufficiency",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rule} · {self.get_sufficiency_display()}"


class EvaluationEvidence(models.Model):
    evaluation = models.ForeignKey(EvidenceEvaluation, on_delete=models.PROTECT)
    record = models.ForeignKey("evidence.EvidenceRecord", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evaluation", "record"], name="unique_evaluation_record"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.evaluation_id} · Bukti {self.record_id}"


class EvaluationRuleRetirement(models.Model):
    rule = models.OneToOneField(
        EvaluationRuleVersion, on_delete=models.PROTECT, related_name="retirement"
    )
    reason = models.CharField(max_length=500)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(reason=""), name="required_evaluation_rule_retirement_reason"
            ),
        ]

    def __str__(self) -> str:
        return str(self.rule)


class EvaluationRulePublication(models.Model):
    rule = models.OneToOneField(
        EvaluationRuleVersion, on_delete=models.PROTECT, related_name="publication"
    )
    minimum_below = models.PositiveIntegerField()
    minimum_meets = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(minimum_below__gt=0, minimum_meets__gt=0),
                name="positive_publication_performance_thresholds",
            ),
        ]

    def __str__(self) -> str:
        return str(self.rule)


class AssessorFindingAssignment(models.Model):
    record = models.ForeignKey("evidence.EvidenceRecord", on_delete=models.PROTECT)
    standard = models.ForeignKey(
        "competencies.PerformanceStandardVersion", on_delete=models.PROTECT
    )
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["record", "standard", "assessor"], name="unique_assessor_finding_assignment"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.record} · {self.standard}"


class AssessorFinding(models.Model):
    class Outcome(models.TextChoices):
        BELOW = "below", "Di bawah standar"
        MEETS = "meets", "Memenuhi standar"

    assignment = models.OneToOneField(
        AssessorFindingAssignment, on_delete=models.PROTECT, related_name="finding"
    )
    outcome = models.CharField(max_length=5, choices=Outcome.choices)
    rationale = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(outcome__in=["below", "meets"]) & ~Q(rationale=""),
                name="valid_assessor_standard_finding",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.assignment} · {self.get_outcome_display()}"


class AssessorFindingRevision(models.Model):
    finding = models.ForeignKey(AssessorFinding, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=5, choices=AssessorFinding.Outcome.choices)
    rationale = models.CharField(max_length=500)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["finding", "number"], name="unique_assessor_finding_revision"
            ),
            models.CheckConstraint(
                condition=(
                    Q(number__gt=1, outcome__in=["below", "meets"])
                    & ~Q(rationale="")
                    & ~Q(reason="")
                ),
                name="valid_assessor_finding_revision",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.finding.assignment} · Versi {self.number}"


class AdaptivePolicyVersion(models.Model):
    rule_publication = models.ForeignKey(EvaluationRulePublication, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    maximum_attempts = models.PositiveIntegerField()
    review_within_days = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["rule_publication_id", "-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["rule_publication", "number"], name="unique_adaptive_policy_version"
            ),
            models.CheckConstraint(
                condition=Q(number__gt=0, review_within_days__gt=0),
                name="valid_adaptive_policy_version_parameters",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.rule_publication.rule} · Kebijakan {self.number}"


class AdaptiveAttemptOption(models.Model):
    policy = models.ForeignKey(
        AdaptivePolicyVersion, on_delete=models.PROTECT, related_name="options"
    )
    sampling = models.ForeignKey("assessments.AssessmentSamplingRule", on_delete=models.PROTECT)
    source_link = models.ForeignKey(
        "assessments.BlueprintItemEvidenceSource", on_delete=models.PROTECT
    )
    priority = models.PositiveIntegerField()
    maximum_per_option = models.PositiveIntegerField()
    adds_attempt = models.BooleanField(default=False)
    adds_context = models.BooleanField(default=False)
    adds_source = models.BooleanField(default=False)
    adds_verifier = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "sampling", "source_link"], name="unique_adaptive_option_mapping"
            ),
            models.CheckConstraint(
                condition=(
                    Q(priority__gt=0, maximum_per_option__gt=0)
                    & (
                        Q(adds_attempt=True)
                        | Q(adds_context=True)
                        | Q(adds_source=True)
                        | Q(adds_verifier=True)
                    )
                ),
                name="valid_adaptive_option_parameters",
            ),
        ]

    def __str__(self) -> str:
        return str(self.sampling)


class AdaptivePolicyPublication(models.Model):
    policy = models.OneToOneField(
        AdaptivePolicyVersion, on_delete=models.PROTECT, related_name="publication"
    )
    automatic_reservations = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return str(self.policy)


class ConfirmedAttemptSlot(models.Model):
    option = models.ForeignKey(
        AdaptiveAttemptOption, on_delete=models.PROTECT, related_name="confirmed_slots"
    )
    event = models.ForeignKey("assessments.AssessmentEvent", on_delete=models.PROTECT)
    capacity = models.PositiveIntegerField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event__occurred_on", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["option", "event"], name="unique_confirmed_adaptive_slot"
            ),
            models.CheckConstraint(
                condition=Q(capacity__gt=0), name="positive_confirmed_adaptive_slot_capacity"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.option} · {self.event}"


class AttemptReservation(models.Model):
    baseline = models.ForeignKey("evidence.LearnerEvidenceBaseline", on_delete=models.PROTECT)
    evaluation = models.ForeignKey(EvidenceEvaluation, on_delete=models.PROTECT)
    slot = models.ForeignKey(
        ConfirmedAttemptSlot, on_delete=models.PROTECT, related_name="reservations"
    )
    event = models.ForeignKey("assessments.AssessmentEvent", on_delete=models.PROTECT)
    gap_targets = models.JSONField()
    automatic = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    attempt = models.OneToOneField(
        "assessments.AssessmentAttempt",
        on_delete=models.PROTECT,
        null=True,
        related_name="adaptive_reservation",
    )
    linked_at = models.DateTimeField(null=True)
    linked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    released_at = models.DateTimeField(null=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+"
    )
    release_reason = models.CharField(max_length=500, blank=True)
    release_evaluation = models.ForeignKey(
        EvidenceEvaluation,
        on_delete=models.PROTECT,
        null=True,
        related_name="released_reservations",
    )

    class Meta:
        permissions = [
            ("release_attemptreservation", "Can release a reserved attempt slot"),
            ("link_attemptreservation", "Can link a recorded attempt to a reservation"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(attempt__isnull=True, linked_at__isnull=True, linked_by__isnull=True)
                    | Q(
                        attempt__isnull=False,
                        linked_at__isnull=False,
                        linked_by__isnull=False,
                        released_at__isnull=True,
                    )
                ),
                name="valid_adaptive_reservation_attempt_link",
            ),
            models.UniqueConstraint(
                fields=["baseline", "event"],
                condition=Q(released_at__isnull=True),
                name="unique_active_adaptive_reservation_for_event",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        released_at__isnull=True,
                        released_by__isnull=True,
                        release_reason="",
                        release_evaluation__isnull=True,
                    )
                    | (
                        Q(released_at__isnull=False, released_by__isnull=False)
                        & ~Q(release_reason="")
                    )
                ),
                name="valid_adaptive_reservation_release",
            ),
        ]

    def __str__(self) -> str:
        return str(self.slot)


class AttemptFulfillmentCheck(models.Model):
    reservation = models.ForeignKey(
        AttemptReservation, on_delete=models.PROTECT, related_name="fulfillment_checks"
    )
    supporting_record = models.ForeignKey(
        "evidence.EvidenceRecord",
        on_delete=models.PROTECT,
        null=True,
        related_name="supporting_attempt_fulfillments",
    )
    trigger_record = models.ForeignKey(
        "evidence.EvidenceRecord",
        on_delete=models.PROTECT,
        null=True,
        related_name="triggered_attempt_fulfillments",
    )
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]

    def __str__(self) -> str:
        return "Terpenuhi" if self.supporting_record_id else "Menunggu bukti yang memenuhi syarat"


class ScheduledAssessorAssignment(models.Model):
    reservation = models.ForeignKey(
        AttemptReservation, on_delete=models.PROTECT, related_name="scheduling_assignments"
    )
    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=500)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(reason=""), name="required_scheduled_assessor_assignment_reason"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reservation} · {self.assessor}"


class AdaptiveEscalation(models.Model):
    baseline = models.ForeignKey("evidence.LearnerEvidenceBaseline", on_delete=models.PROTECT)
    target = models.ForeignKey("competencies.CompetencyItem", on_delete=models.PROTECT)
    policy = models.ForeignKey(AdaptivePolicyVersion, on_delete=models.PROTECT)
    opened_by_evaluation = models.ForeignKey(EvidenceEvaluation, on_delete=models.PROTECT)
    latest_evaluation = models.ForeignKey(
        EvidenceEvaluation, on_delete=models.PROTECT, related_name="+"
    )
    remaining = models.JSONField(default=dict)
    due_on = models.DateField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    reviewed_at = models.DateTimeField(null=True)
    review_note = models.CharField(max_length=500, blank=True)
    closed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["baseline", "target"],
                condition=Q(closed_at__isnull=True),
                name="unique_open_escalation_per_target",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.target} · {self.due_on}"
