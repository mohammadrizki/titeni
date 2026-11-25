from typing import cast

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs
from apps.accounts.models import User
from apps.evidence.forms import CapabilityForm, EvidenceTypeForm, SourceCompetencyForm, SourceForm
from apps.evidence.models import (
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceSourceCompetency,
    EvidenceType,
)

REGISTRY_FORMS = {
    "source": SourceForm,
    "type": EvidenceTypeForm,
    "capability": CapabilityForm,
    "competency": SourceCompetencyForm,
}


@require_http_methods(["GET", "POST"])
@login_required
def registry(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    action = request.POST.get("action") if request.method == "POST" else None
    if request.method == "POST" and action not in REGISTRY_FORMS:
        return HttpResponse(status=400)
    forms = {
        name: form_class(request.POST if name == action else None, program=program, prefix=name)
        for name, form_class in REGISTRY_FORMS.items()
    }
    if action is not None:
        form = forms[action]
        if form.is_valid():
            try:
                with transaction.atomic():
                    record = form.save(commit=False)
                    record.created_by = actor
                    record.save()
            except IntegrityError:
                form.add_error(None, "Entri bertentangan dengan data registri yang tersimpan.")
            else:
                return redirect("academics:evidence:registry", program_id=program_id)
    return render(
        request,
        "evidence/source_registry.html",
        {
            "program": program,
            "forms": forms,
            "sources": EvidenceSource.objects.filter(program=program),
            "types": EvidenceType.objects.filter(program=program),
            "capabilities": EvidenceSourceCapability.objects.filter(
                source__program=program
            ).select_related("source", "evidence_type"),
            "competencies": EvidenceSourceCompetency.objects.filter(
                source__program=program
            ).select_related("source", "competency__version"),
        },
    )
