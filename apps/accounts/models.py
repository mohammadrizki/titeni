import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="unique_login_email",
            )
        ]
        permissions = [
            ("access_system_workspace", "Can access the Titeni system workspace"),
        ]


class ProgramConfigurationGrant(models.Model):
    account = models.ForeignKey(User, on_delete=models.PROTECT, related_name="configuration_grants")
    program = models.ForeignKey("academics.StudyProgram", on_delete=models.PROTECT)
    starts_on = models.DateField()
    ends_on = models.DateField(blank=True, null=True)
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", null=True)
    revoked_at = models.DateTimeField(null=True)
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="program_grant_date_order",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(revoked_at__isnull=True, revoked_by__isnull=True)
                    | models.Q(revoked_at__isnull=False, revoked_by__isnull=False)
                ),
                name="program_grant_revocation_attribution",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account_id} · {self.program_id}"


class AccessRole(models.Model):
    class Scope(models.TextChoices):
        SYSTEM = "system", "Sistem"
        PROGRAM = "program", "Program studi"
        OTHER = "other", "Lainnya"

    name = models.CharField("Nama peran", unique=True, max_length=150)
    scope = models.CharField("Ruang lingkup", max_length=10, choices=Scope.choices)
    permissions = models.ManyToManyField("auth.Permission", verbose_name="Hak akses")
    updated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(scope__in=["system", "program", "other"]),
                name="valid_access_role_scope",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class UserRoleAssignment(models.Model):
    account = models.ForeignKey(User, on_delete=models.PROTECT, related_name="role_assignments")
    role = models.ForeignKey(AccessRole, on_delete=models.PROTECT, related_name="assignments")
    program = models.ForeignKey(
        "academics.StudyProgram", on_delete=models.PROTECT, null=True, blank=True
    )
    assigned_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "role", "program"],
                nulls_distinct=False,
                name="unique_scoped_user_role_assignment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.account_id} · {self.role_id}"
