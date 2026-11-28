from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from django.db.models import F, Q
from django.utils import timezone

from apps.academics.models import AcademicPeriod

from .models import AttemptReservation, EvidenceEvaluation

MINIMUM_GROUP_SIZE = 5


def day_start(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_default_timezone())


def publishable(groups: Counter, total: int) -> bool:
    return total >= MINIMUM_GROUP_SIZE and all(
        count >= MINIMUM_GROUP_SIZE for count in groups.values()
    )


def competency_rows(period: AcademicPeriod, cutoff: datetime) -> list[dict]:
    item = "rule__standard__standard__item"
    enrollment = "baseline__enrollment"
    latest = (
        EvidenceEvaluation.objects.filter(
            baseline__enrollment__cohort__period=period,
            baseline__enrollment__enrolled_on__lte=period.ends_on,
            baseline__publication__artifact_map__program_id=period.program_id,
            baseline__publication__version__blueprint_version__blueprint__program_id=period.program_id,
            baseline__publication__version__blueprint_version__framework_version__framework__program_id=period.program_id,
            rule__standard__standard__item__version_id=F(
                "baseline__publication__version__blueprint_version__framework_version_id"
            ),
            rule__demonstration=False,
            rule__publication__created_at__lte=F("created_at"),
            created_at__lt=cutoff,
        )
        .filter(Q(rule__retirement__isnull=True) | Q(rule__retirement__created_at__gte=cutoff))
        .order_by(f"{enrollment}__learner_id", f"{item}_id", "-created_at", "-pk")
        .distinct(f"{enrollment}__learner_id", f"{item}_id")
        .values_list(
            f"{item}_id",
            f"{item}__version__number",
            f"{item}__code",
            f"{item}__name",
            "sufficiency",
            "performance",
        )
    )
    labels = {}
    groups: dict[int, Counter] = defaultdict(Counter)
    for item_id, version, code, name, sufficiency, performance in latest.iterator():
        labels[item_id] = (version, code, name)
        groups[item_id][sufficiency, performance] += 1

    rows = []
    for item_id in sorted(groups, key=labels.__getitem__):
        counts = groups[item_id]
        evaluated = sum(counts.values())
        if not publishable(counts, evaluated):
            continue
        version, code, name = labels[item_id]
        rows.append(
            {
                "version": version,
                "code": code,
                "name": name,
                "evaluated": evaluated,
                "insufficient": sum(
                    count
                    for (sufficiency, _), count in counts.items()
                    if sufficiency == EvidenceEvaluation.Sufficiency.INSUFFICIENT
                ),
                "performance_known": sum(
                    count
                    for (_, performance), count in counts.items()
                    if performance
                    in {EvidenceEvaluation.Performance.OPEN, EvidenceEvaluation.Performance.CLOSED}
                ),
                "open": counts[
                    EvidenceEvaluation.Sufficiency.SUFFICIENT, EvidenceEvaluation.Performance.OPEN
                ],
            }
        )
    return rows


def burden_row(period: AcademicPeriod, start: datetime, cutoff: datetime) -> dict[str, int]:
    reservations = (
        AttemptReservation.objects.filter(
            baseline__enrollment__cohort__period=period,
            baseline__enrollment__enrolled_on__lte=period.ends_on,
            baseline__publication__artifact_map__program_id=period.program_id,
            evaluation__baseline_id=F("baseline_id"),
            evaluation__rule__demonstration=False,
            evaluation__rule__publication__created_at__lte=F("evaluation__created_at"),
            event__component__version__blueprint__program_id=period.program_id,
            created_at__gte=start,
            created_at__lt=cutoff,
        )
        .order_by()
        .values_list("baseline__enrollment__learner_id", "linked_at", "released_at")
    )
    totals: Counter[str] = Counter()
    learner_counts: dict[int, Counter[str]] = defaultdict(Counter)
    for learner_id, linked_at, released_at in reservations.iterator():
        if linked_at is not None and linked_at < cutoff:
            status = "linked"
        elif released_at is not None and released_at < cutoff:
            status = "released"
        else:
            status = "reserved"
        totals[status] += 1
        learner_counts[learner_id][status] += 1

    contributors = len(learner_counts)
    # Showing both people and events can expose a single repeat participant.
    groups = Counter(
        (counts["linked"], counts["released"], counts["reserved"])
        for counts in learner_counts.values()
    )
    if not publishable(groups, contributors):
        return {}
    return {
        "learners": contributors,
        "total": sum(totals.values()),
        "linked": totals["linked"],
        "released": totals["released"],
        "reserved": totals["reserved"],
    }


def build_snapshot(period: AcademicPeriod) -> dict:
    start = day_start(period.starts_on)
    cutoff = day_start(period.ends_on + timedelta(days=1))
    return {
        "competencies": competency_rows(period, cutoff),
        "burden": burden_row(period, start, cutoff),
    }
