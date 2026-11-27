from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User
from apps.assessments.models import AssessmentEvent, AssessmentParticipation
from apps.evidence.models import LearnerEvidenceBaseline

from .findings import ASSESSOR_PERMISSION
from .models import AttemptReservation, ScheduledAssessorAssignment

SCHEDULE_PERMISSION = "adaptive.add_scheduledassessorassignment"


def eligible_assessors(program_id: int) -> QuerySet[User]:
    today = timezone.localdate()
    grants = ProgramConfigurationGrant.objects.filter(
        program_id=program_id, starts_on__lte=today, revoked_at__isnull=True
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    return (
        User.objects.filter(
            pk__in=grants.values("account_id"),
            is_active=True,
            role_assignments__program_id=program_id,
            role_assignments__role__scope=AccessRole.Scope.PROGRAM,
            role_assignments__role__permissions__content_type__app_label="adaptive",
            role_assignments__role__permissions__codename=ASSESSOR_PERMISSION.split(".")[1],
        )
        .distinct()
        .order_by("username")
    )


@transaction.atomic
def assign_scheduled_assessor(
    reservation: AttemptReservation, actor: User, assessor_id: UUID, reason: str, previous_id: int
) -> None:
    baseline = LearnerEvidenceBaseline.objects.select_for_update().get(pk=reservation.baseline_id)
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        SCHEDULE_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied
    reservation = AttemptReservation.objects.get(pk=reservation.pk)
    event = AssessmentEvent.objects.select_for_update().get(pk=reservation.event_id)
    if (
        reservation.released_at is not None
        or reservation.attempt_id is not None
        or event.occurred_on < timezone.localdate()
        or AssessmentParticipation.objects.filter(
            event=event, enrollment_id=baseline.enrollment_id
        ).exists()
    ):
        raise ValidationError("Penugasan hanya tersedia sebelum partisipasi pada reservasi aktif.")

    reason = reason.strip()
    if not 0 < len(reason) <= 500:
        raise ValidationError("Isi alasan penugasan hingga 500 karakter.")
    assessor = eligible_assessors(program_id).filter(pk=assessor_id).first()
    if assessor is None:
        raise ValidationError("Pilih asesor dengan akses dan penugasan aktif pada prodi ini.")

    latest = reservation.scheduling_assignments.first()
    if latest is not None and latest.assessor_id == assessor.pk and latest.reason == reason:
        return
    if previous_id != (latest.pk if latest else 0):
        raise ValidationError("Penugasan sudah berubah. Tinjau penugasan terkini.")
    ScheduledAssessorAssignment.objects.create(
        reservation=reservation, assessor=assessor, assigned_by=actor, reason=reason
    )
