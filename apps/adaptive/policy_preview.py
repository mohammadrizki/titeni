from dataclasses import dataclass

from django.db.models import Count, F, Q, QuerySet
from django.utils import timezone

from apps.assessments.models import AssessmentParticipation

from .models import (
    AdaptivePolicyVersion,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvidenceEvaluation,
)
from .planning import AttemptOption, PlannedAttempt, PlanProposal, propose_attempts

ATTEMPTS = "Percobaan unik"
CONTEXTS = "Konteks unik"
SOURCES = "Sumber unik"
VERIFIERS = "Verifikator unik"
SUPPORTED = {ATTEMPTS, CONTEXTS, SOURCES, VERIFIERS}


@dataclass(frozen=True)
class EvidenceCoverage:
    gaps: dict[str, int]
    contexts: frozenset[str]
    sources: frozenset[int | None]

    @classmethod
    def from_evaluation(cls, evaluation: EvidenceEvaluation) -> "EvidenceCoverage":
        snapshot = evaluation.snapshot
        return cls(
            {
                row["label"]: max(0, row["minimum"] - row["count"])
                for row in snapshot["criteria"]
                if row["label"] in SUPPORTED
            },
            frozenset(row["context"] for row in snapshot["evidence"]),
            frozenset(row.get("source") for row in snapshot["evidence"]),
        )

    def planned_reservation(
        self,
        reservation: AttemptReservation,
        reference: str,
        *,
        participating: bool,
        can_supersede: bool,
    ) -> PlannedAttempt:
        option = reservation.slot.option
        context = option.sampling.context.strip().casefold()
        source = option.source_link.capability.source_id
        coverage = set(reservation.gap_targets) & SUPPORTED
        if context in self.contexts or not context:
            coverage.discard(CONTEXTS)
        if source in self.sources:
            coverage.discard(SOURCES)
        return PlannedAttempt(
            reference,
            AttemptOption(
                str(reservation.slot_id),
                frozenset(coverage),
                option.priority,
                1,
                distinct=((CONTEXTS, context), (SOURCES, str(source))),
            ),
            can_supersede=can_supersede,
            expected_to_contribute=not participating,
        )


def confirmed_policy_slots(
    blueprint_version_id: int, policy: AdaptivePolicyVersion
) -> QuerySet[ConfirmedAttemptSlot]:
    return ConfirmedAttemptSlot.objects.filter(
        option__policy=policy,
        option__policy__publication__isnull=False,
        event__occurred_on__gte=timezone.localdate(),
        event__component__version_id=blueprint_version_id,
        event__component_id=F("option__sampling__item_id"),
        option__policy__rule_publication__rule__standard__standard__item__version_id=(
            F("event__component__version__framework_version_id")
        ),
    )


def preview_policy(
    evaluation: EvidenceEvaluation,
    policy: AdaptivePolicyVersion,
    *,
    locked_slots: set[int] | None = None,
) -> tuple[PlanProposal, dict[str, ConfirmedAttemptSlot]]:
    evaluated = EvidenceCoverage.from_evaluation(evaluation)
    blueprint = evaluation.baseline.publication.version.blueprint_version_id
    existing_events = set(
        AssessmentParticipation.objects.filter(
            enrollment_id=evaluation.baseline.enrollment_id
        ).values_list("event_id", flat=True)
    )
    reservations = AttemptReservation.objects.filter(
        baseline_id=evaluation.baseline_id, released_at__isnull=True
    )
    same_target = reservations.filter(
        evaluation__rule__standard__standard__item_id=(evaluation.rule.standard.standard.item_id)
    )
    used_options = {
        row["slot__option_id"]: row["total"]
        for row in same_target.values("slot__option_id").annotate(total=Count("pk"))
    }
    candidates = confirmed_policy_slots(blueprint, policy)
    cutoff = evaluation.snapshot.get("reassessment_cutoff")
    if cutoff:
        candidates = candidates.filter(event__occurred_on__gt=cutoff)
        same_target = same_target.filter(event__occurred_on__gt=cutoff)
    if locked_slots is not None:
        candidates = candidates.filter(pk__in=locked_slots)
    confirmed = (
        candidates.exclude(event_id__in=existing_events)
        .exclude(event_id__in=reservations.values("event_id"))
        .annotate(booked=Count("reservations", filter=Q(reservations__released_at__isnull=True)))
        .filter(capacity__gt=F("booked"))
        .select_related("event", "option__sampling", "option__source_link__capability__source")
    )
    slots: dict[str, ConfirmedAttemptSlot] = {}
    options = []
    for slot in confirmed:
        option = slot.option
        context = option.sampling.context.strip().casefold()
        source = option.source_link.capability.source_id
        coverage = set()
        if option.adds_attempt:
            coverage.add(ATTEMPTS)
        if option.adds_context and context and context not in evaluated.contexts:
            coverage.add(CONTEXTS)
        if option.adds_source and source not in evaluated.sources:
            coverage.add(SOURCES)
        # A confirmed event does not identify an independent verifier.
        code = str(slot.pk)
        slots[code] = slot
        options.append(
            AttemptOption(
                code,
                frozenset(coverage),
                option.priority,
                slot.capacity - slot.booked,
                distinct=((CONTEXTS, context), (SOURCES, str(source))),
                limits=(
                    (f"event:{slot.event_id}", 1),
                    (
                        f"option:{option.pk}",
                        max(0, option.maximum_per_option - used_options.get(option.pk, 0)),
                    ),
                ),
            )
        )
    scheduled = tuple(
        evaluated.planned_reservation(
            reservation,
            str(reservation.event),
            participating=reservation.event_id in existing_events,
            can_supersede=False,
        )
        for reservation in same_target.filter(
            event__occurred_on__gte=timezone.localdate()
        ).select_related("slot__option__sampling", "slot__option__source_link__capability", "event")
    )
    proposal = propose_attempts(
        EvidenceEvaluation.Sufficiency(evaluation.sufficiency),
        EvidenceEvaluation.Performance(evaluation.performance),
        evaluated.gaps,
        tuple(options),
        scheduled,
        max(0, policy.maximum_attempts - sum(used_options.values())),
    )
    return proposal, slots
