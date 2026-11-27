from datetime import timedelta
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import F, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from apps.academics.models import StudyProgram
from apps.accounts.models import User

from .models import (
    ProgressionAppeal,
    ProgressionAppealPolicy,
    ProgressionBallot,
    ProgressionCommitteeMandate,
    ProgressionCommitteeParticipation,
    ProgressionDecision,
)
from .progression_committees import WORKSPACE

POLICY = "learning.add_progressionappealpolicy"
ASSIGN = "learning.change_progressionappeal"


class PolicyForm(forms.ModelForm):
    days = forms.IntegerField(label="Tenggat banding (hari)", min_value=1, max_value=3650)

    class Meta:
        model = ProgressionAppealPolicy
        fields = ("program", "days")
        labels = {"program": "Program studi"}


class AppealForm(forms.ModelForm):
    class Meta:
        model = ProgressionAppeal
        fields = ("reason",)


class MandateForm(forms.Form):
    mandate = forms.ModelChoiceField(
        label="Komite banding", queryset=ProgressionCommitteeMandate.objects.none()
    )


def independent_mandates(appeal: ProgressionAppeal) -> QuerySet[ProgressionCommitteeMandate]:
    decision = appeal.decision
    ballot = decision.ballot
    declarations = ProgressionCommitteeParticipation.objects.filter(
        pk__in=[row["declaration"] for row in ballot.tally.get("participants", [])]
    ).values("member__account_id")
    authors = {
        decision.published_by_id,
        ballot.created_by_id,
        ballot.closed_by_id,
        decision.draft.created_by_id,
        decision.draft.assignment.reviewer_id,
    } - {None}
    now = timezone.now()
    today = timezone.localdate(now)
    return (
        ProgressionCommitteeMandate.objects.filter(
            program_id=ballot.mandate.program_id,
            starts_on__lte=today,
            ends_on__gte=today,
            issued_at__lte=now,
            revoked_at__isnull=True,
            chair__account__is_active=True,
            chair__mandate_id=F("pk"),
        )
        .exclude(pk=ballot.mandate_id)
        .exclude(memberships__account_id__in=authors)
        .exclude(memberships__account_id__in=declarations)
        .exclude(memberships__account_id__in=ballot.votes.values("member__account_id"))
        .exclude(memberships__account_id__in=ballot.comments.values("member__account_id"))
    )


@never_cache
@login_required
@permission_required((WORKSPACE, POLICY), raise_exception=True)
@require_http_methods(["GET", "POST"])
def policies(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    writing = request.method == "POST"
    form = PolicyForm(request.POST if writing else None)
    if writing and form.is_valid():
        with transaction.atomic():
            program = StudyProgram.objects.select_for_update().get(
                pk=form.cleaned_data["program"].pk
            )
            previous = ProgressionAppealPolicy.objects.filter(program=program).first()
            days = form.cleaned_data["days"]
            if previous is None or previous.days != days:
                ProgressionAppealPolicy.objects.create(program=program, days=days, created_by=actor)
            if previous is None:
                ProgressionDecision.objects.filter(
                    ballot__enrollment__cohort__period__program=program,
                    replaces__isnull=True,
                    appeal_until__isnull=True,
                ).update(appeal_until=F("published_at") + timedelta(days=days))
        return redirect("accounts:progression_appeal_policies")
    current = ProgressionAppealPolicy.objects.order_by("program_id", "-pk").distinct("program_id")
    return render(
        request,
        "learning/progression_appeal_admin.html",
        {"policy_form": form, "policies": current.select_related("program", "created_by")},
        status=400 if writing else 200,
    )


@never_cache
@login_required
@permission_required((WORKSPACE, ASSIGN), raise_exception=True)
@require_safe
def queue(request: HttpRequest) -> HttpResponse:
    appeals = ProgressionAppeal.objects.select_related(
        "decision__ballot__enrollment__learner__account",
        "decision__ballot__enrollment__cohort",
        "mandate",
    )
    return render(request, "learning/progression_appeal_admin.html", {"appeals": appeals})


@never_cache
@login_required
@permission_required((WORKSPACE, ASSIGN), raise_exception=True)
@require_http_methods(["GET", "POST"])
def assign(request: HttpRequest, appeal_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    appeal = get_object_or_404(ProgressionAppeal, pk=appeal_id)
    writing = request.method == "POST"
    form = MandateForm(request.POST if writing else None)
    cast(forms.ModelChoiceField, form.fields["mandate"]).queryset = independent_mandates(appeal)
    if writing and form.is_valid():
        with transaction.atomic():
            mandate = get_object_or_404(
                independent_mandates(appeal).select_for_update(of=("self",)),
                pk=form.cleaned_data["mandate"].pk,
            )
            appeal = get_object_or_404(ProgressionAppeal.objects.select_for_update(), pk=appeal_id)
            if appeal.mandate_id is not None and appeal.mandate_id != mandate.pk:
                return HttpResponse("Komite banding sudah ditunjuk.", status=409)
            if appeal.mandate_id is None:
                appeal.mandate, appeal.assigned_at, appeal.assigned_by = (
                    mandate,
                    timezone.now(),
                    actor,
                )
                appeal.save(update_fields=("mandate", "assigned_at", "assigned_by"))
            return redirect("accounts:assign_progression_appeal", appeal_id)
    return render(
        request,
        "learning/progression_appeal_admin.html",
        {"appeal": appeal, "assign_form": form},
        status=400 if writing else 200,
    )


def resolve_appeal(ballot: ProgressionBallot, actor: User, rationale: str) -> str:
    appeal = get_object_or_404(
        ProgressionAppeal.objects.select_for_update(of=("self",)),
        pk=ballot.appeal_id,
        mandate_id=ballot.mandate_id,
        decision__ballot__enrollment_id=ballot.enrollment_id,
        assigned_at__lte=ballot.created_at,
    )
    if not independent_mandates(appeal).filter(pk=ballot.mandate_id).exists():
        return "Mandat banding sudah tidak memenuhi syarat."
    if appeal.resolved_at is not None:
        return "" if appeal.result_ballot_id == ballot.pk else "Banding sudah diputuskan."
    original = appeal.decision.ballot
    changed = (ballot.proposed_outcome, ballot.standard_id, ballot.conditions) != (
        original.proposed_outcome,
        original.standard_id,
        original.conditions,
    )
    if changed:
        ProgressionDecision.objects.create(
            ballot=ballot,
            draft=ballot.draft,
            replaces=appeal.decision,
            published_by=actor,
            rationale=rationale,
        )
    appeal.result_ballot = ballot
    appeal.outcome = (
        ProgressionAppeal.Outcome.CHANGED if changed else ProgressionAppeal.Outcome.UPHELD
    )
    appeal.resolution = rationale
    appeal.resolved_at, appeal.resolved_by = timezone.now(), actor
    appeal.save(
        update_fields=("result_ballot", "outcome", "resolution", "resolved_at", "resolved_by")
    )
    return ""
