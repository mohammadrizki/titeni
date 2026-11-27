from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.acquisition import allowed

from .models import EvidenceEvaluation
from .planning import AttemptOption, PlannedAttempt, PlanningRoute, propose_attempts

CONTEXT = "Cakupan konteks"
ASSESSOR = "Keberagaman asesor"


class PlanningDemonstrationForm(forms.Form):
    sufficiency = forms.ChoiceField(
        label="Kecukupan bukti sintetis", choices=EvidenceEvaluation.Sufficiency.choices
    )
    performance = forms.ChoiceField(
        label="Kesenjangan performa sintetis", choices=EvidenceEvaluation.Performance.choices
    )
    context_gap = forms.IntegerField(label="Kekurangan cakupan konteks", min_value=0, max_value=20)
    assessor_gap = forms.IntegerField(
        label="Kekurangan keberagaman asesor", min_value=0, max_value=20
    )
    combined_slots = forms.IntegerField(
        label="Slot percobaan yang mencakup kedua celah", min_value=0, max_value=20
    )
    context_slots = forms.IntegerField(label="Slot khusus konteks", min_value=0, max_value=20)
    assessor_slots = forms.IntegerField(label="Slot khusus asesor", min_value=0, max_value=20)
    pending = forms.IntegerField(
        label="Percobaan gabungan terjadwal dan belum dikerjakan", min_value=0, max_value=20
    )
    maximum_new = forms.IntegerField(label="Batas percobaan baru", min_value=0, max_value=20)

    def clean(self) -> dict:
        values = cast(dict, super().clean())
        if values.get("sufficiency") != EvidenceEvaluation.Sufficiency.SUFFICIENT and values.get(
            "performance"
        ) not in {None, EvidenceEvaluation.Performance.UNDETERMINED}:
            self.add_error("performance", "Performa tetap belum ditentukan jika bukti belum cukup.")
        return values


@require_http_methods(["GET", "POST"])
@login_required
def planning_demonstration(request: HttpRequest, program_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if not allowed(
        actor, program_role_permissions(actor, program_id), "adaptive.add_evidenceevaluation"
    ):
        raise PermissionDenied

    form = PlanningDemonstrationForm(request.POST if request.method == "POST" else None)
    proposal = None
    route_label = ""
    if form.is_valid():
        values = form.cleaned_data
        combined = AttemptOption(
            "Gabungan", frozenset({CONTEXT, ASSESSOR}), 1, values["combined_slots"]
        )
        options = (
            combined,
            AttemptOption("Khusus konteks", frozenset({CONTEXT}), 2, values["context_slots"]),
            AttemptOption("Khusus asesor", frozenset({ASSESSOR}), 2, values["assessor_slots"]),
        )
        proposal = propose_attempts(
            EvidenceEvaluation.Sufficiency(values["sufficiency"]),
            EvidenceEvaluation.Performance(values["performance"]),
            {CONTEXT: values["context_gap"], ASSESSOR: values["assessor_gap"]},
            options,
            tuple(
                PlannedAttempt(f"Percobaan terjadwal {number}", combined, True)
                for number in range(1, values["pending"] + 1)
            ),
            values["maximum_new"],
        )
        route_label = {
            PlanningRoute.ACQUIRE: "Rencana mencakup celah bukti",
            PlanningRoute.REVIEW: "Perlu tinjauan pengelola",
            PlanningRoute.INTERVENE: "Intervensi pembelajaran dan asesmen ulang",
            PlanningRoute.ATTAINMENT_REVIEW: "Tinjauan capaian",
        }[proposal.route]
    return render(
        request,
        "adaptive/planning_demonstration.html",
        {
            "program": program,
            "form": form,
            "proposal": proposal,
            "route_label": route_label,
        },
    )
