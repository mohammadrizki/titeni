from typing import cast

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.competencies.forms import (
    IndicatorForm,
    ItemForm,
    MilestoneForm,
    RelationshipForm,
    StandardForm,
)
from apps.competencies.models import (
    CompetencyFramework,
    CompetencyFrameworkVersion,
    CompetencyIndicator,
    CompetencyMilestone,
    CompetencyRelationship,
    PerformanceStandardVersion,
)


@require_http_methods(["GET", "POST"])
@login_required
def framework(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if request.method == "POST":
        with transaction.atomic():
            record, _ = CompetencyFramework.objects.get_or_create(program=program)
            record = CompetencyFramework.objects.select_for_update().get(pk=record.pk)
            latest = record.versions.first()
            draft = record.versions.create(
                number=latest.number + 1 if latest else 1, created_by=actor
            )
        return redirect("academics:competencies:draft", program_id=program_id, version_id=draft.pk)
    return render(
        request,
        "competencies/framework_drafts.html",
        {
            "program": program,
            "versions": CompetencyFrameworkVersion.objects.filter(framework__program=program),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def draft(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    drafts = CompetencyFrameworkVersion.objects.select_related("framework").filter(
        framework__program=program
    )
    version = get_object_or_404(drafts, pk=version_id)
    item_form = ItemForm(version=version)
    milestone_form = MilestoneForm(version=version)
    indicator_form = IndicatorForm(version=version, prefix="indicator")
    relationship_form = RelationshipForm(version=version, prefix="relationship")
    standard_form = StandardForm(version=version, prefix="standard")
    if request.method == "POST":
        with transaction.atomic():
            # Serialize additions so duplicate codes become form errors.
            version = get_object_or_404(drafts.select_for_update(of=("self",)), pk=version_id)
            form: ItemForm | MilestoneForm | IndicatorForm | RelationshipForm | StandardForm
            match request.POST.get("action"):
                case "item":
                    item_form = ItemForm(request.POST, version=version)
                    form = item_form
                case "indicator":
                    indicator_form = IndicatorForm(
                        request.POST, version=version, prefix="indicator"
                    )
                    form = indicator_form
                case "milestone":
                    milestone_form = MilestoneForm(request.POST, version=version)
                    form = milestone_form
                case "relationship":
                    relationship_form = RelationshipForm(
                        request.POST, version=version, prefix="relationship"
                    )
                    form = relationship_form
                case "standard":
                    standard_form = StandardForm(request.POST, version=version, prefix="standard")
                    form = standard_form
                case _:
                    return HttpResponse(status=400)
            if form.is_valid():
                if isinstance(form, StandardForm):
                    form.create_version(actor)
                else:
                    record = form.save(commit=False)
                    record.created_by = actor
                    record.save()
                return redirect(
                    "academics:competencies:draft", program_id=program_id, version_id=version_id
                )
    return render(
        request,
        "competencies/framework_draft.html",
        {
            "program": program,
            "version": version,
            "item_form": item_form,
            "milestone_form": milestone_form,
            "indicator_form": indicator_form,
            "indicators": CompetencyIndicator.objects.filter(item__version=version).select_related(
                "item"
            ),
            "relationship_form": relationship_form,
            "relationships": CompetencyRelationship.objects.filter(
                source__version=version
            ).select_related("source", "target"),
            "standard_form": standard_form,
            "standard_versions": PerformanceStandardVersion.objects.filter(
                standard__item__version=version
            )
            .select_related("standard__item")
            .order_by("standard__item__code", "standard__code", "-number"),
            "items": version.items.select_related("parent"),
            "milestones": CompetencyMilestone.objects.filter(item__version=version).select_related(
                "item", "stage__version__curriculum"
            ),
        },
    )
