from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.models import AssessmentAttempt, AssessmentEvent, AssessmentParticipation
from apps.evidence.models import LearnerEvidenceBaseline

from .fulfillment import refresh_fulfillment
from .models import (
    AdaptivePolicyVersion,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
)
from .policy_preview import preview_policy

RESERVE_PERMISSION = "adaptive.add_attemptreservation"
RELEASE_PERMISSION = "adaptive.release_attemptreservation"
LINK_PERMISSION = "adaptive.link_attemptreservation"


@transaction.atomic
def reserve_attempt(
    evaluation: EvidenceEvaluation,
    policy: AdaptivePolicyVersion,
    slot_id: int,
    actor: User,
) -> AttemptReservation:
    baseline = LearnerEvidenceBaseline.objects.select_for_update().get(pk=evaluation.baseline_id)
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        RESERVE_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied
    rule = EvaluationRuleVersion.objects.select_for_update().get(pk=evaluation.rule_id)
    slot = ConfirmedAttemptSlot.objects.filter(pk=slot_id, option__policy=policy).first()
    if (
        slot is None
        or policy.rule_publication.rule_id != rule.pk
        or not hasattr(policy, "publication")
    ):
        raise ValidationError("Pilih slot terkonfirmasi dari versi kebijakan terbit.")

    # Attempt registration uses the same event lock.
    AssessmentEvent.objects.select_for_update().get(pk=slot.event_id)
    ConfirmedAttemptSlot.objects.select_for_update().get(pk=slot.pk)
    prior = AttemptReservation.objects.filter(
        baseline_id=evaluation.baseline_id, event_id=slot.event_id, released_at__isnull=True
    ).first()
    if prior is not None and prior.slot_id == slot.pk and prior.evaluation_id == evaluation.pk:
        return prior

    latest = (
        EvidenceEvaluation.objects.filter(
            baseline_id=evaluation.baseline_id,
            rule__demonstration=False,
            rule__standard__standard__item_id=rule.standard.standard.item_id,
        )
        .order_by("-pk")
        .first()
    )
    if latest != evaluation or EvaluationRuleRetirement.objects.filter(rule=rule).exists():
        raise ValidationError("Gunakan evaluasi terbaru dengan aturan aktif.")

    proposal, _ = preview_policy(evaluation, policy)
    selection = next((row for row in proposal.additional if row.option.code == str(slot.pk)), None)
    if selection is None:
        raise ValidationError("Slot tidak lagi tersedia dalam usulan. Periksa kembali pratinjau.")

    return AttemptReservation.objects.create(
        baseline_id=evaluation.baseline_id,
        evaluation=evaluation,
        slot=slot,
        event_id=slot.event_id,
        gap_targets=list(selection.targets),
        created_by=actor,
    )


@transaction.atomic
def release_attempt(reservation: AttemptReservation, actor: User, reason: str) -> None:
    baseline = LearnerEvidenceBaseline.objects.select_for_update().get(pk=reservation.baseline_id)
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        RELEASE_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied

    reservation = AttemptReservation.objects.get(pk=reservation.pk)
    if reservation.released_at is not None:
        return
    reason = reason.strip()
    if not 0 < len(reason) <= 500:
        raise ValidationError("Isi alasan pelepasan hingga 500 karakter.")

    AssessmentEvent.objects.select_for_update().get(pk=reservation.event_id)
    if (
        reservation.attempt_id is not None
        or AssessmentParticipation.objects.filter(
            event_id=reservation.event_id,
            enrollment_id=baseline.enrollment_id,
        ).exists()
    ):
        raise ValidationError("Reservasi sudah terkait dengan partisipasi asesmen.")
    reservation.released_at = timezone.now()
    reservation.released_by = actor
    reservation.release_reason = reason
    reservation.save(update_fields=["released_at", "released_by", "release_reason"])


@transaction.atomic
def link_attempt(reservation: AttemptReservation, attempt_id: int, actor: User) -> None:
    baseline = LearnerEvidenceBaseline.objects.select_for_update().get(pk=reservation.baseline_id)
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        LINK_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied
    reservation = AttemptReservation.objects.get(pk=reservation.pk)
    if reservation.released_at is not None:
        raise ValidationError("Reservasi ini sudah dilepas.")
    if reservation.attempt_id is not None:
        if reservation.attempt_id == attempt_id:
            return
        raise ValidationError("Reservasi sudah tertaut ke percobaan lain.")

    AssessmentEvent.objects.select_for_update().get(pk=reservation.event_id)
    attempt = AssessmentAttempt.objects.filter(
        pk=attempt_id,
        participation__event_id=reservation.event_id,
        participation__enrollment_id=baseline.enrollment_id,
        participation__event__component__version__blueprint__program_id=program_id,
    ).first()
    if attempt is None:
        raise ValidationError("Pilih percobaan mahasiswa ini pada pelaksanaan yang direservasi.")
    if AttemptReservation.objects.filter(attempt=attempt).exists():
        raise ValidationError("Percobaan ini sudah tertaut ke reservasi lain.")
    reservation.attempt = attempt
    reservation.linked_at = timezone.now()
    reservation.linked_by = actor
    reservation.save(update_fields=["attempt", "linked_at", "linked_by"])
    refresh_fulfillment(reservation, actor)
