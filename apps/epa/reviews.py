from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, F, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe

from apps.academics.models import LearnerEnrollment
from apps.accounts.access import configurable_programs
from apps.accounts.models import User

from .models import (
    EntrustableProfessionalActivity,
    EntrustmentReview,
    EPAObservation,
    EPAPublication,
    EPAReviewAssignment,
)
from .observations import active_publication, kaprodi_can, program_grants

ASSIGN_REVIEW = "add_epareviewassignment"
REVIEW = "add_entrustmentreview"
REVIEWER_ROLE = "Peninjau EPA"


class ReviewAssignmentForm(forms.Form):
    enrollment = forms.ModelChoiceField(
        label="Pendaftaran mahasiswa", queryset=LearnerEnrollment.objects.none()
    )
    reviewer = forms.ModelChoiceField(label="Peninjau EPA", queryset=User.objects.none())

    def __init__(self, *args, program_id: int, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(
            forms.ModelChoiceField, self.fields["enrollment"]
        ).queryset = LearnerEnrollment.objects.filter(
            cohort__period__program_id=program_id
        ).select_related("learner__account", "cohort")
        cast(forms.ModelChoiceField, self.fields["reviewer"]).queryset = User.objects.filter(
            pk__in=program_grants(REVIEWER_ROLE, REVIEW)
            .filter(program_id=program_id)
            .values("account_id")
        ).order_by("username")

    def clean(self) -> dict:
        data = super().clean() or {}
        enrollment, reviewer = data.get("enrollment"), data.get("reviewer")
        if enrollment is not None and reviewer is not None:
            if reviewer.pk == enrollment.learner.account_id:
                self.add_error("reviewer", "Peninjau harus berbeda dari mahasiswa.")
        return data


class EvidenceChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj: EPAObservation) -> str:
        return (
            f"#{obj.pk} · {obj.occurred_on:%d-%m-%Y} · {obj.context} · "
            f"Versi EPA {obj.assignment.publication.version.number}"
        )


class ReviewDraftForm(forms.ModelForm):
    previous = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    observations = EvidenceChoiceField(
        label="Observasi pendukung",
        queryset=EPAObservation.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = EntrustmentReview
        fields = ("level", "rationale")

    def __init__(self, *args, assignment: EPAReviewAssignment, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(
            forms.ModelChoiceField, self.fields["level"]
        ).queryset = assignment.publication.version.scale.levels.all()
        cast(
            forms.ModelMultipleChoiceField, self.fields["observations"]
        ).queryset = review_observations(assignment)


def review_observations(assignment: EPAReviewAssignment) -> QuerySet[EPAObservation]:
    return EPAObservation.objects.filter(
        assignment__enrollment_id=assignment.enrollment_id,
        assignment__publication__version__activity_id=assignment.publication.version.activity_id,
        assignment__publication__version__number__lte=assignment.publication.version.number,
        level__version_id=F("assignment__publication__version__scale_id"),
    ).select_related(
        "assignment__assessor",
        "assignment__publication__version__activity",
        "assignment__enrollment__learner__account",
        "assignment__enrollment__cohort",
        "level__version__scale",
    )


def own_review_assignments(actor: User) -> QuerySet[EPAReviewAssignment]:
    programs = program_grants(REVIEWER_ROLE, REVIEW).filter(account=actor).values("program_id")
    return EPAReviewAssignment.objects.filter(
        reviewer=actor,
        publication__version__activity__program_id__in=programs,
        enrollment__cohort__period__program_id=F("publication__version__activity__program_id"),
    ).select_related(
        "publication__version__activity",
        "publication__version__scale__scale",
        "enrollment__learner__account",
        "enrollment__cohort",
    )


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def assign(
    request: HttpRequest, program_id: int, activity_id: int, version_id: int
) -> HttpResponse:
    actor = cast(User, request.user)
    if not kaprodi_can(actor, program_id, ASSIGN_REVIEW):
        raise PermissionDenied
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    publication = get_object_or_404(
        EPAPublication.objects.select_related("version__activity").filter(
            version__activity_id=activity_id, version__activity__program=program
        ),
        version_id=version_id,
    )
    writing = request.method == "POST"
    form = ReviewAssignmentForm(request.POST if writing else None, program_id=program_id)
    current = publication == active_publication(activity_id)
    if writing:
        with transaction.atomic():
            EntrustableProfessionalActivity.objects.select_for_update().get(pk=activity_id)
            if publication != active_publication(activity_id):
                return HttpResponse("Gunakan versi EPA yang sedang berlaku.", status=409)
            if form.is_valid():
                EPAReviewAssignment.objects.get_or_create(
                    publication=publication,
                    enrollment=form.cleaned_data["enrollment"],
                    reviewer=form.cleaned_data["reviewer"],
                    defaults={"created_by": actor},
                )
                return redirect(
                    "academics:epa:review_assignments", program_id, activity_id, version_id
                )
    return render(
        request,
        "epa/review_assignments.html",
        {
            "program": program,
            "publication": publication,
            "form": form if current else None,
            "assignments": EPAReviewAssignment.objects.filter(publication=publication)
            .select_related("enrollment__learner__account", "enrollment__cohort", "reviewer")
            .annotate(draft_count=Count("drafts")),
        },
        status=400 if writing else 200,
    )


@never_cache
@login_required
@require_safe
def queue(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "epa/review_queue.html",
        {"assignments": own_review_assignments(cast(User, request.user))},
    )


@never_cache
@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def draft(request: HttpRequest, assignment_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    assignments = own_review_assignments(actor)
    assignment = get_object_or_404(assignments, pk=assignment_id)
    latest = assignment.drafts.first()
    number = latest.number if latest else 0
    initial: dict[str, object] = {"previous": number}
    if latest is not None:
        initial.update(
            level=latest.level_id,
            rationale=latest.rationale,
            observations=list(latest.evidence.values_list("pk", flat=True)),
        )
    writing = request.method == "POST"
    form = ReviewDraftForm(
        request.POST if writing else None, initial=initial, assignment=assignment
    )
    status = 200
    if writing:
        with transaction.atomic():
            assignment = get_object_or_404(
                assignments.select_for_update(of=("self",)), pk=assignment_id
            )
            latest = assignment.drafts.first()
            number = latest.number if latest else 0
            status = 400
            if form.is_valid():
                if form.cleaned_data["previous"] != number:
                    form.add_error(
                        None, "Draf sudah berubah. Muat ulang halaman untuk melanjutkan."
                    )
                    status = 409
                else:
                    review = form.save(commit=False)
                    review.assignment = assignment
                    review.number = number + 1
                    review.created_by = actor
                    review.save()
                    review.evidence.add(*form.cleaned_data["observations"])
                    return redirect("epa_review_draft", assignment_id)
    return render(
        request,
        "epa/review_draft.html",
        {
            "assignment": assignment,
            "form": form,
            "observations": review_observations(assignment),
            "drafts": assignment.drafts.select_related("level").prefetch_related("evidence"),
        },
        status=status,
    )
