from typing import cast

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.assessments.forms import (
    BlueprintEvidenceSourceForm,
    BlueprintItemForm,
    BlueprintMappingForm,
    BlueprintVersionForm,
    SamplingRuleForm,
)
from apps.assessments.models import (
    AssessmentBlueprint,
    AssessmentBlueprintVersion,
    AssessmentSamplingRule,
    BlueprintItemCompetency,
    BlueprintItemEvidenceSource,
)
from apps.evidence.models import EvidenceSourceCapability


@require_http_methods(["GET", "POST"])
@login_required
def blueprints(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    form = BlueprintVersionForm(request.POST if request.method == "POST" else None, program=program)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            blueprint, _ = AssessmentBlueprint.objects.get_or_create(program=program)
            blueprint = AssessmentBlueprint.objects.select_for_update().get(pk=blueprint.pk)
            latest = blueprint.versions.first()
            version = form.save(commit=False)
            version.blueprint = blueprint
            version.number = latest.number + 1 if latest else 1
            version.created_by = actor
            version.save()
        return redirect(
            "academics:assessments:blueprint_draft", program_id=program_id, version_id=version.pk
        )
    return render(
        request,
        "assessments/blueprints.html",
        {
            "program": program,
            "form": form,
            "versions": AssessmentBlueprintVersion.objects.filter(
                blueprint__program=program
            ).select_related("framework_version"),
        },
    )


@require_http_methods(["GET", "POST"])
@login_required
def blueprint_draft(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    versions = AssessmentBlueprintVersion.objects.filter(
        blueprint__program_id=program_id, blueprint__program__in=configurable_programs(actor)
    ).select_related("blueprint__program", "framework_version")
    version = get_object_or_404(versions, pk=version_id)
    item_form = BlueprintItemForm(version=version)
    mapping_form = BlueprintMappingForm(version=version)
    sampling_form = SamplingRuleForm(version=version, prefix="sampling")
    source_form = BlueprintEvidenceSourceForm(version=version, prefix="source")
    if request.method == "POST":
        with transaction.atomic():
            version = get_object_or_404(versions.select_for_update(of=("self",)), pk=version_id)
            form: (
                BlueprintItemForm
                | BlueprintMappingForm
                | SamplingRuleForm
                | BlueprintEvidenceSourceForm
            )
            match request.POST.get("action"):
                case "item":
                    item_form = BlueprintItemForm(request.POST, version=version)
                    form = item_form
                case "mapping":
                    mapping_form = BlueprintMappingForm(request.POST, version=version)
                    form = mapping_form
                case "sampling":
                    sampling_form = SamplingRuleForm(
                        request.POST, version=version, prefix="sampling"
                    )
                    form = sampling_form
                case "source":
                    source_form = BlueprintEvidenceSourceForm(
                        request.POST, version=version, prefix="source"
                    )
                    form = source_form
                case _:
                    return HttpResponse(status=400)
            if form.is_valid():
                record = form.save(commit=False)
                if isinstance(record, BlueprintItemEvidenceSource):
                    get_object_or_404(
                        EvidenceSourceCapability.objects.select_for_update(),
                        pk=record.capability_id,
                    )
                record.created_by = actor
                record.save()
                return redirect(
                    "academics:assessments:blueprint_draft",
                    program_id=program_id,
                    version_id=version_id,
                )
    return render(
        request,
        "assessments/blueprint_draft.html",
        {
            "program": version.blueprint.program,
            "version": version,
            "item_form": item_form,
            "mapping_form": mapping_form,
            "sampling_form": sampling_form,
            "sampling_rules": AssessmentSamplingRule.objects.filter(
                item__version=version
            ).select_related("item"),
            "source_form": source_form,
            "evidence_sources": BlueprintItemEvidenceSource.objects.filter(
                item__version=version
            ).select_related("item", "capability__source", "capability__evidence_type"),
            "items": version.items.select_related("stage__version__curriculum"),
            "mappings": BlueprintItemCompetency.objects.filter(
                item__version=version
            ).select_related("item", "competency", "indicator"),
        },
    )
