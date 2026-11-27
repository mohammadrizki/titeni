from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.accounts.models import User

from .committees import WORKSPACE
from .decisions import lock_chair_ballot, redirect_to_discussion
from .models import (
    EntrustmentDecision,
    EPAAppeal,
    EPACommitteeBallot,
    EPACommitteeMandate,
    EPACommitteeParticipation,
)

ASSIGN_APPEAL = "epa.change_epaappeal"


class AppealMandateForm(forms.Form):
    mandate = forms.ModelChoiceField(
        label="Komite banding", queryset=EPACommitteeMandate.objects.none()
    )


class ResolutionForm(forms.Form):
    reason = forms.CharField(label="Alasan hasil banding", max_length=4000, widget=forms.Textarea)


def independent_mandates(appeal: EPAAppeal):
    decision = appeal.decision
    ballot = decision.ballot
    participated = EPACommitteeParticipation.objects.filter(
        pk__in=[row["declaration"] for row in ballot.result.get("participants", [])]
    ).values("created_by_id")
    involved = {
        decision.created_by_id,
        ballot.created_by_id,
        ballot.closed_by_id,
        ballot.draft.created_by_id,
    } - {None}
    now = timezone.now()
    today = timezone.localdate(now)
    return (
        EPACommitteeMandate.objects.filter(
            program_id=ballot.mandate.program_id,
            scopes__activity_id=ballot.publication.version.activity_id,
            starts_on__lte=today,
            ends_on__gte=today,
            issued_at__lte=now,
            revoked_at__isnull=True,
            chair__member__account__is_active=True,
        )
        .exclude(pk=ballot.mandate_id)
        .exclude(
            pk__in=EPACommitteeBallot.objects.filter(
                publication_id=ballot.publication_id,
                enrollment_id=ballot.enrollment_id,
                created_at__lt=appeal.assigned_at or now,
            ).values("mandate_id")
        )
        .exclude(memberships__account_id__in=involved)
        .exclude(memberships__account_id__in=participated)
        .exclude(memberships__account_id__in=ballot.votes.values("created_by_id"))
        .exclude(memberships__account_id__in=ballot.comments.values("created_by_id"))
    )


@never_cache
@login_required
@permission_required((WORKSPACE, ASSIGN_APPEAL), raise_exception=True)
@require_safe
def queue(request: HttpRequest) -> HttpResponse:
    appeals = EPAAppeal.objects.select_related(
        "decision__ballot__publication__version__activity",
        "decision__ballot__enrollment__learner__account",
        "decision__ballot__enrollment__cohort",
        "mandate",
    )
    return render(request, "epa/appeals.html", {"appeals": appeals})


@never_cache
@login_required
@permission_required((WORKSPACE, ASSIGN_APPEAL), raise_exception=True)
@require_http_methods(["GET", "POST"])
def assign(request: HttpRequest, appeal_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    appeal = get_object_or_404(EPAAppeal, pk=appeal_id)
    writing = request.method == "POST"
    form = AppealMandateForm(request.POST if writing else None)
    cast(forms.ModelChoiceField, form.fields["mandate"]).queryset = independent_mandates(appeal)
    if writing and form.is_valid():
        mandate = form.cleaned_data["mandate"]
        with transaction.atomic():
            get_object_or_404(
                independent_mandates(appeal).select_for_update(of=("self",)), pk=mandate.pk
            )
            appeal = get_object_or_404(EPAAppeal.objects.select_for_update(), pk=appeal_id)
            if appeal.mandate_id is not None and appeal.mandate_id != mandate.pk:
                return HttpResponse("Komite banding sudah ditunjuk.", status=409)
            if appeal.mandate_id is None:
                appeal.mandate, appeal.assigned_by, appeal.assigned_at = (
                    mandate,
                    actor,
                    timezone.now(),
                )
                appeal.save(update_fields=("mandate", "assigned_by", "assigned_at"))
            return redirect("accounts:epa_assign_appeal", appeal_id)
    return render(
        request,
        "epa/appeal_assignment.html",
        {"appeal": appeal, "form": form},
        status=400 if writing else 200,
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_POST
def resolve(request: HttpRequest, ballot_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    ballot = get_object_or_404(EPACommitteeBallot, pk=ballot_id)
    form = ResolutionForm(request.POST)
    with transaction.atomic():
        ballot = lock_chair_ballot(actor, ballot)
        appeal = get_object_or_404(
            EPAAppeal.objects.select_for_update(of=("self",)).filter(
                mandate_id=ballot.mandate_id,
                decision__ballot__publication_id=ballot.publication_id,
                decision__ballot__enrollment_id=ballot.enrollment_id,
                assigned_at__lte=ballot.created_at,
            ),
        )
        if not independent_mandates(appeal).filter(pk=ballot.mandate_id).exists():
            raise PermissionDenied
        if appeal.resolved_at is not None:
            if appeal.result_ballot_id == ballot.pk:
                return redirect_to_discussion(ballot)
            return HttpResponse("Hasil banding sudah tercatat.", status=409)
        if not form.is_valid():
            return HttpResponse(
                "Alasan hasil banding wajib diisi dan maksimal 4000 karakter.", status=400
            )
        changed = ballot.level.pk != appeal.decision.ballot.level.pk
        if changed:
            EntrustmentDecision.objects.create(
                ballot=ballot, replaces=appeal.decision, created_by=actor
            )
        appeal.result_ballot = ballot
        appeal.outcome = EPAAppeal.Outcome.CHANGED if changed else EPAAppeal.Outcome.UPHELD
        appeal.resolution = form.cleaned_data["reason"]
        appeal.resolved_at, appeal.resolved_by = timezone.now(), actor
        appeal.save(
            update_fields=("result_ballot", "outcome", "resolution", "resolved_at", "resolved_by")
        )
    return redirect_to_discussion(ballot)
