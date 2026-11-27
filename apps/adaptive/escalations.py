from datetime import timedelta

from django.utils import timezone

from .models import AdaptiveEscalation, AdaptivePolicyVersion, EvidenceEvaluation


def update_escalation(
    evaluation: EvidenceEvaluation,
    policy: AdaptivePolicyVersion | None = None,
    remaining: dict[str, int] | None = None,
    *,
    needs_review: bool = False,
) -> None:
    """Called under the baseline lock after reservation changes."""
    target_id = evaluation.rule.standard.standard.item_id
    active = AdaptiveEscalation.objects.filter(
        baseline_id=evaluation.baseline_id, target_id=target_id, closed_at__isnull=True
    )
    if needs_review and policy is not None:
        case, created = active.get_or_create(
            defaults={
                "baseline_id": evaluation.baseline_id,
                "target_id": target_id,
                "policy": policy,
                "opened_by_evaluation": evaluation,
                "latest_evaluation": evaluation,
                "remaining": remaining or {},
                "due_on": timezone.localdate() + timedelta(days=policy.review_within_days),
            },
        )
        if not created:
            active.update(latest_evaluation=evaluation, remaining=remaining or {})
    else:
        active.update(latest_evaluation=evaluation, closed_at=timezone.now())
