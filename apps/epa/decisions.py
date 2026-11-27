from datetime import timedelta
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.academics.models import StudyProgram
from apps.accounts.models import User

from .committees import WORKSPACE, active_mandates
from .models import (
    EntrustableProfessionalActivity,
    EntrustmentDecision,
    EPAAppeal,
    EPAAppealPolicy,
    EPACommitteeBallot,
    EPACommitteeChair,
)
from .observations import program_grants
from .participation import eligible_participants

VIEW_DECISION = "view_entrustmentdecision"
ADD_APPEAL = "add_epaappeal"
POLICY_PERMISSION = "epa.add_epaappealpolicy"


def own_decisions(actor: User, permission: str = VIEW_DECISION) -> QuerySet[EntrustmentDecision]:
    programs = program_grants("Mahasiswa", permission).filter(account=actor).values("program_id")
    return EntrustmentDecision.objects.filter(
        ballot__enrollment__learner__account=actor,
        ballot__enrollment__cohort__period__program_id__in=programs,
    ).select_related(
        "ballot__publication__version__activity",
        "ballot__draft__level__version__scale",
        "ballot__proposed_level__version__scale",
        "ballot__enrollment__learner__account",
        "created_by",
        "replaces",
        "epaappeal",
        "replacement",
    )


class PolicyForm(forms.ModelForm):
    days = forms.IntegerField(label="Tenggat banding (hari)", min_value=1, max_value=3650)

    class Meta:
        model = EPAAppealPolicy
        fields = ("program", "days")
        labels = {"program": "Program studi"}


class AppealForm(forms.ModelForm):
    class Meta:
        model = EPAAppeal
        fields = ("reason",)


@never_cache
@login_required
@permission_required((WORKSPACE, POLICY_PERMISSION), raise_exception=True)
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
            previous = EPAAppealPolicy.objects.filter(program=program).first()
            if previous is None or previous.days != form.cleaned_data["days"]:
                item = form.save(commit=False)
                item.created_by = actor
                item.save()
        return redirect("accounts:epa_appeal_policies")
    latest = EPAAppealPolicy.objects.order_by("program_id", "-pk").distinct("program_id")
    return render(
        request,
        "epa/appeal_policies.html",
        {"form": form, "policies": latest.select_related("program", "created_by")},
        status=400 if writing else 200,
    )


def lock_chair_ballot(actor: User, ballot: EPACommitteeBallot) -> EPACommitteeBallot:
    get_object_or_404(active_mandates(actor).select_for_update(of=("self",)), pk=ballot.mandate_id)
    if not EPACommitteeChair.objects.filter(
        mandate_id=ballot.mandate_id, member__account=actor, member__mandate_id=ballot.mandate_id
    ).exists():
        raise PermissionDenied
    if (
        not eligible_participants(ballot.mandate, ballot.publication_id, ballot.enrollment_id)
        .filter(created_by=actor)
        .exists()
    ):
        raise PermissionDenied
    return get_object_or_404(
        EPACommitteeBallot.objects.select_for_update().filter(
            outcome=EPACommitteeBallot.Outcome.ADVANCED, closed_at__isnull=False
        ),
        pk=ballot.pk,
    )


@never_cache
@login_required
@require_POST
def publish(request: HttpRequest, ballot_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    ballot = get_object_or_404(
        EPACommitteeBallot.objects.select_related("publication__version__activity"), pk=ballot_id
    )
    with transaction.atomic():
        # Serialize publications of the same EPA across distinct mandates.
        activity = EntrustableProfessionalActivity.objects.select_for_update().get(
            pk=ballot.publication.version.activity_id
        )
        ballot = lock_chair_ballot(actor, ballot)
        initial = EntrustmentDecision.objects.filter(
            ballot__publication_id=ballot.publication_id,
            ballot__enrollment_id=ballot.enrollment_id,
            replaces__isnull=True,
        ).first()
        if initial is not None:
            if initial.ballot_id == ballot.pk:
                return redirect_to_discussion(ballot)
            return HttpResponse("Kasus sudah memiliki keputusan awal.", status=409)
        policy = EPAAppealPolicy.objects.filter(program_id=activity.program_id).first()
        if policy is None:
            return HttpResponse("Fakultas perlu menetapkan tenggat banding prodi.", status=409)
        now = timezone.now()
        EntrustmentDecision.objects.create(
            ballot=ballot, created_by=actor, appeal_until=now + timedelta(days=policy.days)
        )
    return redirect_to_discussion(ballot)


def redirect_to_discussion(ballot: EPACommitteeBallot) -> HttpResponse:
    return redirect(
        "epa_committee_discussion", ballot.mandate_id, ballot.publication_id, ballot.enrollment_id
    )


@never_cache
@login_required
@require_safe
def student_decisions(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "epa/student_decisions.html",
        {"decisions": own_decisions(cast(User, request.user))},
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def student_decision(request: HttpRequest, decision_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    decisions = own_decisions(actor)
    decision = get_object_or_404(decisions, pk=decision_id)
    writing = request.method == "POST"
    form = AppealForm(request.POST if writing else None)
    allowed = own_decisions(actor, ADD_APPEAL).filter(pk=decision_id).exists()
    if writing:
        if not allowed:
            raise PermissionDenied
        with transaction.atomic():
            decision = get_object_or_404(decisions.select_for_update(of=("self",)), pk=decision_id)
            if EPAAppeal.objects.filter(decision=decision).exists():
                return redirect("epa_student_decision", decision_id)
            if decision.appeal_until is None or timezone.now() > decision.appeal_until:
                return HttpResponse(
                    "Tenggat banding telah berakhir atau tidak berlaku.", status=409
                )
            if form.is_valid():
                appeal = form.save(commit=False)
                appeal.decision, appeal.created_by = decision, actor
                appeal.save()
                return redirect("epa_student_decision", decision_id)
    appeal = getattr(decision, "epaappeal", None)
    can_appeal = (
        allowed
        and appeal is None
        and decision.appeal_until is not None
        and timezone.now() <= decision.appeal_until
    )
    return render(
        request,
        "epa/student_decision.html",
        {
            "decision": decision,
            "appeal": appeal,
            "form": form if can_appeal else None,
            "evidence": decision.ballot.draft.evidence.select_related("level"),
        },
        status=400 if writing else 200,
    )
