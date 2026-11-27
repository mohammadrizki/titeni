from dataclasses import dataclass
from datetime import date

from django.db.models import QuerySet

from apps.evidence.models import EvidenceRecord

from .models import ReflectionRevision


@dataclass(frozen=True)
class EvidenceSummaryRow:
    reference: str
    revision: int
    occurred_on: date
    component: str
    source: str
    evidence_type: str
    context: str
    eligible: bool


@dataclass(frozen=True)
class EvidenceSummary:
    revision: int
    eligible_count: int
    attempt_count: int
    rows: tuple[EvidenceSummaryRow, ...]


def summarize_evidence(
    revision: ReflectionRevision,
    owned_evidence: QuerySet[EvidenceRecord],
    candidates: QuerySet[EvidenceRecord],
) -> EvidenceSummary:
    linked = (
        revision.evidence.filter(pk__in=owned_evidence)
        .select_related(
            "attempt__participation__event__component",
            "source_link__capability__source",
            "source_link__capability__evidence_type",
        )
        .order_by("-attempt__participation__event__occurred_on", "pk")
    )
    records = list(linked)
    eligible = set(
        candidates.filter(pk__in=[record.pk for record in records]).values_list("pk", flat=True)
    )
    rows = []
    attempts = set()
    for record in records:
        event = record.attempt.participation.event
        capability = record.source_link.capability
        if record.pk in eligible:
            attempts.add(record.attempt_id)
        rows.append(
            EvidenceSummaryRow(
                reference=record.reference,
                revision=record.revision_number,
                occurred_on=event.occurred_on,
                component=event.component.name,
                source=capability.source.name,
                evidence_type=capability.evidence_type.name,
                context=record.context,
                eligible=record.pk in eligible,
            )
        )
    return EvidenceSummary(revision.number, len(eligible), len(attempts), tuple(rows))
