import pytest

from apps.adaptive.models import EvidenceEvaluation
from apps.adaptive.performance import (
    PerformanceFinding,
    PerformanceThresholds,
    StandardFinding,
    evaluate_performance,
)

Sufficiency = EvidenceEvaluation.Sufficiency
Performance = EvidenceEvaluation.Performance


@pytest.mark.parametrize(
    ("sufficiency", "observations", "expected"),
    [
        (
            Sufficiency.INSUFFICIENT,
            [StandardFinding.BELOW],
            PerformanceFinding(Performance.UNDETERMINED, "evidence_not_sufficient"),
        ),
        (
            Sufficiency.REVIEW,
            [StandardFinding.MEETS, StandardFinding.MEETS],
            PerformanceFinding(Performance.UNDETERMINED, "evidence_not_sufficient"),
        ),
        (
            Sufficiency.SUFFICIENT,
            [],
            PerformanceFinding(Performance.UNDETERMINED, "too_few_performance_findings"),
        ),
        (
            Sufficiency.SUFFICIENT,
            [StandardFinding.BELOW],
            PerformanceFinding(Performance.OPEN, "below_standard"),
        ),
        (
            Sufficiency.SUFFICIENT,
            [StandardFinding.MEETS],
            PerformanceFinding(Performance.UNDETERMINED, "too_few_performance_findings"),
        ),
        (
            Sufficiency.SUFFICIENT,
            [StandardFinding.MEETS, StandardFinding.MEETS],
            PerformanceFinding(Performance.CLOSED, "meets_standard"),
        ),
        (
            Sufficiency.SUFFICIENT,
            [StandardFinding.BELOW, StandardFinding.MEETS, StandardFinding.MEETS],
            PerformanceFinding(Performance.UNDETERMINED, "conflicting_findings"),
        ),
    ],
)
def test_interpret_synthetic_performance(
    sufficiency: Sufficiency, observations: list[StandardFinding], expected: PerformanceFinding
) -> None:
    rule = PerformanceThresholds(minimum_below=1, minimum_meets=2)
    assert evaluate_performance(sufficiency, enumerate(observations), rule) == expected


def test_demonstration_rule_rejects_zero_threshold() -> None:
    with pytest.raises(ValueError, match="lebih besar dari nol"):
        PerformanceThresholds(minimum_below=0, minimum_meets=2)


def test_attempt_deduplication_keeps_conflicts_visible() -> None:
    rule = PerformanceThresholds(minimum_below=1, minimum_meets=2)
    meets = (1, StandardFinding.MEETS)
    below = (1, StandardFinding.BELOW)
    assert evaluate_performance(Sufficiency.SUFFICIENT, [meets, meets], rule) == (
        PerformanceFinding(Performance.UNDETERMINED, "too_few_performance_findings")
    )
    assert evaluate_performance(Sufficiency.SUFFICIENT, [meets, below], rule) == (
        PerformanceFinding(Performance.UNDETERMINED, "conflicting_findings")
    )
