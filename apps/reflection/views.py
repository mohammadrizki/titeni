from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.academics.models import LearnerEnrollment
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.competencies.models import CompetencyItem
from apps.evidence.models import EvidenceRecord, LearnerEvidenceBaseline

from .models import Reflection, ReflectionPrompt
from .summary import summarize_evidence


class DraftForm(forms.Form):
    body = forms.CharField(label="Refleksi pribadi", max_length=10000, widget=forms.Textarea)
    evidence = forms.ModelMultipleChoiceField(
        label="Bukti terverifikasi", queryset=EvidenceRecord.objects.none(), required=False
    )
    competencies = forms.ModelMultipleChoiceField(
        label="Kompetensi dari baseline", queryset=CompetencyItem.objects.none(), required=False
    )
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


def own_enrollments(actor: User) -> QuerySet[LearnerEnrollment]:
    programs = UserRoleAssignment.objects.filter(
        account=actor,
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="reflection",
        role__permissions__codename="add_reflection",
    ).values("program_id")
    return LearnerEnrollment.objects.filter(
        learner__account=actor,
        learner__account__is_active=True,
        cohort__period__program_id__in=programs,
    )


@never_cache
@require_http_methods(["GET"])
@login_required
def index(request: HttpRequest) -> HttpResponse:
    enrollments = own_enrollments(cast(User, request.user)).select_related(
        "cohort__period__program"
    )
    return render(request, "reflection/index.html", {"enrollments": enrollments})


@never_cache
@sensitive_post_parameters()
@require_http_methods(["GET", "POST"])
@login_required
def drafts(
    request: HttpRequest, enrollment_id: int, reflection_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    enrollment = get_object_or_404(own_enrollments(actor), pk=enrollment_id)
    own_drafts = Reflection.objects.filter(enrollment=enrollment)
    owned_evidence = EvidenceRecord.objects.filter(
        attempt__participation__enrollment=enrollment,
        attempt__participation__event__component__version__blueprint__program_id=(
            enrollment.cohort.period.program_id
        ),
    )
    candidates = EvidenceRecord.objects.eligible_for_reconciliation().filter(pk__in=owned_evidence)
    program_id = enrollment.cohort.period.program_id
    framework_versions = LearnerEvidenceBaseline.objects.filter(
        enrollment=enrollment,
        publication__artifact_map__program_id=program_id,
        publication__version__blueprint_version__blueprint__program_id=program_id,
    ).values("publication__version__blueprint_version__framework_version_id")
    competencies = CompetencyItem.objects.filter(
        version_id__in=framework_versions, version__framework__program_id=program_id
    )
    selected = None
    status = 200
    with transaction.atomic():
        if reflection_id is not None:
            scoped = own_drafts.select_for_update() if request.method == "POST" else own_drafts
            selected = get_object_or_404(scoped, pk=reflection_id)
        latest = selected.revisions.first() if selected else None
        number = latest.number if latest else 0
        previous_evidence = set(latest.evidence.values_list("pk", flat=True)) if latest else set()
        previous_competencies = (
            set(latest.competencies.values_list("pk", flat=True)) if latest else set()
        )
        form = DraftForm(
            request.POST if request.method == "POST" else None,
            initial={
                "body": latest.body if latest else "",
                "revision": number,
                "evidence": previous_evidence,
                "competencies": previous_competencies,
            },
        )
        cast(forms.ModelMultipleChoiceField, form.fields["evidence"]).queryset = candidates
        cast(forms.ModelMultipleChoiceField, form.fields["competencies"]).queryset = competencies
        if request.method == "POST" and form.is_valid():
            if form.cleaned_data["revision"] != number:
                form.add_error(None, "Draf sudah berubah. Salin teks Anda dan buka versi terbaru.")
                status = 409
            else:
                evidence_ids = {record.pk for record in form.cleaned_data["evidence"]}
                list(
                    EvidenceRecord.objects.select_for_update()
                    .filter(pk__in=evidence_ids)
                    .order_by("pk")
                    .values_list("pk", flat=True)
                )
                if (
                    set(candidates.filter(pk__in=evidence_ids).values_list("pk", flat=True))
                    != evidence_ids
                ):
                    form.add_error(
                        "evidence", "Pilihan bukti berubah. Periksa kembali daftar bukti."
                    )
                    status = 409
                else:
                    selected = selected or own_drafts.create(enrollment=enrollment)
                    body = form.cleaned_data["body"]
                    competency_ids = {item.pk for item in form.cleaned_data["competencies"]}
                    if (
                        latest is None
                        or latest.body != body
                        or previous_evidence != evidence_ids
                        or previous_competencies != competency_ids
                    ):
                        version = selected.revisions.create(number=number + 1, body=body)
                        version.evidence.set(evidence_ids)
                        version.competencies.set(competency_ids)
                    return redirect("reflection_draft", enrollment.pk, selected.pk)

    program_prompts = list(
        ReflectionPrompt.objects.filter(program_id=program_id).values_list("text", "is_active")
    )
    return render(
        request,
        "reflection/drafts.html",
        {
            "enrollment": enrollment,
            "selected": selected,
            "drafts": own_drafts,
            "form": form,
            "program_prompts": [prompt for prompt, active in program_prompts if active],
            "use_default_prompts": not program_prompts,
            "prompt_competencies": competencies.filter(pk__in=previous_competencies),
            "has_competency_choices": competencies.exists(),
            "evidence_summary": summarize_evidence(latest, owned_evidence, candidates)
            if latest
            else None,
            "revisions": (
                selected.revisions.prefetch_related(
                    Prefetch("evidence", queryset=owned_evidence),
                    Prefetch("competencies", queryset=competencies),
                )
                if selected
                else ()
            ),
        },
        status=status,
    )
