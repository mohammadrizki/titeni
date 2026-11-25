from django.contrib.auth.models import Permission
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.academics.models import StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User


def configurable_programs(actor: User) -> QuerySet[StudyProgram]:
    if not actor.is_active:
        return StudyProgram.objects.none()
    today = timezone.localdate()
    grants = ProgramConfigurationGrant.objects.filter(
        account=actor, starts_on__lte=today, revoked_at__isnull=True
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    return StudyProgram.objects.filter(pk__in=grants.values("program_id"))


def program_role_permissions(actor: User, program_id: int) -> set[str]:
    if not actor.is_active:
        return set()
    permissions = Permission.objects.filter(
        accessrole__scope=AccessRole.Scope.PROGRAM,
        accessrole__assignments__account=actor,
        accessrole__assignments__program_id=program_id,
    ).values_list("content_type__app_label", "codename")
    return {f"{app}.{codename}" for app, codename in permissions}
