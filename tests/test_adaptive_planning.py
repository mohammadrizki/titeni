import pytest

from apps.adaptive.models import EvidenceEvaluation
from apps.adaptive.planning import AttemptOption, PlannedAttempt, PlanningRoute, propose_attempts

Sufficiency = EvidenceEvaluation.Sufficiency
Performance = EvidenceEvaluation.Performance
COMBINED = AttemptOption("combined", frozenset({"context", "assessor"}), 2, 1)
CONTEXT = AttemptOption("context", frozenset({"context"}), 1, 2)


def propose(gaps, scheduled=(), limit=2):
    return propose_attempts(
        Sufficiency.INSUFFICIENT,
        Performance.UNDETERMINED,
        gaps,
        (CONTEXT, COMBINED),
        scheduled,
        limit,
    )


def test_combined_attempt_addresses_several_gaps() -> None:
    result = propose({"context": 2, "assessor": 1})
    assert [(row.option.code, row.targets) for row in result.additional] == [
        ("combined", ("assessor", "context")),
        ("context", ("context",)),
    ]
    assert result.route == PlanningRoute.ACQUIRE
    assert result.remaining == {}


def test_recalculation_reuses_pending_and_preserves_completed() -> None:
    scheduled = (
        PlannedAttempt("completed", COMBINED, False, expected_to_contribute=False),
        PlannedAttempt("targeted", COMBINED, True),
        PlannedAttempt("extra", CONTEXT, True),
    )
    result = propose({"context": 1, "assessor": 1}, scheduled)
    assert result.keep == ("completed", "targeted")
    assert result.supersede == ("extra",)
    assert not result.additional


@pytest.mark.parametrize("limit", [0, 1, 5])
def test_limit_or_unavailable_option_leaves_gap_for_review(limit: int) -> None:
    result = propose({"assessor": 2}, limit=limit)
    assert result.route == PlanningRoute.REVIEW
    assert len(result.additional) == min(limit, 1)
    assert result.remaining == {"assessor": 2 - min(limit, 1)}


def test_unclassified_gap_preserves_existing_plan_for_review() -> None:
    result = propose({}, (PlannedAttempt("pending", COMBINED, True),))
    assert result.route == PlanningRoute.REVIEW
    assert result.keep == ("pending",)
    assert not result.supersede


@pytest.mark.parametrize(
    ("performance", "route"),
    [
        (Performance.OPEN, PlanningRoute.INTERVENE),
        (Performance.CLOSED, PlanningRoute.ATTAINMENT_REVIEW),
    ],
)
def test_sufficient_evidence_stops_additional_acquisition(performance, route) -> None:
    result = propose_attempts(
        Sufficiency.SUFFICIENT,
        performance,
        {"context": 3},
        (CONTEXT,),
        (PlannedAttempt("pending", CONTEXT, True), PlannedAttempt("started", CONTEXT, False)),
        3,
    )
    assert result.route == route
    assert result.keep == ("started",)
    assert result.supersede == ("pending",)
    assert not result.additional


def test_repeated_context_and_shared_event_cannot_inflate_coverage() -> None:
    options = (
        AttemptOption(
            "morning",
            frozenset({"contexts", "attempts"}),
            1,
            3,
            distinct=(("contexts", "morning"),),
            limits=(("event:1", 1),),
        ),
        AttemptOption(
            "different-option-same-event",
            frozenset({"attempts"}),
            2,
            3,
            limits=(("event:1", 1),),
        ),
        AttemptOption(
            "same-context-another-event",
            frozenset({"contexts"}),
            3,
            3,
            distinct=(("contexts", "morning"),),
            limits=(("event:2", 1),),
        ),
    )
    result = propose_attempts(
        Sufficiency.INSUFFICIENT,
        Performance.UNDETERMINED,
        {"contexts": 2, "attempts": 2},
        options,
        (),
        3,
    )
    assert len(result.additional) == 1
    assert result.remaining == {"contexts": 1, "attempts": 1}
