from django.db import models


class Reflection(models.Model):
    enrollment = models.ForeignKey("academics.LearnerEnrollment", on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pk"]

    def __str__(self) -> str:
        return f"Refleksi {self.pk}"


class ReflectionRevision(models.Model):
    reflection = models.ForeignKey(Reflection, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    body = models.TextField(max_length=10000)
    evidence = models.ManyToManyField("evidence.EvidenceRecord", blank=True)
    competencies = models.ManyToManyField(
        "competencies.CompetencyItem", through="ReflectionCompetency", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(
                fields=["reflection", "number"], name="unique_reflection_revision"
            ),
            models.CheckConstraint(
                condition=models.Q(number__gt=0) & ~models.Q(body=""),
                name="valid_reflection_revision",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reflection} · {self.number}"


class ReflectionCompetency(models.Model):
    revision = models.ForeignKey(ReflectionRevision, on_delete=models.PROTECT)
    competency = models.ForeignKey("competencies.CompetencyItem", on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "competency"], name="unique_reflection_revision_competency"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.revision} · {self.competency}"


class ReflectionPrompt(models.Model):
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    text = models.CharField("Pemantik", max_length=400)
    position = models.PositiveIntegerField("Urutan", default=10)
    is_active = models.BooleanField("Aktif", default=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "text"], name="unique_reflection_prompt_per_program"
            ),
            models.CheckConstraint(
                condition=models.Q(position__gt=0) & ~models.Q(text=""),
                name="valid_reflection_prompt",
            ),
        ]

    def __str__(self) -> str:
        return self.text


class ReflectionAdvisorAssignment(models.Model):
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
                fields=["enrollment", "advisor"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_reflection_advisor",
            ),
        ]

    def __str__(self) -> str:
        return str(self.advisor)


class ReflectionShare(models.Model):
    revision = models.ForeignKey(ReflectionRevision, on_delete=models.PROTECT)
    assignment = models.ForeignKey(ReflectionAdvisorAssignment, on_delete=models.PROTECT)
    shared_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "assignment"],
                condition=models.Q(revoked_at__isnull=True),
                name="unique_active_reflection_share",
            ),
        ]

    def __str__(self) -> str:
        return str(self.revision)


class ReflectionCoachingMessage(models.Model):
    share = models.ForeignKey(ReflectionShare, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(body=""), name="nonempty_coaching_message")
        ]

    def __str__(self) -> str:
        return f"Pesan coaching {self.pk}"


class CoachingRecommendation(models.Model):
    share = models.ForeignKey(
        ReflectionShare, on_delete=models.PROTECT, related_name="recommendations"
    )
    author = models.ForeignKey("accounts.User", on_delete=models.PROTECT)
    body = models.TextField(max_length=4000)
    due_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    completion_note = models.TextField(max_length=4000, blank=True)

    class Meta:
        ordering = ["pk"]
        permissions = [("complete_coachingrecommendation", "Can record coaching follow-up")]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(body="")
                & (
                    models.Q(completed_at__isnull=True, completion_note="")
                    | (models.Q(completed_at__isnull=False) & ~models.Q(completion_note=""))
                ),
                name="valid_coaching_recommendation",
            )
        ]

    def __str__(self) -> str:
        return f"Rekomendasi coaching {self.pk}"
