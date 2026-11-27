from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, QuerySet, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.accounts.models import User

from .committees import WORKSPACE, active_mandates
from .models import (
    EPACommitteeMandate,
    EPACommitteeParticipation,
    EPAReviewAssignment,
)


def committee_cases(mandate: EPACommitteeMandate) -> QuerySet[EPAReviewAssignment]:
    activities = mandate.scopes.filter(activity__program_id=mandate.program_id).values(
        "activity_id"
    )
    return (
        EPAReviewAssignment.objects.filter(
            publication__version__activity_id__in=activities,
            enrollment__cohort__period__program_id=mandate.program_id,
            drafts__isnull=False,
        )
        .order_by("publication_id", "enrollment_id", "pk")
        .distinct("publication_id", "enrollment_id")
        .select_related(
            "publication__version__activity", "enrollment__learner__account", "enrollment__cohort"
        )
    )


class ParticipationForm(forms.Form):
    present = forms.TypedChoiceField(
        label="Kehadiran",
        choices=(("1", "Hadir"), ("0", "Tidak hadir")),
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
    )
    conflict = forms.TypedChoiceField(
        label="Konflik kepentingan pada kasus ini",
        choices=(("0", "Tidak memiliki konflik"), ("1", "Memiliki konflik")),
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
    )


def current_participation(
    mandate: EPACommitteeMandate, publication_id: int, enrollment_id: int
) -> QuerySet[EPACommitteeParticipation]:
    records = EPACommitteeParticipation.objects.filter(
        mandate=mandate, publication_id=publication_id, enrollment_id=enrollment_id
    )
    latest = records.filter(created_by_id=OuterRef("created_by_id")).values("pk")[:1]
    return records.filter(pk=Subquery(latest))


def eligible_participants(
    mandate: EPACommitteeMandate, publication_id: int, enrollment_id: int
) -> QuerySet[EPACommitteeParticipation]:
    if (
        not committee_cases(mandate)
        .filter(publication_id=publication_id, enrollment_id=enrollment_id)
        .exists()
    ):
        return EPACommitteeParticipation.objects.none()
    now = timezone.now()
    today = timezone.localdate(now)
    valid_member_ids = mandate.memberships.filter(
        account__is_active=True,
        mandate__starts_on__lte=today,
        mandate__ends_on__gte=today,
        mandate__issued_at__lte=now,
        mandate__revoked_at__isnull=True,
    ).values("account_id")
    return current_participation(mandate, publication_id, enrollment_id).filter(
        created_by_id__in=valid_member_ids,
        present=True,
        conflict=False,
    )


def quorum_count(mandate: EPACommitteeMandate, publication_id: int, enrollment_id: int) -> int:
    return eligible_participants(mandate, publication_id, enrollment_id).count()


@never_cache
@login_required
@require_safe
def mandates(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    return render(
        request,
        "epa/participation_mandates.html",
        {"mandates": active_mandates(actor).select_related("program")},
    )


@never_cache
@login_required
@require_safe
def cases(request: HttpRequest, mandate_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    mandate = get_object_or_404(active_mandates(actor), pk=mandate_id)
    page = Paginator(committee_cases(mandate), 25).get_page(request.GET.get("page"))
    return render(request, "epa/participation_cases.html", {"mandate": mandate, "page": page})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def participate(
    request: HttpRequest, mandate_id: int, publication_id: int, enrollment_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    eligible = active_mandates(actor)
    mandate = get_object_or_404(eligible, pk=mandate_id)
    case_filter = {"publication_id": publication_id, "enrollment_id": enrollment_id}
    case = get_object_or_404(committee_cases(mandate), **case_filter)
    own_history = EPACommitteeParticipation.objects.filter(
        mandate=mandate, created_by=actor, **case_filter
    )
    previous = own_history.first()
    writing = request.method == "POST"
    form = ParticipationForm(
        request.POST if writing else None,
        initial={"present": int(previous.present), "conflict": int(previous.conflict)}
        if previous is not None
        else None,
    )
    if writing and form.is_valid():
        with transaction.atomic():
            get_object_or_404(eligible.select_for_update(of=("self",)), pk=mandate_id)
            previous = own_history.first()
            values = form.cleaned_data
            if previous is None or (
                previous.present != values["present"] or previous.conflict != values["conflict"]
            ):
                own_history.create(mandate=mandate, created_by=actor, **case_filter, **values)
            return redirect("epa_participate", mandate_id, publication_id, enrollment_id)
    return render(
        request,
        "epa/participation_case.html",
        {
            "mandate": mandate,
            "case": case,
            "form": form,
            "previous": previous,
            "quorum": quorum_count(mandate, publication_id, enrollment_id),
            "can_discuss": previous is not None and previous.present and not previous.conflict,
        },
        status=400 if writing else 200,
    )


@never_cache
@login_required
@permission_required((WORKSPACE, "epa.view_epacommitteeparticipation"), raise_exception=True)
@require_safe
def audit(request: HttpRequest, mandate_id: int) -> HttpResponse:
    mandate = get_object_or_404(
        EPACommitteeMandate.objects.select_related("program"), pk=mandate_id
    )
    records = EPACommitteeParticipation.objects.filter(mandate=mandate).select_related(
        "publication__version__activity",
        "enrollment__learner__account",
        "enrollment__cohort",
        "created_by",
    )
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "epa/participation_audit.html", {"mandate": mandate, "page": page})
