from datetime import timedelta
from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, QuerySet, Subquery
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe

from apps.academics.models import LearnerEnrollment, StudyProgram
from apps.accounts.models import User
from apps.competencies.models import PerformanceStandardVersion

from .academic_advisors import role_grants
from .models import (
    ProgressionAppeal,
    ProgressionAppealPolicy,
    ProgressionBallot,
    ProgressionCommitteeMandate,
    ProgressionCommitteeParticipation,
    ProgressionDecision,
    ProgressionReview,
    ProgressionVote,
)
from .progression_appeals import AppealForm, independent_mandates, resolve_appeal
from .progression_committees import WORKSPACE

AUDIT = "learning.view_progressionballot"
VIEW_DECISION = "view_progressiondecision"
ADD_APPEAL = "add_progressionappeal"


def active_mandates() -> QuerySet[ProgressionCommitteeMandate]:
    now = timezone.now()
    today = timezone.localdate(now)
    return ProgressionCommitteeMandate.objects.filter(
        issued_at__lte=now, revoked_at__isnull=True, starts_on__lte=today, ends_on__gte=today
    )


def member_mandates(actor: User) -> QuerySet[ProgressionCommitteeMandate]:
    return active_mandates().filter(
        memberships__account=actor, memberships__account__is_active=True
    )


def case_enrollments(mandate: ProgressionCommitteeMandate) -> QuerySet[LearnerEnrollment]:
    return (
        LearnerEnrollment.objects.filter(
            cohort__period__program_id=mandate.program_id,
            progressionreviewassignment__drafts__isnull=False,
        )
        .distinct()
        .select_related("learner__account", "cohort")
    )


def eligible_participants(
    mandate: ProgressionCommitteeMandate, enrollment_id: int
) -> QuerySet[ProgressionCommitteeParticipation]:
    records = ProgressionCommitteeParticipation.objects.filter(
        mandate=mandate, enrollment_id=enrollment_id
    )
    latest = records.filter(member_id=OuterRef("member_id")).values("pk")[:1]
    return records.filter(
        pk=Subquery(latest),
        member__mandate=mandate,
        member__account__is_active=True,
        mandate__in=active_mandates(),
        enrollment__cohort__period__program_id=mandate.program_id,
        present=True,
        conflict=False,
    )


class AttendanceForm(forms.Form):
    present = forms.TypedChoiceField(
        label="Kehadiran",
        choices=(("1", "Hadir"), ("0", "Tidak hadir")),
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
    )
    conflict = forms.TypedChoiceField(
        label="Konflik kepentingan",
        choices=(("0", "Tidak ada"), ("1", "Ada")),
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
    )


class ProposalForm(forms.Form):
    appeal = forms.ModelChoiceField(
        label="Banding yang dibahas", queryset=ProgressionAppeal.objects.none(), required=False
    )

    draft = forms.ModelChoiceField(label="Draf", queryset=ProgressionReview.objects.none())
    outcome = forms.ChoiceField(label="Usulan", choices=ProgressionBallot.ProposedOutcome.choices)
    standard = forms.ModelChoiceField(
        label="Versi standar capaian kompetensi",
        queryset=PerformanceStandardVersion.objects.none(),
        required=False,
    )
    conditions = forms.CharField(
        label="Syarat atau kebutuhan bukti", max_length=4000, widget=forms.Textarea, required=False
    )

    def __init__(
        self, *args, enrollment: LearnerEnrollment, appeals: QuerySet[ProgressionAppeal], **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["appeal"]).queryset = appeals
        drafts = ProgressionReview.objects.filter(assignment__enrollment=enrollment).select_related(
            "assignment__enrollment__learner__account",
            "assignment__enrollment__cohort",
            "assignment__reviewer",
        )
        cast(forms.ModelChoiceField, self.fields["draft"]).queryset = drafts
        standard_ids = drafts.filter(evidence__evaluation__isnull=False).values(
            "evidence__evaluation__rule__standard_id"
        )
        cast(
            forms.ModelChoiceField, self.fields["standard"]
        ).queryset = PerformanceStandardVersion.objects.filter(pk__in=standard_ids).select_related(
            "standard__item"
        )

    def clean(self) -> dict:
        data = super().clean() or {}
        draft, outcome, standard = data.get("draft"), data.get("outcome"), data.get("standard")
        if outcome == ProgressionBallot.ProposedOutcome.ATTAINMENT and standard is None:
            self.add_error("standard", "Pilih versi standar untuk pengesahan capaian.")
        if (
            draft is not None
            and standard is not None
            and not draft.evidence.filter(evaluation__rule__standard=standard).exists()
        ):
            self.add_error("standard", "Versi standar harus berasal dari bukti pada draf terpilih.")
        if outcome in {
            ProgressionBallot.ProposedOutcome.CONDITIONAL,
            ProgressionBallot.ProposedOutcome.DEFERRED,
        } and not data.get("conditions"):
            self.add_error("conditions", "Tuliskan syarat atau kebutuhan bukti tambahan.")
        return data


class NoteForm(forms.Form):
    body = forms.CharField(label="Catatan pembahasan", max_length=4000, widget=forms.Textarea)


class VoteForm(forms.Form):
    choice = forms.ChoiceField(label="Suara", choices=ProgressionVote.Choice.choices)


class PublicationForm(forms.Form):
    rationale = forms.CharField(label="Alasan keputusan", max_length=4000, widget=forms.Textarea)


@never_cache
@login_required
@require_safe
def queue(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    return render(
        request,
        "learning/progression_committee_queue.html",
        {"mandates": member_mandates(actor).select_related("program")},
    )


@never_cache
@login_required
@require_safe
def cases(request: HttpRequest, mandate_id: int) -> HttpResponse:
    mandate = get_object_or_404(member_mandates(cast(User, request.user)), pk=mandate_id)
    page = Paginator(case_enrollments(mandate), 25).get_page(request.GET.get("page"))
    return render(
        request, "learning/progression_committee_cases.html", {"mandate": mandate, "page": page}
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def review(request: HttpRequest, mandate_id: int, enrollment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    mandates = member_mandates(actor)
    mandate = get_object_or_404(mandates, pk=mandate_id)
    enrollment = get_object_or_404(case_enrollments(mandate), pk=enrollment_id)
    member = get_object_or_404(mandate.memberships, account=actor)
    case = {"mandate": mandate, "enrollment": enrollment}
    own_attendance = ProgressionCommitteeParticipation.objects.filter(**case, member=member)
    previous = own_attendance.first()
    ballots = ProgressionBallot.objects.filter(**case).select_related(
        "draft__assignment__reviewer", "standard__standard__item", "decision"
    )
    ballot = ballots.first()
    writing = request.method == "POST"
    action = request.POST.get("action") if writing else ""
    attendance = AttendanceForm(
        request.POST if action == "attendance" else None,
        initial=(
            {"present": int(previous.present), "conflict": int(previous.conflict)}
            if previous
            else None
        ),
    )
    appeals = ProgressionAppeal.objects.filter(
        mandate=mandate,
        decision__ballot__enrollment=enrollment,
        assigned_at__isnull=False,
        resolved_at__isnull=True,
    ).select_related(
        "decision__ballot__enrollment__learner__account", "decision__ballot__enrollment__cohort"
    )
    proposal = ProposalForm(
        request.POST if action == "open" else None, enrollment=enrollment, appeals=appeals
    )
    if not appeals.exists():
        proposal.fields["appeal"].widget = forms.HiddenInput()
    comment = NoteForm(request.POST if action == "comment" else None)
    vote = VoteForm(request.POST if action == "vote" else None)
    publication = PublicationForm(request.POST if action == "publish" else None)
    eligible = eligible_participants(mandate, enrollment_id)
    can_discuss = eligible.filter(member=member).exists()
    is_chair = mandate.chair_id == member.pk
    error = ""
    if writing:
        with transaction.atomic():
            get_object_or_404(mandates.select_for_update(of=("self",)), pk=mandate_id)
            if action == "attendance":
                if attendance.is_valid():
                    previous = own_attendance.first()
                    values = attendance.cleaned_data
                    if previous is None or (
                        previous.present != values["present"]
                        or previous.conflict != values["conflict"]
                    ):
                        own_attendance.create(**case, member=member, **values)
                    return redirect("progression_committee_case", mandate_id, enrollment_id)
            else:
                records = {item.member_id: item for item in eligible}
                if member.pk not in records or (
                    action in {"open", "close", "publish"} and not is_chair
                ):
                    raise PermissionDenied
                ballot = ballots.first()
                if action == "open":
                    if ballot and (
                        ballot.closed_at is None
                        or (
                            ballot.result == ProgressionBallot.Result.ADVANCED
                            and not hasattr(ballot, "decision")
                            and not hasattr(ballot, "appeal_result")
                        )
                    ):
                        return HttpResponse("Putaran sebelumnya belum selesai.", status=409)
                    if len(records) < mandate.quorum:
                        error = "Kuorum belum terpenuhi."
                    elif proposal.is_valid():
                        data = proposal.cleaned_data
                        appeal = data["appeal"]
                        if (
                            appeal is not None
                            and not independent_mandates(appeal).filter(pk=mandate.pk).exists()
                        ):
                            return HttpResponse(
                                "Mandat banding sudah tidak memenuhi syarat.", status=409
                            )
                        if (
                            appeal is None
                            and ProgressionDecision.objects.filter(
                                draft=data["draft"], replaces__isnull=True
                            ).exists()
                        ):
                            return HttpResponse("Draf sudah memiliki keputusan.", status=409)
                        ProgressionBallot.objects.create(
                            **case,
                            draft=data["draft"],
                            appeal=appeal,
                            proposed_outcome=data["outcome"],
                            standard=data["standard"],
                            conditions=data["conditions"],
                            created_by=actor,
                        )
                        return redirect("progression_committee_case", mandate_id, enrollment_id)
                elif action in {"comment", "vote", "close", "publish"}:
                    if ballot is None or request.POST.get("ballot") != str(ballot.pk):
                        return HttpResponse("Putaran telah berubah.", status=409)
                    if action == "publish":
                        if ballot.result != ProgressionBallot.Result.ADVANCED:
                            return HttpResponse("Usulan belum lolos.", status=409)
                        if publication.is_valid():
                            rationale = publication.cleaned_data["rationale"]
                            if ballot.appeal_id is not None:
                                problem = resolve_appeal(ballot, actor, rationale)
                                if problem:
                                    return HttpResponse(problem, status=409)
                            else:
                                problem = publish_initial(ballot, actor, rationale)
                                if problem:
                                    return HttpResponse(problem, status=409)
                            return redirect("progression_committee_case", mandate_id, enrollment_id)
                    elif ballot.closed_at is not None:
                        return HttpResponse("Putaran sudah ditutup.", status=409)
                    elif action == "comment" and comment.is_valid():
                        ballot.comments.create(member=member, body=comment.cleaned_data["body"])
                        return redirect("progression_committee_case", mandate_id, enrollment_id)
                    elif action == "vote" and vote.is_valid():
                        saved, _ = ballot.votes.get_or_create(
                            member=member, defaults={"choice": vote.cleaned_data["choice"]}
                        )
                        if saved.choice != vote.cleaned_data["choice"]:
                            return HttpResponse("Suara Anda sudah tercatat.", status=409)
                        return redirect("progression_committee_case", mandate_id, enrollment_id)
                    elif action == "close":
                        votes = dict(ballot.votes.values_list("member_id", "choice"))
                        approvals = sum(
                            votes.get(pk) == ProgressionVote.Choice.APPROVE for pk in records
                        )
                        ballot.result = (
                            ProgressionBallot.Result.ADVANCED
                            if len(records) >= mandate.quorum and approvals * 2 > len(records)
                            else ProgressionBallot.Result.RETURNED
                        )
                        ballot.tally = {
                            "eligible": len(records),
                            "quorum": mandate.quorum,
                            "approvals": approvals,
                            "participants": [
                                {"declaration": item.pk, "vote": votes.get(pk)}
                                for pk, item in records.items()
                            ],
                        }
                        ballot.closed_at, ballot.closed_by = timezone.now(), actor
                        ballot.save(update_fields=("closed_at", "closed_by", "result", "tally"))
                        return redirect("progression_committee_case", mandate_id, enrollment_id)
                else:
                    return HttpResponse(status=400)
    visible = ballot if can_discuss else None
    return render(
        request,
        "learning/progression_committee_case.html",
        {
            "mandate": mandate,
            "enrollment": enrollment,
            "attendance": attendance,
            "previous": previous,
            "quorum": eligible.count(),
            "ballot": visible,
            "is_chair": is_chair,
            "proposal": proposal
            if can_discuss
            and is_chair
            and (
                not ballot
                or ballot.closed_at
                and (
                    ballot.result == ProgressionBallot.Result.RETURNED
                    or hasattr(ballot, "decision")
                    or hasattr(ballot, "appeal_result")
                )
            )
            else None,
            "appeals": appeals if can_discuss else (),
            "comment": comment,
            "vote": vote,
            "publication": publication,
            "error": error,
            "own_vote": visible.votes.filter(member=member).first() if visible else None,
            "comments": visible.comments.select_related("member__account") if visible else (),
            "evidence": decision_evidence(visible.draft) if visible else (),
        },
        status=400 if writing else 200,
    )


def decision_evidence(draft: ProgressionReview):
    return draft.evidence.select_related(
        "evaluation__rule__standard__standard__item",
        "decision__ballot__publication__version__activity",
        "decision__ballot__draft__level",
        "decision__ballot__proposed_level",
    )


def publish_initial(ballot: ProgressionBallot, actor: User, rationale: str) -> str:
    ProgressionReview.objects.select_for_update().get(pk=ballot.draft_id)
    previous = ProgressionDecision.objects.filter(draft=ballot.draft, replaces__isnull=True).first()
    if previous is not None:
        return "" if previous.ballot_id == ballot.pk else "Draf sudah memiliki keputusan."
    program = StudyProgram.objects.select_for_update().get(pk=ballot.mandate.program_id)
    policy = ProgressionAppealPolicy.objects.filter(program=program).first()
    if policy is None:
        return "Fakultas perlu menetapkan tenggat banding progresi untuk prodi ini."
    decision = ProgressionDecision.objects.create(
        ballot=ballot,
        draft=ballot.draft,
        published_by=actor,
        rationale=rationale,
    )
    decision.appeal_until = decision.published_at + timedelta(days=policy.days)
    decision.save(update_fields=("appeal_until",))
    return ""


def student_decisions(
    actor: User, permission: str = VIEW_DECISION
) -> QuerySet[ProgressionDecision]:
    programs = role_grants("Mahasiswa", permission).filter(account=actor).values("program_id")
    return ProgressionDecision.objects.filter(
        ballot__enrollment__learner__account=actor,
        ballot__enrollment__cohort__period__program_id__in=programs,
    ).select_related(
        "ballot__enrollment__cohort",
        "ballot__standard__standard__item",
        "draft",
        "progressionappeal",
        "replaces",
        "replacement",
    )


@never_cache
@login_required
@require_safe
def decisions(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "learning/progression_decisions.html",
        {"decisions": student_decisions(cast(User, request.user))},
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def decision_detail(request: HttpRequest, decision_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    records = student_decisions(actor)
    decision = get_object_or_404(records, pk=decision_id)
    writing = request.method == "POST"
    form = AppealForm(request.POST if writing else None)
    allowed = student_decisions(actor, ADD_APPEAL).filter(pk=decision_id).exists()
    if writing:
        if not allowed:
            raise PermissionDenied
        with transaction.atomic():
            decision = get_object_or_404(records.select_for_update(of=("self",)), pk=decision_id)
            if ProgressionAppeal.objects.filter(decision=decision).exists():
                return redirect("progression_decision", decision_id)
            if decision.appeal_until is None or timezone.now() > decision.appeal_until:
                return HttpResponse(
                    "Tenggat banding telah berakhir atau tidak berlaku.", status=409
                )
            if form.is_valid():
                appeal = form.save(commit=False)
                appeal.decision, appeal.created_by = decision, actor
                appeal.save()
                return redirect("progression_decision", decision_id)
    appeal = getattr(decision, "progressionappeal", None)
    can_appeal = (
        allowed
        and appeal is None
        and decision.appeal_until is not None
        and timezone.now() <= decision.appeal_until
    )
    return render(
        request,
        "learning/progression_decisions.html",
        {
            "decision": decision,
            "evidence": decision_evidence(decision.draft),
            "appeal": appeal,
            "appeal_form": form if can_appeal else None,
        },
        status=400 if writing else 200,
    )


@never_cache
@login_required
@permission_required((WORKSPACE, AUDIT), raise_exception=True)
@require_safe
def audit(request: HttpRequest, mandate_id: int) -> HttpResponse:
    mandate = get_object_or_404(ProgressionCommitteeMandate, pk=mandate_id)
    ballots = (
        ProgressionBallot.objects.filter(mandate=mandate)
        .select_related(
            "enrollment__learner__account", "enrollment__cohort", "closed_by", "decision"
        )
        .prefetch_related("votes__member__account")
    )
    page = Paginator(ballots, 25).get_page(request.GET.get("page"))
    return render(
        request, "learning/progression_ballot_audit.html", {"mandate": mandate, "page": page}
    )
