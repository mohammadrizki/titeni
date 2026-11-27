from apps.accounts.models import User
from apps.evidence.models import EvidenceRecord

from .models import AttemptFulfillmentCheck, AttemptReservation

VIEW_FULFILLMENT = "adaptive.view_attemptfulfillmentcheck"


def refresh_fulfillment(
    reservation: AttemptReservation, actor: User, trigger: EvidenceRecord | None = None
) -> None:
    """Record a changed finding while the caller holds the learner baseline lock."""
    if reservation.attempt_id is None or reservation.released_at is not None:
        return
    option = reservation.slot.option
    context = option.sampling.context.strip().casefold()
    records = (
        EvidenceRecord.objects.eligible_for_reconciliation()
        .filter(attempt_id=reservation.attempt_id, source_link_id=option.source_link_id)
        .order_by("pk")
        .values_list("pk", "context")
    )
    supporting_id = next(
        (
            record_id
            for record_id, value in records.iterator()
            if value.strip().casefold() == context
        ),
        None,
    )
    prior = reservation.fulfillment_checks.first()
    if prior is None or prior.supporting_record_id != supporting_id:
        AttemptFulfillmentCheck.objects.create(
            reservation=reservation,
            supporting_record_id=supporting_id,
            trigger_record=trigger,
            checked_by=actor,
        )
