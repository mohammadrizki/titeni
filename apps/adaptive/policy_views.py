from collections import defaultdict
from typing import cast
from urllib.parse import urlencode
from uuid import UUID

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed, can_view_evidence_records, require_evidence_view
from apps.assessments.models import (
    AssessmentAttempt,
    AssessmentEvent,
    AssessmentParticipation,
    AssessmentSamplingRule,
    BlueprintItemEvidenceSource,
)
from apps.evidence.models import LearnerEvidenceBaseline
from apps.evidence.plans import can_access_plan

from .fulfillment import VIEW_FULFILLMENT
from .models import (
    AdaptiveAttemptOption,
    AdaptiveEscalation,
    AdaptivePolicyPublication,
    AdaptivePolicyVersion,
    AttemptFulfillmentCheck,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvaluationRulePublication,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
    ScheduledAssessorAssignment,
)
from .policy_preview import preview_policy
from .reservations import (
    LINK_PERMISSION,
    RELEASE_PERMISSION,
    RESERVE_PERMISSION,
    link_attempt,
    release_attempt,
    reserve_attempt,
)
from .scheduling import SCHEDULE_PERMISSION, assign_scheduled_assessor, eligible_assessors
from .services import PUBLISH_PERMISSION

VIEW_POLICY = "adaptive.view_adaptivepolicyversion"


class PolicyForm(forms.Form):
    rule_publication = forms.ModelChoiceField(
        label="Aturan evaluasi terbit", queryset=EvaluationRulePublication.objects.none()
    )
    maximum_attempts = forms.IntegerField(
        label="Batas kumulatif percobaan tambahan", min_value=0, max_value=10000
    )
    review_within_days = forms.IntegerField(
        label="Tenggat tinjauan sejak eskalasi (hari)", min_value=1, max_value=3650
    )


class SlotForm(forms.Form):
    option = forms.ModelChoiceField(
        label="Opsi percobaan", queryset=AdaptiveAttemptOption.objects.none()
    )
    event = forms.ModelChoiceField(
        label="Pelaksanaan asesmen", queryset=AssessmentEvent.objects.none()
    )
    capacity = forms.IntegerField(label="Kapasitas yang dikonfirmasi", min_value=1, max_value=10000)

    def clean(self) -> dict:
        values = cast(dict, super().clean())
        option = values.get("option")
        event = values.get("event")
        if option and event and option.sampling.item_id != event.component_id:
            self.add_error("event", "Pelaksanaan harus berasal dari komponen opsi.")
        return values


class OptionForm(forms.ModelForm):
    class Meta:
        model = AdaptiveAttemptOption
        fields = (
            "sampling",
            "source_link",
            "priority",
            "maximum_per_option",
            "adds_attempt",
            "adds_context",
            "adds_source",
            "adds_verifier",
        )
        labels = {
            "sampling": "Komponen dan konteks sampling",
            "source_link": "Komponen, sumber, dan jenis bukti",
            "priority": "Prioritas (angka lebih kecil didahulukan)",
            "maximum_per_option": "Batas kumulatif opsi",
            "adds_attempt": "Percobaan",
            "adds_context": "Konteks",
            "adds_source": "Sumber",
            "adds_verifier": "Verifikator",
        }

    def clean(self) -> dict:
        values = cast(dict, super().clean())
        sampling = values.get("sampling")
        source = values.get("source_link")
        if sampling and source and sampling.item_id != source.item_id:
            self.add_error("source_link", "Sumber dan sampling harus dari komponen yang sama.")
        if not any(
            values.get(field)
            for field in ("adds_attempt", "adds_context", "adds_source", "adds_verifier")
        ):
            self.add_error(None, "Pilih setidaknya satu jenis celah.")
        return values


def publications_for_program(program_id: int) -> QuerySet[EvaluationRulePublication]:
    return EvaluationRulePublication.objects.filter(
        rule__standard__standard__item__version__framework__program_id=program_id,
        rule__demonstration=False,
    ).select_related("rule__standard__standard__item")


def can_view_escalation_queue(actor: User, program_id: int, roles: set[str]) -> bool:
    return (
        {VIEW_POLICY, "adaptive.view_adaptiveescalation"} <= roles
        and can_access_plan(actor, program_id, "view")
        and allowed(actor, roles, "adaptive.view_evidenceevaluation")
        and can_view_evidence_records(actor, roles)
    )


def program_escalations(program_id: int) -> QuerySet[AdaptiveEscalation]:
    return AdaptiveEscalation.objects.filter(
        baseline__enrollment__cohort__period__program_id=program_id,
        baseline__publication__artifact_map__program_id=program_id,
        target__version__framework__program_id=program_id,
    )


@require_http_methods(["GET"])
@login_required
def escalation_queue(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    roles = program_role_permissions(actor, program_id)
    if not can_view_escalation_queue(actor, program_id, roles):
        raise PermissionDenied
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    today = timezone.localdate()
    cases = program_escalations(program_id)
    opened = Q(closed_at__isnull=True)
    overdue = opened & Q(due_on__lt=today)
    totals = cases.aggregate(
        open=Count("pk", filter=opened),
        overdue=Count("pk", filter=overdue),
        due_today=Count("pk", filter=opened & Q(due_on=today)),
    )
    state = request.GET.get("status", "open")
    filters = {"open": opened, "overdue": overdue, "closed": ~opened}
    if state not in filters:
        raise Http404
    page = Paginator(
        cases.filter(filters[state])
        .select_related("baseline__enrollment__learner__account", "target")
        .order_by("due_on", "pk"),
        25,
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "adaptive/escalation_queue.html",
        {
            "program": program,
            "page": page,
            "state": state,
            "totals": totals,
            "today": today,
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def policies(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    if VIEW_POLICY not in roles:
        raise PermissionDenied
    can_add = "adaptive.add_adaptivepolicyversion" in roles
    publications = publications_for_program(program_id)
    form = PolicyForm(request.POST if request.method == "POST" else None)
    cast(forms.ModelChoiceField, form.fields["rule_publication"]).queryset = publications.filter(
        rule__retirement__isnull=True
    )
    if request.method == "POST":
        if not can_add:
            raise PermissionDenied
        if form.is_valid():
            publication = form.cleaned_data["rule_publication"]
            with transaction.atomic():
                EvaluationRulePublication.objects.select_for_update().get(pk=publication.pk)
                siblings = AdaptivePolicyVersion.objects.filter(rule_publication=publication)
                last = siblings.aggregate(number=Max("number"))["number"]
                policy = AdaptivePolicyVersion.objects.create(
                    number=(last or 0) + 1, created_by=actor, **form.cleaned_data
                )
            return redirect(
                "academics:evidence:adaptive_policy", program_id=program_id, policy_id=policy.pk
            )
    versions = AdaptivePolicyVersion.objects.filter(
        rule_publication__in=publications
    ).select_related(
        "rule_publication__rule__standard__standard__item", "created_by", "publication"
    )
    return render(
        request,
        "adaptive/policies.html",
        {
            "program": program,
            "form": form,
            "can_add": can_add,
            "versions": versions,
            "escalation_reminders": (
                program_escalations(program_id)
                .filter(closed_at__isnull=True, due_on__lte=timezone.localdate())
                .count()
                if can_view_escalation_queue(actor, program_id, roles)
                else None
            ),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def policy_detail(request: HttpRequest, program_id: int, policy_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    if VIEW_POLICY not in roles:
        raise PermissionDenied
    policy = get_object_or_404(
        AdaptivePolicyVersion.objects.select_related(
            "rule_publication__rule__standard__standard__item"
        ),
        pk=policy_id,
        rule_publication__in=publications_for_program(program_id),
    )
    action = request.POST.get("action", "add-option") if request.method == "POST" else None
    can_add = "adaptive.add_adaptiveattemptoption" in roles
    can_publish = PUBLISH_PERMISSION in roles
    can_confirm = "adaptive.add_confirmedattemptslot" in roles
    target = policy.rule_publication.rule.standard.standard.item
    form = OptionForm(request.POST if action == "add-option" else None)
    item_scope = {
        "item__version__blueprint__program_id": program_id,
        "item__version__framework_version_id": target.version_id,
        "item__blueprintitemcompetency__competency_id": target.pk,
    }
    cast(forms.ModelChoiceField, form.fields["sampling"]).queryset = (
        AssessmentSamplingRule.objects.filter(**item_scope).select_related("item").distinct()
    )
    cast(forms.ModelChoiceField, form.fields["source_link"]).queryset = (
        BlueprintItemEvidenceSource.objects.filter(
            **item_scope,
            capability__source__program_id=program_id,
            capability__evidence_type__program_id=program_id,
        )
        .select_related("item", "capability__source", "capability__evidence_type")
        .distinct()
    )
    options = policy.options.select_related(
        "sampling__item",
        "source_link__capability__source",
        "source_link__capability__evidence_type",
    )
    slot_form = SlotForm(request.POST if action == "confirm-slot" else None)
    cast(forms.ModelChoiceField, slot_form.fields["option"]).queryset = options
    cast(
        forms.ModelChoiceField, slot_form.fields["event"]
    ).queryset = AssessmentEvent.objects.filter(
        component_id__in=options.values("sampling__item_id"),
        occurred_on__gte=timezone.localdate(),
    ).select_related("component")
    published = AdaptivePolicyPublication.objects.filter(policy=policy).first()
    publication_error = ""
    if action == "publish":
        if not can_publish:
            raise PermissionDenied
        with transaction.atomic():
            rule = EvaluationRuleVersion.objects.select_for_update().get(
                pk=policy.rule_publication.rule_id
            )
            AdaptivePolicyVersion.objects.select_for_update().get(pk=policy.pk)
            if EvaluationRuleRetirement.objects.filter(rule=rule).exists():
                publication_error = "Aturan evaluasi induk sudah dihentikan."
            elif policy.maximum_attempts and not options.exists():
                publication_error = "Tambahkan opsi atau buat versi dengan batas nol."
            else:
                AdaptivePolicyPublication.objects.get_or_create(
                    policy=policy,
                    defaults={
                        "created_by": actor,
                        "automatic_reservations": request.POST.get("automatic_reservations")
                        == "on",
                    },
                )
                return redirect(request.path)
    elif action == "confirm-slot":
        if not can_confirm or published is None:
            raise PermissionDenied
        if slot_form.is_valid():
            with transaction.atomic():
                AdaptivePolicyVersion.objects.select_for_update().get(pk=policy.pk)
                slot, created = ConfirmedAttemptSlot.objects.get_or_create(
                    option=slot_form.cleaned_data["option"],
                    event=slot_form.cleaned_data["event"],
                    defaults={"capacity": slot_form.cleaned_data["capacity"], "created_by": actor},
                )
                if not created and slot.capacity != slot_form.cleaned_data["capacity"]:
                    slot_form.add_error(
                        None, "Kapasitas untuk opsi dan pelaksanaan ini sudah tercatat."
                    )
                else:
                    return redirect(request.path)
    elif action == "add-option":
        if not can_add:
            raise PermissionDenied
        if form.is_valid():
            option = form.save(commit=False)
            with transaction.atomic():
                AdaptivePolicyVersion.objects.select_for_update().get(pk=policy.pk)
                if AdaptivePolicyPublication.objects.filter(policy=policy).exists():
                    form.add_error(None, "Versi terbit terkunci. Buat draf versi baru.")
                elif policy.options.filter(
                    sampling=option.sampling, source_link=option.source_link
                ).exists():
                    form.add_error(None, "Opsi dengan konteks dan sumber ini sudah tercatat.")
                else:
                    option.policy = policy
                    option.created_by = actor
                    option.save()
                    return redirect(request.path)
    elif action is not None:
        raise PermissionDenied

    return render(
        request,
        "adaptive/policy_detail.html",
        {
            "program": program,
            "policy": policy,
            "form": form,
            "can_add": can_add and published is None,
            "can_publish": can_publish and published is None,
            "can_confirm": can_confirm and published is not None,
            "published": published,
            "publication_error": publication_error,
            "options": options,
            "slot_form": slot_form,
            "slots": ConfirmedAttemptSlot.objects.filter(option__policy=policy).select_related(
                "option__sampling__item", "event", "created_by"
            ),
        },
    )


def requested_pk(raw: str) -> int:
    try:
        value = int(raw)
        if not 0 < value < 2**63:
            raise ValueError
    except ValueError as error:
        raise Http404 from error
    return value


@require_http_methods(["GET", "POST"])
@login_required
def preview_policy_for_evaluation(
    request: HttpRequest, program_id: int, enrollment_id: int, evaluation_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    roles = program_role_permissions(actor, program_id)
    if not (
        VIEW_POLICY in roles
        and can_access_plan(actor, program_id, "view")
        and allowed(actor, roles, "adaptive.view_evidenceevaluation")
    ):
        raise PermissionDenied
    require_evidence_view(actor, roles)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    evaluation = get_object_or_404(
        EvidenceEvaluation,
        pk=evaluation_id,
        baseline__enrollment_id=enrollment_id,
        baseline__enrollment__cohort__period__program=program,
        baseline__publication__artifact_map__program=program,
        rule__publication__in=publications_for_program(program_id),
    )
    versions = AdaptivePolicyVersion.objects.filter(
        rule_publication__rule_id=evaluation.rule_id,
    ).select_related("rule_publication__rule__standard__standard__item", "publication")
    active_rule = not hasattr(evaluation.rule, "retirement")
    can_reserve = RESERVE_PERMISSION in roles and active_rule
    can_release = RELEASE_PERMISSION in roles
    can_link = LINK_PERMISSION in roles
    can_schedule = SCHEDULE_PERMISSION in roles
    can_view_escalations = "adaptive.view_adaptiveescalation" in roles
    can_review_escalation = can_view_escalations and "adaptive.change_adaptiveescalation" in roles
    escalations = AdaptiveEscalation.objects.none()
    can_view_fulfillment = VIEW_FULFILLMENT in roles
    error_message = ""
    status = 200
    chosen = request.POST.get("policy") if request.method == "POST" else request.GET.get("policy")
    policy = None
    proposal = None
    rows = []
    reservations = AttemptReservation.objects.none()
    if chosen is not None:
        policy = get_object_or_404(versions, pk=requested_pk(chosen))
        reservations = (
            AttemptReservation.objects.filter(
                baseline=evaluation.baseline, slot__option__policy=policy
            )
            .select_related("event", "created_by", "released_by", "attempt", "linked_by")
            .annotate(
                participating=Exists(
                    AssessmentParticipation.objects.filter(
                        event_id=OuterRef("event_id"),
                        enrollment_id=enrollment_id,
                    )
                )
            )
            .prefetch_related(
                Prefetch(
                    "scheduling_assignments",
                    queryset=ScheduledAssessorAssignment.objects.select_related(
                        "assessor", "assigned_by"
                    ),
                )
            )
            .order_by("-pk")
        )
        if can_view_fulfillment:
            reservations = reservations.prefetch_related(
                Prefetch(
                    "fulfillment_checks",
                    queryset=AttemptFulfillmentCheck.objects.select_related(
                        "supporting_record", "checked_by"
                    ),
                )
            )
        if can_view_escalations:
            escalations = (
                AdaptiveEscalation.objects.filter(
                    baseline=evaluation.baseline,
                    target_id=evaluation.rule.standard.standard.item_id,
                )
                .select_related("reviewed_by")
                .order_by("-pk")
            )
        if request.method == "POST":
            action = request.POST.get("action", "reserve")
            try:
                if action == "release" and can_release:
                    reservation = get_object_or_404(
                        reservations, pk=requested_pk(request.POST.get("reservation", ""))
                    )
                    release_attempt(reservation, actor, request.POST.get("reason", ""))
                elif action == "schedule-assessor" and can_schedule:
                    reservation = get_object_or_404(
                        reservations, pk=requested_pk(request.POST.get("reservation", ""))
                    )
                    try:
                        assessor_id = UUID(request.POST.get("assessor", ""))
                    except ValueError as error:
                        raise ValidationError("Pilih asesor yang tersedia.") from error
                    previous = request.POST.get("previous")
                    assign_scheduled_assessor(
                        reservation,
                        actor,
                        assessor_id,
                        request.POST.get("reason", ""),
                        requested_pk(previous) if previous else 0,
                    )
                elif action == "link-attempt" and can_link:
                    reservation = get_object_or_404(
                        reservations, pk=requested_pk(request.POST.get("reservation", ""))
                    )
                    link_attempt(reservation, requested_pk(request.POST.get("attempt", "")), actor)
                elif action == "review-escalation" and can_review_escalation:
                    note = request.POST.get("note", "").strip()
                    if not 0 < len(note) <= 500:
                        raise ValidationError("Isi catatan tindak lanjut hingga 500 karakter.")
                    with transaction.atomic():
                        LearnerEvidenceBaseline.objects.select_for_update().get(
                            pk=evaluation.baseline_id
                        )
                        case = get_object_or_404(
                            escalations, pk=requested_pk(request.POST.get("escalation", ""))
                        )
                        if case.closed_at is not None:
                            raise ValidationError("Eskalasi sudah ditutup.")
                        if case.reviewed_at is None:
                            case.reviewed_at = timezone.now()
                            case.reviewed_by = actor
                            case.review_note = note
                            case.save(update_fields=["reviewed_at", "reviewed_by", "review_note"])
                elif action == "reserve" and can_reserve:
                    reserve_attempt(
                        evaluation, policy, requested_pk(request.POST.get("slot", "")), actor
                    )
                else:
                    raise PermissionDenied
            except ValidationError as error:
                status = 409
                error_message = " ".join(error.messages)
            else:
                return redirect(f"{request.path}?{urlencode({'policy': policy.pk})}")
        if active_rule:
            proposal, slots = preview_policy(evaluation, policy)
            rows = [(slots[row.option.code], row.targets) for row in proposal.additional]
    attempts_by_event: defaultdict[int, list[AssessmentAttempt]] = defaultdict(list)
    if can_link:
        candidates = (
            AssessmentAttempt.objects.filter(
                participation__event_id__in=reservations.filter(
                    attempt__isnull=True,
                    released_at__isnull=True,
                ).values("event_id"),
                participation__enrollment_id=enrollment_id,
                adaptive_reservation__isnull=True,
            )
            .select_related("participation")
            .order_by("number", "pk")
        )
        for attempt in candidates:
            attempts_by_event[attempt.participation.event_id].append(attempt)
    return render(
        request,
        "adaptive/policy_preview.html",
        {
            "program": program,
            "evaluation": evaluation,
            "versions": versions,
            "policy": policy,
            "proposal": proposal,
            "rows": rows,
            "reservation_rows": [
                (reservation, attempts_by_event.get(reservation.event_id, ()))
                for reservation in reservations
            ],
            "can_release": can_release,
            "can_link": can_link,
            "can_schedule": can_schedule,
            "escalations": escalations,
            "can_review_escalation": can_review_escalation,
            "eligible_assessors": eligible_assessors(program_id) if can_schedule else (),
            "today": timezone.localdate(),
            "can_view_fulfillment": can_view_fulfillment,
            "active_rule": active_rule,
            "can_reserve": can_reserve and policy is not None and hasattr(policy, "publication"),
            "error": error_message,
        },
        status=status,
    )
