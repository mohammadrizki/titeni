from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from .models import EvidenceEvaluation


class PlanningRoute(StrEnum):
    ACQUIRE = "acquire"
    REVIEW = "review"
    INTERVENE = "intervene"
    ATTAINMENT_REVIEW = "attainment_review"


@dataclass(frozen=True)
class AttemptOption:
    code: str
    addresses: frozenset[str]
    priority: int
    available: int
    distinct: tuple[tuple[str, str], ...] = ()
    limits: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class PlannedAttempt:
    reference: str
    option: AttemptOption
    can_supersede: bool
    expected_to_contribute: bool = True


@dataclass(frozen=True)
class AdditionalAttemptProposal:
    option: AttemptOption
    targets: tuple[str, ...]


@dataclass(frozen=True)
class PlanProposal:
    route: PlanningRoute
    keep: tuple[str, ...]
    supersede: tuple[str, ...]
    additional: tuple[AdditionalAttemptProposal, ...]
    remaining: dict[str, int]


def propose_attempts(
    sufficiency: EvidenceEvaluation.Sufficiency,
    performance: EvidenceEvaluation.Performance,
    gaps: dict[str, int],
    options: tuple[AttemptOption, ...],
    scheduled: tuple[PlannedAttempt, ...],
    maximum_new: int,
) -> PlanProposal:
    """Propose changes to unperformed requirements; preserve protected attempts."""
    if maximum_new < 0 or any(amount < 0 for amount in gaps.values()):
        raise ValueError("Jumlah celah dan batas percobaan harus nol atau lebih.")
    if len({option.code for option in options}) != len(options):
        raise ValueError("Kode opsi percobaan harus unik.")
    if any(option.available < 0 for option in options):
        raise ValueError("Ketersediaan opsi harus nol atau lebih.")

    evaluation = EvidenceEvaluation
    if sufficiency == evaluation.Sufficiency.SUFFICIENT:
        route = {
            evaluation.Performance.OPEN: PlanningRoute.INTERVENE,
            evaluation.Performance.CLOSED: PlanningRoute.ATTAINMENT_REVIEW,
            evaluation.Performance.UNDETERMINED: PlanningRoute.REVIEW,
        }[performance]
        return PlanProposal(
            route,
            tuple(attempt.reference for attempt in scheduled if not attempt.can_supersede),
            tuple(attempt.reference for attempt in scheduled if attempt.can_supersede),
            (),
            {},
        )
    if sufficiency != evaluation.Sufficiency.INSUFFICIENT or not any(gaps.values()):
        return PlanProposal(PlanningRoute.REVIEW, tuple(a.reference for a in scheduled), (), (), {})

    outstanding = {gap: amount for gap, amount in gaps.items() if amount}
    keep = []
    supersede = []
    additional = []

    used_distinct: set[tuple[str, str]] = set()

    def covered(option: AttemptOption) -> set[str]:
        repeated = {gap for gap, key in option.distinct if (gap, key) in used_distinct}
        return (outstanding.keys() & option.addresses) - repeated

    def allocate(option: AttemptOption, coverage: set[str]) -> None:
        used_distinct.update((gap, key) for gap, key in option.distinct if gap in coverage)
        for gap in coverage:
            outstanding[gap] -= 1
            if outstanding[gap] == 0:
                del outstanding[gap]

    # Use protected attempts first, then retain the pending option that covers the most gaps.
    mutable = []
    for attempt in scheduled:
        if attempt.can_supersede:
            mutable.append(attempt)
        else:
            keep.append(attempt.reference)
            if attempt.expected_to_contribute:
                allocate(attempt.option, covered(attempt.option))

    def scheduled_coverage(attempt: PlannedAttempt) -> set[str]:
        return covered(attempt.option) if attempt.expected_to_contribute else set()

    while mutable:
        attempt = min(
            mutable,
            key=lambda item: (-len(scheduled_coverage(item)), item.option.priority, item.reference),
        )
        mutable.remove(attempt)
        coverage = scheduled_coverage(attempt)
        if coverage:
            keep.append(attempt.reference)
            allocate(attempt.option, coverage)
        else:
            supersede.append(attempt.reference)

    used: Counter[str] = Counter()
    grouped: Counter[str] = Counter()
    for _ in range(maximum_new):
        eligible = (
            option
            for option in options
            if used[option.code] < option.available
            and all(grouped[key] < limit for key, limit in option.limits)
            and covered(option)
        )
        option = min(
            eligible,
            key=lambda item: (-len(covered(item)), item.priority, item.code),
            default=None,
        )
        if option is None:
            break
        coverage = covered(option)
        additional.append(AdditionalAttemptProposal(option, tuple(sorted(coverage))))
        used[option.code] += 1
        grouped.update(key for key, _ in option.limits)
        allocate(option, coverage)

    route = PlanningRoute.REVIEW if outstanding else PlanningRoute.ACQUIRE
    return PlanProposal(route, tuple(keep), tuple(supersede), tuple(additional), outstanding)
