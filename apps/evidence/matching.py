from dataclasses import dataclass
from typing import Any

from apps.evidence.models import EvidencePlacement, EvidenceRecord, LearnerEvidenceBaseline


@dataclass(frozen=True)
class Requirement:
    number: int
    origin: str
    entry: dict[str, Any]

    @property
    def label(self) -> str:
        return (
            self.entry.get("label") or self.entry.get("component") or f"Persyaratan {self.number}"
        )

    @property
    def minimum(self) -> int:
        return self.entry.get("minimum", self.entry.get("minimum_observations", 0))


@dataclass(frozen=True)
class Match:
    requirement: Requirement
    automatic: bool


def match(record: EvidenceRecord, requirement: Requirement) -> Match | None:
    entry = requirement.entry
    capability_id = record.source_link.capability_id
    if requirement.origin == "manual":
        expected_capability = entry.get("capability_id")
        if expected_capability is None or expected_capability == capability_id:
            return Match(requirement, automatic=False)
        return None

    component_id = entry.get("component_id")
    source_ids = {
        source["capability_id"]
        for source in entry.get("sources", [])
        if source.get("capability_id")
    }
    if component_id is not None and component_id != record.source_link.item_id:
        return None
    if source_ids and capability_id not in source_ids:
        return None
    expected_context = entry.get("context", "").strip().casefold()
    observed_context = record.context.strip().casefold()
    if expected_context and observed_context and expected_context != observed_context:
        return None
    automatic = bool(component_id and source_ids and expected_context and observed_context)
    return Match(requirement, automatic=automatic)


def candidates(record: EvidenceRecord, requirements: list[Requirement]) -> list[Match]:
    return [candidate for requirement in requirements if (candidate := match(record, requirement))]


def baseline_requirements(baseline: LearnerEvidenceBaseline) -> list[Requirement]:
    return [
        Requirement(number, row["origin"], row["entry"])
        for number, row in enumerate(baseline.publication.requirements, start=1)
    ]


def resolve_placement(
    record: EvidenceRecord, baseline: LearnerEvidenceBaseline, choices: list[Match]
) -> tuple[Requirement | None, EvidencePlacement | None]:
    placement = getattr(record, "placement", None)
    chosen = next(
        (
            choice
            for choice in choices
            if placement is not None
            and placement.baseline_id == baseline.pk
            and choice.requirement.number == placement.requirement_number
        ),
        None,
    )
    if chosen is not None:
        return chosen.requirement, placement
    if len(choices) == 1 and choices[0].automatic:
        return choices[0].requirement, None
    return None, None
