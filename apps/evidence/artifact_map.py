from collections import defaultdict
from typing import cast

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.assessments.models import (
    AssessmentBlueprintVersion,
    BlueprintItem,
    BlueprintItemCompetency,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyMilestone
from apps.evidence.models import ArtifactMap, ArtifactMapVersion, EvidenceSourceCompetency
from apps.evidence.publications import can_publish


def scoped_blueprints(actor: User, program_id: int) -> QuerySet[AssessmentBlueprintVersion]:
    return AssessmentBlueprintVersion.objects.filter(
        blueprint__program_id=program_id,
        blueprint__program__in=configurable_programs(actor),
    ).select_related("blueprint__program", "framework_version")


def blueprint_proposals(components: list[BlueprintItem]) -> list[dict]:
    proposals = []
    for component in components:
        targets = [
            {
                "competency_id": mapping.competency_id,
                "indicator_id": mapping.indicator_id,
                "label": target_label(mapping, str(mapping.competency)),
            }
            for mapping in component.blueprintitemcompetency_set.all()
        ]
        sources = [
            {"capability_id": link.capability_id, "label": str(link.capability)}
            for link in component.blueprintitemevidencesource_set.all()
        ]
        if not targets or not sources:
            continue
        for rule in component.assessmentsamplingrule_set.all():
            proposals.append(
                {
                    "component_id": component.pk,
                    "component": str(component),
                    "sampling_rule_id": rule.pk,
                    "context": rule.context,
                    "minimum_observations": rule.minimum_observations,
                    "targets": targets,
                    "sources": sources,
                }
            )
    return proposals


def build_snapshot(version: AssessmentBlueprintVersion) -> dict:
    program_id = version.blueprint.program_id
    components = list(
        version.items.select_related("stage__version__curriculum").prefetch_related(
            Prefetch(
                "blueprintitemcompetency_set",
                queryset=BlueprintItemCompetency.objects.select_related("competency", "indicator"),
            ),
            Prefetch(
                "blueprintitemevidencesource_set",
                queryset=BlueprintItemEvidenceSource.objects.select_related(
                    "capability__source", "capability__evidence_type"
                ),
            ),
            "assessmentsamplingrule_set",
        )
    )
    by_competency: defaultdict[int, list[BlueprintItemCompetency]] = defaultdict(list)
    for component in components:
        for mapping in component.blueprintitemcompetency_set.all():
            by_competency[mapping.competency_id].append(mapping)

    registry: defaultdict[int, list[EvidenceSourceCompetency]] = defaultdict(list)
    for source_mapping in EvidenceSourceCompetency.objects.filter(
        source__program_id=program_id, competency__version=version.framework_version
    ).select_related("source"):
        registry[source_mapping.competency_id].append(source_mapping)

    milestones: defaultdict[int, list[CompetencyMilestone]] = defaultdict(list)
    for milestone in CompetencyMilestone.objects.filter(
        item__version=version.framework_version,
        stage__version__curriculum__program_id=program_id,
    ).select_related("stage__version__curriculum"):
        milestones[milestone.item_id].append(milestone)

    return {
        "blueprint_number": version.number,
        "framework_number": version.framework_version.number,
        "blueprint_proposals": blueprint_proposals(components),
        "requirements": [
            {
                "label": str(requirement),
                "capability_id": requirement.capability_id,
                "competency_id": requirement.competency_id,
                "competency": str(requirement.competency),
                "source": str(requirement.capability),
                "minimum": requirement.minimum_count,
                "context": requirement.context,
            }
            for requirement in version.manual_evidence_requirements.select_related(
                "competency", "capability__source", "capability__evidence_type"
            )
        ],
        "components": [
            {
                "id": component.pk,
                "label": str(component),
                "stage": f"{component.stage.version} · {component.stage}",
                "targets": [
                    target_label(mapping, str(mapping.competency))
                    for mapping in component.blueprintitemcompetency_set.all()
                ],
                "sources": [
                    str(link.capability) for link in component.blueprintitemevidencesource_set.all()
                ],
                "sampling": [
                    {"context": rule.context, "minimum": rule.minimum_observations}
                    for rule in component.assessmentsamplingrule_set.all()
                ],
            }
            for component in components
        ],
        "coverage": [
            {
                "id": item.pk,
                "label": str(item),
                "blueprint": [
                    target_label(mapping, str(mapping.item)) for mapping in by_competency[item.pk]
                ],
                "registry": [str(mapping.source) for mapping in registry[item.pk]],
                "milestones": [
                    f"{milestone.stage.version} · {milestone.stage} · {milestone.expectation}"
                    for milestone in milestones[item.pk]
                ],
            }
            for item in version.framework_version.items.all()
        ],
    }


def target_label(mapping: BlueprintItemCompetency, label: str) -> str:
    return f"{label} · {mapping.indicator}" if mapping.indicator is not None else label


@require_safe
@login_required
def artifact_maps(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    return render(
        request,
        "evidence/artifact_maps.html",
        {
            "program": program,
            "blueprints": scoped_blueprints(actor, program_id),
            "versions": ArtifactMapVersion.objects.filter(
                artifact_map__program=program, blueprint_version__blueprint__program=program
            )
            .select_related("blueprint_version", "publication")
            .defer("snapshot"),
        },
    )


@require_safe
@login_required
def artifact_map(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    version = get_object_or_404(
        scoped_blueprints(cast(User, request.user), program_id), pk=version_id
    )
    return render(
        request,
        "evidence/artifact_map.html",
        {
            "program": version.blueprint.program,
            "version": version,
            "snapshot": build_snapshot(version),
            "has_blueprint_proposals": True,
            "history": ArtifactMapVersion.objects.filter(
                artifact_map__program_id=program_id, blueprint_version=version
            ).defer("snapshot"),
        },
    )


@require_POST
@login_required
def save_artifact_map(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    with transaction.atomic():
        version = get_object_or_404(
            scoped_blueprints(actor, program_id).select_for_update(of=("self",)), pk=version_id
        )
        record, _ = ArtifactMap.objects.get_or_create(program_id=program_id)
        record = ArtifactMap.objects.select_for_update().get(pk=record.pk)
        latest = record.versions.defer("snapshot").first()
        saved = record.versions.create(
            blueprint_version=version,
            number=latest.number + 1 if latest else 1,
            snapshot=build_snapshot(version),
            created_by=actor,
        )
    return redirect("academics:evidence:saved_artifact_map", program_id=program_id, map_id=saved.pk)


@require_safe
@login_required
def saved_artifact_map(request: HttpRequest, program_id: int, map_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    saved = get_object_or_404(
        ArtifactMapVersion.objects.select_related(
            "artifact_map__program", "blueprint_version", "publication"
        ),
        pk=map_id,
        artifact_map__program_id=program_id,
        artifact_map__program__in=configurable_programs(actor),
        blueprint_version__blueprint__program_id=program_id,
    )
    return render(
        request,
        "evidence/artifact_map.html",
        {
            "program": saved.artifact_map.program,
            "version": saved.blueprint_version,
            "snapshot": saved.snapshot,
            "saved": saved,
            "publication": getattr(saved, "publication", None),
            "can_publish": can_publish(actor, program_id),
            "has_blueprint_proposals": "blueprint_proposals" in saved.snapshot,
        },
    )
