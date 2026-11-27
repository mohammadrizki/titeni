from django.db.models import Subquery

from apps.adaptive.models import EvidenceEvaluation
from apps.evidence.models import LearnerEvidenceBaseline

TARGET_FIELD = "rule__standard__standard__item_id"


def current_intervention_evaluations(baseline: LearnerEvidenceBaseline) -> set[int]:
    latest = (
        EvidenceEvaluation.objects.filter(
            baseline=baseline, rule__demonstration=False, rule__publication__isnull=False
        )
        .order_by(TARGET_FIELD, "-pk")
        .distinct(TARGET_FIELD)
        .values("pk")
    )
    return set(
        EvidenceEvaluation.objects.filter(
            pk__in=Subquery(latest),
            rule__retirement__isnull=True,
            sufficiency=EvidenceEvaluation.Sufficiency.SUFFICIENT,
            performance=EvidenceEvaluation.Performance.OPEN,
        ).values_list("pk", flat=True)
    )
