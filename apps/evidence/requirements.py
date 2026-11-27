from typing import cast

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import require_program_permission
from apps.accounts.models import User
from apps.evidence.artifact_map import scoped_blueprints
from apps.evidence.forms import EvidenceRequirementForm
from apps.evidence.models import EvidenceSourceCapability


@require_http_methods(["GET", "POST"])
@login_required
def evidence_requirements(request: HttpRequest, program_id: int, version_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    blueprints = scoped_blueprints(actor, program_id)
    with transaction.atomic():
        writing = request.method == "POST"
        version = get_object_or_404(
            blueprints.select_for_update(of=("self",)) if writing else blueprints, pk=version_id
        )
        if writing:
            require_program_permission(
                actor, program_id, "evidence.add_evidencerequirementtemplate"
            )
        form = EvidenceRequirementForm(request.POST if writing else None, version=version)
        if writing and form.is_valid():
            requirement = form.save(commit=False)
            get_object_or_404(
                EvidenceSourceCapability.objects.select_for_update(), pk=requirement.capability_id
            )
            requirement.created_by = actor
            requirement.save()
            return redirect(
                "academics:evidence:evidence_requirements",
                program_id=program_id,
                version_id=version_id,
            )
    return render(
        request,
        "evidence/requirement_drafts.html",
        {
            "program": version.blueprint.program,
            "version": version,
            "form": form,
            "requirements": version.manual_evidence_requirements.select_related(
                "competency", "capability__source", "capability__evidence_type"
            ),
        },
    )
