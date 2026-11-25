from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment, StudyProgram
from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.models import (
    AssessmentAttempt,
    AssessmentEvent,
    AssessmentParticipation,
    BlueprintItem,
    BlueprintItemEvidenceSource,
)
from apps.evidence.models import EvidenceInvalidation, EvidenceRecord, EvidenceVerification

VERIFY_PERMISSION = "evidence.add_evidenceverification"


def allowed(actor: User, roles: set[str], permission: str) -> bool:
    return actor.has_perm(permission) or permission in roles


def can_view_attempts(actor: User, roles: set[str]) -> bool:
    return allowed(actor, roles, "assessments.view_assessmentattempt") and allowed(
        actor, roles, "academics.view_learnerenrollment"
    )


class ComponentChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj: BlueprintItem) -> str:
        return f"Blueprint versi {obj.version.number} · {obj}"


class EventForm(forms.ModelForm):
    component = ComponentChoice(label="Komponen", queryset=BlueprintItem.objects.none())
    occurred_on = forms.DateField(
        label="Tanggal pelaksanaan", widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = AssessmentEvent
        fields = ["component", "name", "occurred_on"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = cast(ComponentChoice, self.fields["component"])
        field.queryset = (
            BlueprintItem.objects.filter(version__blueprint__program=program)
            .select_related("version")
            .order_by("-version__number", "code")
        )


class AttemptForm(forms.Form):
    enrollment = forms.ModelChoiceField(
        label="Pendaftaran mahasiswa", queryset=LearnerEnrollment.objects.none()
    )

    def __init__(self, *args, event: AssessmentEvent, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = cast(forms.ModelChoiceField, self.fields["enrollment"])
        field.queryset = (
            LearnerEnrollment.objects.filter(
                cohort__period__program_id=event.component.version.blueprint.program_id
            )
            .select_related("learner__account", "cohort")
            .order_by("learner__account__username")
        )


class EvidenceRecordForm(forms.ModelForm):
    class Meta:
        model = EvidenceRecord
        fields = ["source_link", "reference", "context"]
        help_texts = {"reference": "Gunakan pengenal bukti tanpa informasi pasien."}

    def __init__(self, *args, attempt: AssessmentAttempt, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.attempt = attempt
        field = cast(forms.ModelChoiceField, self.fields["source_link"])
        field.queryset = BlueprintItemEvidenceSource.objects.filter(
            item_id=attempt.participation.event.component_id
        ).select_related("item", "capability__source", "capability__evidence_type")

    def clean(self) -> dict:
        super().clean()
        data = self.cleaned_data
        if data.get("source_link") and data.get("reference"):
            matches = EvidenceRecord.objects.filter(
                attempt=self.instance.attempt,
                source_link=data["source_link"],
                reference=data["reference"],
            )
            if self.instance.supersedes_id is not None:
                matches = matches.filter(superseded_by__isnull=True).exclude(
                    pk=self.instance.supersedes_id
                )
            if matches.exists():
                self.add_error("reference", "Referensi bukti ini sudah tercatat.")
        return data


class CorrectionForm(EvidenceRecordForm):
    correction_reason = forms.CharField(label="Alasan koreksi", max_length=500)

    class Meta(EvidenceRecordForm.Meta):
        fields = ["source_link", "reference", "context", "correction_reason"]


class InvalidationForm(forms.ModelForm):
    class Meta:
        model = EvidenceInvalidation
        fields = ["reason"]


def program_events(program: StudyProgram):
    return AssessmentEvent.objects.filter(
        component__version__blueprint__program=program
    ).select_related("component__version__blueprint__program")


@require_http_methods(["GET", "POST"])
@login_required
def events(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    if not allowed(actor, roles, "assessments.view_assessmentevent"):
        raise PermissionDenied
    can_add = allowed(actor, roles, "assessments.add_assessmentevent")
    writing = request.method == "POST"
    if writing and not can_add:
        raise PermissionDenied
    form = EventForm(request.POST if writing else None, program=program) if can_add else None
    if writing and form is not None and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            get_object_or_404(BlueprintItem.objects.select_for_update(), pk=event.component_id)
            event.created_by = actor
            event.save()
        return redirect("academics:assessments:events", program_id=program_id)
    return render(
        request,
        "assessments/events.html",
        {"program": program, "form": form, "events": program_events(program)},
    )


@require_http_methods(["GET", "POST"])
@login_required
def attempts(request: HttpRequest, program_id: int, event_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    if not allowed(actor, roles, "assessments.view_assessmentevent"):
        raise PermissionDenied
    can_view = can_view_attempts(actor, roles)
    can_add = can_view and allowed(actor, roles, "assessments.add_assessmentattempt")
    writing = request.method == "POST"
    if writing and not can_add:
        raise PermissionDenied
    queryset = program_events(program)
    with transaction.atomic():
        event = get_object_or_404(
            queryset.select_for_update(of=("self",)) if writing else queryset, pk=event_id
        )
        form = AttemptForm(request.POST if writing else None, event=event) if can_add else None
        if writing and form is not None and form.is_valid():
            participation, _ = AssessmentParticipation.objects.get_or_create(
                event=event, enrollment=form.cleaned_data["enrollment"]
            )
            latest = participation.attempts.order_by("-number").first()
            participation.attempts.create(
                number=latest.number + 1 if latest else 1, created_by=actor
            )
            return redirect(
                "academics:assessments:attempts", program_id=program_id, event_id=event.pk
            )
    attempts = AssessmentAttempt.objects.filter(
        participation__event=event, participation__enrollment__cohort__period__program=program
    ).select_related("participation__enrollment__learner__account")
    return render(
        request,
        "assessments/attempts.html",
        {
            "program": program,
            "event": event,
            "form": form,
            "attempts": attempts if can_view else None,
            "can_view_attempts": can_view,
            "can_view_evidence": allowed(actor, roles, "evidence.view_evidencerecord"),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def attempt_evidence(
    request: HttpRequest, program_id: int, event_id: int, attempt_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    require_evidence_view(actor, roles)
    can_add = allowed(actor, roles, "evidence.add_evidencerecord")
    writing = request.method == "POST"
    if writing and not can_add:
        raise PermissionDenied
    attempts = scoped_evidence_attempts(program, event_id)
    with transaction.atomic():
        attempt = get_object_or_404(
            attempts.select_for_update(of=("self",)) if writing else attempts, pk=attempt_id
        )
        form = (
            EvidenceRecordForm(request.POST if writing else None, attempt=attempt)
            if can_add
            else None
        )
        if writing and form is not None and form.is_valid():
            record = form.save(commit=False)
            get_object_or_404(
                BlueprintItemEvidenceSource.objects.select_for_update(), pk=record.source_link_id
            )
            record.created_by = actor
            record.save()
            return redirect(
                "academics:assessments:attempt_evidence",
                program_id=program_id,
                event_id=event_id,
                attempt_id=attempt_id,
            )
    return render(
        request,
        "assessments/attempt_evidence.html",
        {
            "program": program,
            "attempt": attempt,
            "event": attempt.participation.event,
            "form": form,
            "can_verify": VERIFY_PERMISSION in roles,
            "records": attempt.evidence_records.select_related(
                "verification__created_by",
                "invalidation",
                "superseded_by",
                "created_by",
                "source_link__capability__source",
                "source_link__capability__evidence_type",
            ),
        },
    )


def can_view_evidence_records(actor: User, roles: set[str]) -> bool:
    return (
        allowed(actor, roles, "assessments.view_assessmentevent")
        and can_view_attempts(actor, roles)
        and allowed(actor, roles, "evidence.view_evidencerecord")
    )


def require_evidence_view(actor: User, roles: set[str]) -> None:
    if not can_view_evidence_records(actor, roles):
        raise PermissionDenied


def scoped_evidence_attempts(program: StudyProgram, event_id: int):
    return AssessmentAttempt.objects.filter(
        participation__event_id=event_id,
        participation__event__in=program_events(program),
        participation__enrollment__cohort__period__program=program,
    ).select_related(
        "participation__enrollment__learner__account", "participation__event__component"
    )


class VerificationForm(forms.ModelForm):
    class Meta:
        model = EvidenceVerification
        fields = ["status", "reason"]


@require_http_methods(["GET", "POST"])
@login_required
def verify_evidence(
    request: HttpRequest, program_id: int, event_id: int, attempt_id: int, record_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    roles = program_role_permissions(actor, program_id)
    require_evidence_view(actor, roles)
    writing = request.method == "POST"
    action = request.POST.get("action", "verify") if writing else ""
    if writing and action not in {"verify", "correct", "invalidate"}:
        return HttpResponse(status=400)

    with transaction.atomic():
        attempts = scoped_evidence_attempts(program, event_id)
        if action == "correct":
            # Serialize corrections and new references for the same attempt.
            attempts = attempts.select_for_update(of=("self",))
        attempt = get_object_or_404(attempts, pk=attempt_id)
        records = attempt.evidence_records.select_related(
            "created_by",
            "import_batch",
            "source_link__capability__source",
            "source_link__capability__evidence_type",
            "supersedes",
            "superseded_by",
            "invalidation__created_by",
            "verification__created_by",
        )
        record = get_object_or_404(
            records.select_for_update(of=("self",)) if writing else records, pk=record_id
        )
        if writing:
            # Reverse relations may have changed while the record lock was being acquired.
            record.refresh_from_db()
        existing = getattr(record, "verification", None)
        invalidation = getattr(record, "invalidation", None)
        successor = getattr(record, "superseded_by", None)
        is_reviewer = VERIFY_PERMISSION in roles and record.created_by_id != actor.pk
        can_correct = allowed(actor, roles, "evidence.add_evidencerecord")
        if writing:
            if not (can_correct if action == "correct" else is_reviewer):
                raise PermissionDenied
            if (
                successor
                or (invalidation and action != "correct")
                or (existing and action == "verify")
            ):
                return HttpResponse(
                    "Aksi ini tidak tersedia untuk versi bukti tersebut.", status=409
                )

        form = correction_form = invalidation_form = None
        if not successor:
            if is_reviewer and not invalidation:
                invalidation_form = InvalidationForm(
                    request.POST if action == "invalidate" else None,
                    prefix="cancel",
                    instance=EvidenceInvalidation(record=record, created_by=actor),
                )
                if not existing:
                    form = VerificationForm(
                        request.POST if action == "verify" else None,
                        instance=EvidenceVerification(record=record, created_by=actor),
                    )
            if can_correct:
                correction_form = CorrectionForm(
                    request.POST if action == "correct" else None,
                    attempt=attempt,
                    prefix="correction",
                    instance=EvidenceRecord(
                        attempt=attempt,
                        supersedes=record,
                        source_link_id=record.source_link_id,
                        reference=record.reference,
                        context=record.context,
                        revision_number=record.revision_number + 1,
                        created_by=actor,
                    ),
                )

        submitted = {
            "verify": form,
            "correct": correction_form,
            "invalidate": invalidation_form,
        }.get(action)
        if submitted is not None and submitted.is_valid():
            updated = submitted.save(commit=False)
            if isinstance(updated, EvidenceRecord):
                get_object_or_404(
                    BlueprintItemEvidenceSource.objects.select_for_update(),
                    pk=updated.source_link_id,
                )
            updated.save()
            return redirect(
                "academics:assessments:attempt_evidence",
                program_id=program_id,
                event_id=event_id,
                attempt_id=attempt_id,
            )
    return render(
        request,
        "assessments/evidence_verification.html",
        {
            "program": program,
            "attempt": attempt,
            "event": attempt.participation.event,
            "record": record,
            "verification": existing,
            "form": form,
            "successor": successor,
            "invalidation": invalidation,
            "invalidation_form": invalidation_form,
            "correction_form": correction_form,
            "artifacts": record.artifacts.select_related("created_by"),
            "can_upload_artifact": can_correct and successor is None and invalidation is None,
        },
    )
