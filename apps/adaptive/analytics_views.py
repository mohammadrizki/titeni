from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.academics.models import AcademicPeriod, StudyProgram
from apps.accounts.access import configurable_programs
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import PROGRAM_LEAD_ROLE

from .models import ProgramAnalyticsReport
from .program_analytics import MINIMUM_GROUP_SIZE, build_snapshot


def analytics_programs(actor: User) -> QuerySet[StudyProgram]:
    grants = UserRoleAssignment.objects.filter(
        account=actor,
        role__scope=AccessRole.Scope.PROGRAM,
        role__name__in=(PROGRAM_LEAD_ROLE, "Pengelola Kurikulum"),
        role__permissions__content_type__app_label="adaptive",
        role__permissions__codename="view_programanalyticsreport",
    ).values("program_id")
    return configurable_programs(actor).filter(pk__in=grants)


@never_cache
@login_required
@require_safe
def index(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    return render(
        request, "adaptive/program_analytics_index.html", {"programs": analytics_programs(actor)}
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def report(request: HttpRequest, program_id: int, period_id: int | None = None) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(analytics_programs(actor), pk=program_id)
    periods = AcademicPeriod.objects.filter(program=program, ends_on__lt=timezone.localdate())
    if period_id is None:
        if request.method == "POST":
            return HttpResponse(status=405, headers={"Allow": "GET, HEAD"})
        return render(
            request, "adaptive/program_analytics.html", {"program": program, "periods": periods}
        )
    if request.method == "POST":
        created = False
        with transaction.atomic():
            period = get_object_or_404(periods.select_for_update(), pk=period_id)
            if not ProgramAnalyticsReport.objects.filter(period=period).exists():
                ProgramAnalyticsReport.objects.create(
                    period=period,
                    starts_on=period.starts_on,
                    ends_on=period.ends_on,
                    minimum_group_size=MINIMUM_GROUP_SIZE,
                    snapshot=build_snapshot(period),
                    created_by=actor,
                )
                created = True
        if created:
            messages.success(request, "Laporan agregat periode ini berhasil disimpan.")
        return redirect("academics:program_analytics_period", program_id, period_id)
    period = get_object_or_404(periods, pk=period_id)
    saved = ProgramAnalyticsReport.objects.filter(period=period).first()
    return render(
        request,
        "adaptive/program_analytics.html",
        {"program": program, "period": period, "report": saved},
    )
