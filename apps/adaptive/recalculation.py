from django.db import transaction

from apps.accounts.models import User
from apps.evidence.models import EvidenceRecord, LearnerEvidenceBaseline

from .automatic_adjustment import adjust_pending_reservations
from .fulfillment import refresh_fulfillment
from .models import (
    AttemptReservation,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
)
from .services import persist_evaluation, preview


@transaction.atomic
def reevaluate_for_evidence(
    record: EvidenceRecord, actor: User, trigger: EvidenceEvaluation.Trigger
) -> None:
    participation = record.attempt.participation
    baseline = (
        LearnerEvidenceBaseline.objects.select_for_update()
        .filter(
            enrollment_id=participation.enrollment_id,
            publication__artifact_map__program_id=(
                participation.event.component.version.blueprint.program_id
            ),
        )
        .first()
    )
    if baseline is None:
        return

    reservation = (
        AttemptReservation.objects.filter(
            baseline=baseline, attempt_id=record.attempt_id, released_at__isnull=True
        )
        .select_related("slot__option__sampling")
        .first()
    )
    if reservation is not None:
        refresh_fulfillment(reservation, actor, trigger=record)

    target = "rule__standard__standard__item_id"
    current = (
        EvidenceEvaluation.objects.filter(
            baseline=baseline, rule__demonstration=False, rule__publication__isnull=False
        )
        .order_by(target, "-pk")
        .distinct(target)
    )
    updated = []
    for evaluation in sorted(current, key=lambda item: item.rule_id):
        rule = EvaluationRuleVersion.objects.select_for_update().get(pk=evaluation.rule_id)
        if EvaluationRuleRetirement.objects.filter(rule=rule).exists():
            continue
        snapshot = preview(baseline, rule)
        if snapshot != evaluation.snapshot:
            evaluation = persist_evaluation(
                baseline, rule, actor, snapshot, trigger=trigger, trigger_record=record
            )
            updated.append(evaluation)
    adjust_pending_reservations(baseline, updated)
