from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .models import EvidenceEvaluation


class StandardFinding(StrEnum):
    BELOW = "below"
    MEETS = "meets"


@dataclass(frozen=True)
class PerformanceThresholds:
    minimum_below: int
    minimum_meets: int

    def __post_init__(self) -> None:
        if min(self.minimum_below, self.minimum_meets) < 1:
            raise ValueError("Ambang performa harus lebih besar dari nol.")


@dataclass(frozen=True)
class PerformanceFinding:
    status: EvidenceEvaluation.Performance
    reason: str


def evaluate_performance(
    sufficiency: EvidenceEvaluation.Sufficiency,
    findings_by_attempt: Iterable[tuple[int, StandardFinding]],
    rule: PerformanceThresholds,
) -> PerformanceFinding:
    """Evaluate findings already interpreted against one version of a standard."""
    performance = EvidenceEvaluation.Performance
    if sufficiency != EvidenceEvaluation.Sufficiency.SUFFICIENT:
        return PerformanceFinding(performance.UNDETERMINED, "evidence_not_sufficient")

    below_attempts: set[int] = set()
    meets_attempts: set[int] = set()
    for attempt, finding in findings_by_attempt:
        (below_attempts if finding == StandardFinding.BELOW else meets_attempts).add(attempt)
    below, meets = len(below_attempts), len(meets_attempts)
    if below and meets:
        return PerformanceFinding(performance.UNDETERMINED, "conflicting_findings")
    if below >= rule.minimum_below:
        return PerformanceFinding(performance.OPEN, "below_standard")
    if meets >= rule.minimum_meets:
        return PerformanceFinding(performance.CLOSED, "meets_standard")
    return PerformanceFinding(performance.UNDETERMINED, "too_few_performance_findings")
