from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe

from apps.accounts.models import User

from .committees import WORKSPACE, active_mandates
from .models import (
    EntrustmentDecision,
    EntrustmentReview,
    EPAAppeal,
    EPACommitteeBallot,
    EPACommitteeChair,
    EPACommitteeComment,
    EPACommitteeMandate,
    EPACommitteeMembership,
    EPACommitteeVote,
    SupervisionLevel,
)
from .participation import committee_cases, eligible_participants

ASSIGN_CHAIR = "epa.add_epacommitteechair"
AUDIT_BALLOTS = "epa.view_epacommitteeballot"


class ChairForm(forms.Form):
    member = forms.ModelChoiceField(
        label="Ketua komite", queryset=EPACommitteeMembership.objects.none()
    )


class ProposalChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: EntrustmentReview) -> str:
        return f"{obj.created_by} · Draf {obj.number} · {obj.level}"


class ProposalForm(forms.Form):
    draft = ProposalChoiceField(label="Draf rekomendasi", queryset=EntrustmentReview.objects.none())


class AppealProposalForm(ProposalForm):
    level = forms.ModelChoiceField(
        label="Tingkat supervisi usulan banding", queryset=SupervisionLevel.objects.none()
    )
    rationale = forms.CharField(
        label="Alasan usulan banding", max_length=4000, widget=forms.Textarea
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = EPACommitteeComment
        fields = ("body",)


class VoteForm(forms.ModelForm):
    class Meta:
        model = EPACommitteeVote
        fields = ("choice",)


@never_cache
@login_required
@permission_required((WORKSPACE, ASSIGN_CHAIR), raise_exception=True)
@require_http_methods(["GET", "POST"])
def chair(request: HttpRequest, mandate_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    mandate = get_object_or_404(EPACommitteeMandate, pk=mandate_id)
    writing = request.method == "POST"
    form = ChairForm(request.POST if writing else None)
    cast(forms.ModelChoiceField, form.fields["member"]).queryset = mandate.memberships.filter(
        account__is_active=True
    ).select_related("account")
    if writing:
        with transaction.atomic():
            mandate = get_object_or_404(
                EPACommitteeMandate.objects.select_for_update(), pk=mandate_id
            )
            if (
                mandate.issued_at is None
                or mandate.revoked_at is not None
                or mandate.ends_on < timezone.localdate()
            ):
                return HttpResponse("Mandat harus sudah ditetapkan dan masih berlaku.", status=409)
            if form.is_valid():
                appointed, created = EPACommitteeChair.objects.get_or_create(
                    mandate=mandate,
                    defaults={"member": form.cleaned_data["member"], "created_by": actor},
                )
                if not created and appointed.member_id != form.cleaned_data["member"].pk:
                    return HttpResponse("Ketua sudah ditunjuk untuk mandat ini.", status=409)
                return redirect("accounts:epa_committee", mandate.pk)
    return render(
        request,
        "epa/committee_chair.html",
        {"mandate": mandate, "form": form},
        status=400 if writing else 200,
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def discussion(
    request: HttpRequest, mandate_id: int, publication_id: int, enrollment_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    case = {"publication_id": publication_id, "enrollment_id": enrollment_id}
    mandates = active_mandates(actor)
    mandate = get_object_or_404(mandates, pk=mandate_id)
    get_object_or_404(committee_cases(mandate), **case)
    participants = eligible_participants(mandate, **case)
    if not participants.filter(created_by=actor).exists():
        raise PermissionDenied
    is_chair = EPACommitteeChair.objects.filter(mandate=mandate, member__account=actor).exists()
    ballots = EPACommitteeBallot.objects.filter(mandate=mandate, **case).select_related(
        "draft__level__version__scale",
        "proposed_level__version__scale",
        "enrollment__learner__account",
        "enrollment__cohort",
        "publication__version__activity",
    )
    decisions = EntrustmentDecision.objects.filter(
        ballot__publication_id=publication_id,
        ballot__enrollment_id=enrollment_id,
        replaces__isnull=True,
    )
    assigned_appeals = EPAAppeal.objects.filter(decision__in=decisions, mandate=mandate)
    appeal = assigned_appeals.first()
    ballot = ballots.first()
    writing = request.method == "POST"
    action = request.POST.get("action") if writing else None
    proposal: ProposalForm
    bound_data = request.POST if action == "open" else None
    if appeal is not None:
        proposal = AppealProposalForm(bound_data)
        cast(
            forms.ModelChoiceField, proposal.fields["level"]
        ).queryset = appeal.decision.ballot.publication.version.scale.levels.all()
    else:
        proposal = ProposalForm(bound_data)
    cast(
        forms.ModelChoiceField, proposal.fields["draft"]
    ).queryset = EntrustmentReview.objects.filter(
        assignment__publication_id=publication_id,
        assignment__enrollment_id=enrollment_id,
        level__version_id=F("assignment__publication__version__scale_id"),
    ).select_related(
        "assignment__enrollment__learner__account",
        "assignment__enrollment__cohort",
        "assignment__publication__version__activity",
    )
    comment_form = CommentForm(request.POST if action == "comment" else None)
    vote_form = VoteForm(request.POST if action == "vote" else None)
    error = ""
    if writing:
        with transaction.atomic():
            get_object_or_404(mandates.select_for_update(of=("self",)), pk=mandate_id)
            member_records = list(eligible_participants(mandate, **case))
            member_ids = {record.created_by_id for record in member_records}
            if actor.pk not in member_ids:
                raise PermissionDenied
            ballot = ballots.first()
            if action in {"open", "close"} and not is_chair:
                raise PermissionDenied
            if action == "open":
                current_appeal = assigned_appeals.first()
                if current_appeal != appeal:
                    return HttpResponse("Muat ulang untuk membuka pembahasan kasus.", status=409)
                if decisions.exists() and (appeal is None or appeal.resolved_at is not None):
                    return HttpResponse("Kasus sudah memiliki keputusan.", status=409)
                if ballot is not None and (
                    ballot.closed_at is None
                    or ballot.outcome == EPACommitteeBallot.Outcome.ADVANCED
                ):
                    return HttpResponse("Kasus sudah memiliki pembahasan atau hasil.", status=409)
                if len(member_ids) < mandate.quorum:
                    error = "Kuorum belum terpenuhi."
                elif proposal.is_valid():
                    EPACommitteeBallot.objects.create(
                        mandate=mandate,
                        **case,
                        draft=proposal.cleaned_data["draft"],
                        proposed_level=proposal.cleaned_data.get("level"),
                        proposed_rationale=proposal.cleaned_data.get("rationale", ""),
                        created_by=actor,
                    )
                    return redirect(
                        "epa_committee_discussion", mandate_id, publication_id, enrollment_id
                    )
            elif action in {"comment", "vote", "close"}:
                target = request.POST.get("ballot")
                if ballot is None or ballot.closed_at is not None or target != str(ballot.pk):
                    return HttpResponse("Pemungutan suara ini sudah tidak terbuka.", status=409)
                if action == "comment" and comment_form.is_valid():
                    comment = comment_form.save(commit=False)
                    comment.ballot, comment.created_by = ballot, actor
                    comment.save()
                elif action == "vote" and vote_form.is_valid():
                    vote, created = ballot.votes.get_or_create(
                        created_by=actor, defaults={"choice": vote_form.cleaned_data["choice"]}
                    )
                    if not created and vote.choice != vote_form.cleaned_data["choice"]:
                        return HttpResponse("Suara Anda sudah tercatat.", status=409)
                elif action == "close":
                    if len(member_ids) < mandate.quorum:
                        error = "Kuorum belum terpenuhi."
                    else:
                        votes = dict(ballot.votes.values_list("created_by_id", "choice"))
                        approvals = sum(
                            votes.get(member) == EPACommitteeVote.Choice.APPROVE
                            for member in member_ids
                        )
                        ballot.closed_at = timezone.now()
                        ballot.closed_by = actor
                        ballot.outcome = (
                            EPACommitteeBallot.Outcome.ADVANCED
                            if approvals * 2 > len(member_ids)
                            else EPACommitteeBallot.Outcome.RETURNED
                        )
                        ballot.result = {
                            "quorum": mandate.quorum,
                            "eligible": len(member_ids),
                            "approvals": approvals,
                            "participants": [
                                {"declaration": record.pk, "vote": votes.get(record.created_by_id)}
                                for record in member_records
                            ],
                        }
                        ballot.save(update_fields=("closed_at", "closed_by", "outcome", "result"))
                if not (error or comment_form.errors or vote_form.errors):
                    return redirect(
                        "epa_committee_discussion", mandate_id, publication_id, enrollment_id
                    )
            else:
                return HttpResponse(status=400)
    can_open = is_chair and (
        ballot is None or ballot.outcome == EPACommitteeBallot.Outcome.RETURNED
    )
    return render(
        request,
        "epa/discussion.html",
        {
            "mandate": mandate,
            **case,
            "ballot": ballot,
            "ballots": ballots,
            "proposal": proposal
            if can_open
            and (not decisions.exists() or (appeal is not None and appeal.resolved_at is None))
            else None,
            "decision": decisions.first(),
            "appeal": appeal,
            "is_chair": is_chair,
            "comment_form": comment_form,
            "vote_form": vote_form,
            "error": error,
            "own_vote": ballot.votes.filter(created_by=actor).first() if ballot else None,
            "comments": ballot.comments.select_related("created_by") if ballot else (),
            "evidence": ballot.draft.evidence.select_related("level") if ballot else (),
        },
        status=400 if writing else 200,
    )


@never_cache
@login_required
@permission_required((WORKSPACE, AUDIT_BALLOTS), raise_exception=True)
@require_safe
def audit(request: HttpRequest, mandate_id: int) -> HttpResponse:
    mandate = get_object_or_404(EPACommitteeMandate, pk=mandate_id)
    ballots = (
        EPACommitteeBallot.objects.filter(mandate=mandate)
        .select_related(
            "enrollment__learner__account",
            "enrollment__cohort",
            "publication__version__activity",
            "draft__level",
            "proposed_level",
            "created_by",
            "closed_by",
        )
        .prefetch_related("votes__created_by")
    )
    page = Paginator(ballots, 25).get_page(request.GET.get("page"))
    return render(request, "epa/ballot_audit.html", {"mandate": mandate, "page": page})
