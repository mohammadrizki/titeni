from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.academics.models import StudyProgram
from apps.accounts.models import ProgramConfigurationGrant, User


def configurable_programs(actor: User) -> QuerySet[StudyProgram]:
    if not actor.is_active:
        return StudyProgram.objects.none()
    today = timezone.localdate()
    grants = ProgramConfigurationGrant.objects.filter(
        account=actor, starts_on__lte=today, revoked_at__isnull=True
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    return StudyProgram.objects.filter(pk__in=grants.values("program_id"))
