from collections import defaultdict

from django.utils import timezone

from apps.assessments.models import AssessmentEvent, AssessmentParticipation
from apps.evidence.models import LearnerEvidenceBaseline

from .escalations import update_escalation
from .models import (
    AdaptivePolicyPublication,
    AdaptivePolicyVersion,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvidenceEvaluation,
)
from .planning import PlanningRoute, propose_attempts
from .policy_preview import EvidenceCoverage, confirmed_policy_slots, preview_policy


def adjust_pending_reservations(
    baseline: LearnerEvidenceBaseline, evaluations: list[EvidenceEvaluation]
) -> None:
    """Adjust pending reservations after the baseline and evaluation rules are locked."""
    evaluations_by_target = {
        evaluation.rule.standard.standard.item_id: evaluation
        for evaluation in evaluations
        if evaluation.baseline_id == baseline.pk and not evaluation.rule.demonstration
    }
    if not evaluations_by_target:
        return

    by_target: defaultdict[int, list[AttemptReservation]] = defaultdict(list)
    pending = AttemptReservation.objects.filter(
        baseline=baseline,
        released_at__isnull=True,
        attempt__isnull=True,
        evaluation__rule__standard__standard__item_id__in=evaluations_by_target,
    ).select_related(
        "evaluation__rule__standard__standard",
        "slot__option__sampling",
        "slot__option__source_link__capability",
        "event",
    )
    for reservation in pending:
        by_target[reservation.evaluation.rule.standard.standard.item_id].append(reservation)
    policies: list[tuple[EvidenceEvaluation, AdaptivePolicyVersion]] = []
    blueprint_id = baseline.publication.version.blueprint_version_id
    confirmed_slots: dict[int, int] = {}
    for evaluation in evaluations_by_target.values():
        if evaluation.sufficiency == EvidenceEvaluation.Sufficiency.SUFFICIENT:
            continue
        publication = (
            AdaptivePolicyPublication.objects.filter(
                policy__rule_publication__rule_id=evaluation.rule_id
            )
            .order_by("-policy__number", "-pk")
            .select_related("policy")
            .first()
        )
        if publication is not None and publication.automatic_reservations:
            policies.append((evaluation, publication.policy))
            if evaluation.sufficiency == EvidenceEvaluation.Sufficiency.INSUFFICIENT:
                confirmed_slots.update(
                    confirmed_policy_slots(blueprint_id, publication.policy).values_list(
                        "pk", "event_id"
                    )
                )

    # Registration locks the event before writing participation. Lock in ascending order.
    event_ids = set(confirmed_slots.values()) | {
        reservation.event_id for rows in by_target.values() for reservation in rows
    }
    list(
        AssessmentEvent.objects.select_for_update()
        .filter(pk__in=event_ids)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    # Every writer locks events before slots, and takes shared locks in ascending order.
    locked_slots = set(
        ConfirmedAttemptSlot.objects.select_for_update()
        .filter(pk__in=confirmed_slots)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    started = set(
        AssessmentParticipation.objects.filter(
            enrollment_id=baseline.enrollment_id, event_id__in=event_ids
        ).values_list("event_id", flat=True)
    )
    now = timezone.now()
    today = timezone.localdate()
    releasable = []
    for target, reservations in by_target.items():
        evaluation = evaluations_by_target[target]
        enough = evaluation.sufficiency == EvidenceEvaluation.Sufficiency.SUFFICIENT
        evaluated = EvidenceCoverage.from_evaluation(evaluation)
        proposal = propose_attempts(
            EvidenceEvaluation.Sufficiency(evaluation.sufficiency),
            EvidenceEvaluation.Performance(evaluation.performance),
            evaluated.gaps,
            (),
            tuple(
                evaluated.planned_reservation(
                    reservation,
                    str(reservation.pk),
                    participating=False,
                    can_supersede=True,
                )
                for reservation in reservations
                if reservation.event_id not in started
                and (enough or reservation.event.occurred_on >= today)
            ),
            0,
        )
        superseded = set(proposal.supersede)
        for reservation in reservations:
            if str(reservation.pk) not in superseded:
                continue
            reservation.released_at = now
            reservation.released_by_id = evaluation.created_by_id
            reservation.release_evaluation = evaluation
            reservation.release_reason = (
                "Bukti sudah cukup pada evaluasi produksi terbaru."
                if enough
                else "Reservasi sudah berlebih untuk celah pada evaluasi produksi terbaru."
            )
            releasable.append(reservation)
    AttemptReservation.objects.bulk_update(
        releasable, ["released_at", "released_by", "release_evaluation", "release_reason"]
    )
    for evaluation, policy in policies:
        proposal, slots = preview_policy(evaluation, policy, locked_slots=locked_slots)
        AttemptReservation.objects.bulk_create(
            AttemptReservation(
                baseline=baseline,
                evaluation=evaluation,
                slot=slots[item.option.code],
                event_id=slots[item.option.code].event_id,
                gap_targets=list(item.targets),
                automatic=True,
                created_by_id=evaluation.created_by_id,
            )
            for item in proposal.additional
        )

        outstanding, _ = preview_policy(evaluation, policy, locked_slots=set())
        update_escalation(
            evaluation,
            policy,
            outstanding.remaining,
            needs_review=outstanding.route == PlanningRoute.REVIEW,
        )
    for evaluation in evaluations_by_target.values():
        if evaluation.sufficiency == EvidenceEvaluation.Sufficiency.SUFFICIENT:
            update_escalation(evaluation)
