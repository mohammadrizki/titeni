from dataclasses import dataclass, field
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, models, transaction
from django.forms import ModelChoiceField, modelform_factory
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.academics.models import (
    AcademicPeriod,
    Cohort,
    Curriculum,
    CurriculumStage,
    LearnerEnrollment,
    StudyProgram,
)
from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.assessments.models import (
    AssessmentBlueprintVersion,
    AssessmentSamplingRule,
    BlueprintItem,
    BlueprintItemCompetency,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import (
    CompetencyFrameworkVersion,
    CompetencyIndicator,
    CompetencyItem,
    CompetencyMilestone,
    CompetencyRelationship,
    PerformanceStandardVersion,
)
from apps.evidence.models import (
    EvidenceRequirementTemplate,
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceSourceCompetency,
    EvidenceType,
)


@dataclass(frozen=True)
class Row:
    model: type[models.Model]
    scope: str
    fields: tuple[str, ...]
    page: str
    parent: str = ""
    choices: dict[str, tuple[str, str]] = field(default_factory=dict)


ROWS = {
    "persyaratan-bukti": Row(
        EvidenceRequirementTemplate,
        "blueprint_version__blueprint__program",
        ("code", "name", "competency", "capability", "minimum_count", "context"),
        "evidence:evidence_requirements",
        "blueprint_version_id",
        {
            "competency": ("version_id", "blueprint_version.framework_version_id"),
            "capability": ("source__program_id", "blueprint_version.blueprint.program_id"),
        },
    ),
    "sumber-bukti": Row(
        EvidenceSource,
        "program",
        ("code", "name", "acquisition", "verification"),
        "evidence:registry",
    ),
    "jenis-bukti": Row(EvidenceType, "program", ("code", "name"), "evidence:registry"),
    "kapabilitas-sumber": Row(
        EvidenceSourceCapability,
        "source__program",
        ("evidence_type",),
        "evidence:registry",
        choices={"evidence_type": ("program_id", "source.program_id")},
    ),
    "kompetensi-sumber": Row(
        EvidenceSourceCompetency,
        "source__program",
        ("competency",),
        "evidence:registry",
        choices={"competency": ("version__framework__program_id", "source.program_id")},
    ),
    "periode": Row(AcademicPeriod, "program", ("code", "name", "starts_on", "ends_on"), "periods"),
    "kohort": Row(
        Cohort,
        "period__program",
        ("code", "name", "period"),
        "cohorts",
        choices={"period": ("program_id", "period.program_id")},
    ),
    "mahasiswa": Row(
        LearnerEnrollment, "cohort__period__program", ("enrolled_on",), "enrollments", "cohort_id"
    ),
    "kurikulum": Row(Curriculum, "program", ("code", "name"), "curricula"),
    "tahap": Row(
        CurriculumStage,
        "version__curriculum__program",
        ("code", "name"),
        "curriculum_version",
        "version_id",
    ),
    "butir": Row(
        CompetencyItem,
        "version__framework__program",
        ("code", "name", "parent"),
        "competencies:draft",
        "version_id",
        {"parent": ("version_id", "version_id")},
    ),
    "indikator": Row(
        CompetencyIndicator,
        "item__version__framework__program",
        ("code", "description"),
        "competencies:draft",
        "item.version_id",
    ),
    "milestone": Row(
        CompetencyMilestone,
        "item__version__framework__program",
        ("stage", "expectation"),
        "competencies:draft",
        "item.version_id",
        {"stage": ("version__curriculum__program_id", "item.version.framework.program_id")},
    ),
    "relasi": Row(
        CompetencyRelationship,
        "source__version__framework__program",
        ("target", "description"),
        "competencies:draft",
        "source.version_id",
        {"target": ("version_id", "source.version_id")},
    ),
    "standar": Row(
        PerformanceStandardVersion,
        "standard__item__version__framework__program",
        ("description",),
        "competencies:draft",
        "standard.item.version_id",
    ),
    "blueprint": Row(
        AssessmentBlueprintVersion,
        "blueprint__program",
        ("framework_version",),
        "assessments:blueprints",
        choices={"framework_version": ("framework__program_id", "blueprint.program_id")},
    ),
    "komponen": Row(
        BlueprintItem,
        "version__blueprint__program",
        ("code", "name", "method", "purpose", "stage", "timing"),
        "assessments:blueprint_draft",
        "version_id",
        {"stage": ("version__curriculum__program_id", "version.blueprint.program_id")},
    ),
    "pemetaan": Row(
        BlueprintItemCompetency,
        "item__version__blueprint__program",
        ("competency", "indicator"),
        "assessments:blueprint_draft",
        "item.version_id",
        {
            "competency": ("version_id", "item.version.framework_version_id"),
            "indicator": ("item__version_id", "item.version.framework_version_id"),
        },
    ),
    "sumber-blueprint": Row(
        BlueprintItemEvidenceSource,
        "item__version__blueprint__program",
        ("capability",),
        "assessments:blueprint_draft",
        "item.version_id",
        {"capability": ("source__program_id", "item.version.blueprint.program_id")},
    ),
    "sampling": Row(
        AssessmentSamplingRule,
        "item__version__blueprint__program",
        ("context", "minimum_observations"),
        "assessments:blueprint_draft",
        "item.version_id",
    ),
}


def permission(spec: Row, action: str) -> str:
    meta = spec.model._meta
    return f"{meta.app_label}.{action}_{meta.model_name}"


def related_value(record: models.Model, path: str) -> Any:
    value = record
    for name in path.split("."):
        value = getattr(value, name)
    return value


def editable(record: models.Model) -> bool:
    if isinstance(record, AssessmentBlueprintVersion):
        return not (record.items.exists() or record.manual_evidence_requirements.exists())
    if isinstance(record, BlueprintItem):
        return not record.events.exists()
    if isinstance(record, BlueprintItemEvidenceSource):
        return not record.acquired_records.exists()
    if isinstance(record, EvidenceSourceCapability):
        return not (record.blueprint_links.exists() or record.evidence_requirements.exists())
    return True


@require_http_methods(["GET", "POST"])
@login_required
def row_action(
    request: HttpRequest, program_id: int, kind: str, row_id: int, action: str
) -> HttpResponse:
    spec = ROWS.get(kind)
    if spec is None or action not in {"lihat", "sunting", "hapus"}:
        raise Http404
    if action == "lihat" and request.method == "POST":
        return HttpResponse(status=405, headers={"Allow": "GET"})

    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    if kind == "mahasiswa" and not actor.has_perm(permission(spec, "view")):
        raise PermissionDenied
    if action != "lihat":
        required = permission(spec, "change" if action == "sunting" else "delete")
        if not actor.has_perm(required) and required not in program_role_permissions(
            actor, program_id
        ):
            raise PermissionDenied

    records = spec.model._default_manager.filter(**{spec.scope: program})
    error = ""
    with transaction.atomic():
        record = get_object_or_404(records, pk=row_id)
        parent_id = related_value(record, spec.parent) if spec.parent else None
        if request.method == "POST":
            # Match the locks used by the draft creation views before modifying a child.
            if spec.page == "competencies:draft":
                get_object_or_404(
                    CompetencyFrameworkVersion.objects.select_for_update(), pk=parent_id
                )
            elif spec.page in {"assessments:blueprint_draft", "evidence:evidence_requirements"}:
                get_object_or_404(
                    AssessmentBlueprintVersion.objects.select_for_update(), pk=parent_id
                )
            record = get_object_or_404(records.select_for_update(of=("self",)), pk=row_id)
        args = [program_id]
        if parent_id is not None:
            args.append(parent_id)
        back_url = reverse(f"academics:{spec.page}", args=args)
        form = None
        if action == "sunting":
            if not editable(record):
                return HttpResponse("Baris sudah digunakan dan tidak dapat disunting.", status=409)
            form_class = modelform_factory(spec.model, fields=spec.fields)
            form = form_class(request.POST if request.method == "POST" else None, instance=record)
            for name, (lookup, path) in spec.choices.items():
                choice = cast(ModelChoiceField, form.fields[name])
                assert choice.queryset is not None
                choice.queryset = choice.queryset.filter(**{lookup: related_value(record, path)})
            if isinstance(record, Cohort) and record.enrollments.exists():
                form.fields["period"].disabled = True
                form.fields["period"].help_text = "Kohort ini sudah memiliki pendaftaran mahasiswa."
            if request.method == "POST" and form.is_valid():
                try:
                    with transaction.atomic():
                        if isinstance(
                            record, (BlueprintItemEvidenceSource, EvidenceRequirementTemplate)
                        ):
                            get_object_or_404(
                                EvidenceSourceCapability.objects.select_for_update(),
                                pk=record.capability_id,
                            )
                        if isinstance(record, PerformanceStandardVersion):
                            standard = (
                                type(record.standard)
                                .objects.select_for_update()
                                .get(pk=record.standard_id)
                            )
                            latest = standard.versions.first()
                            assert latest is not None
                            standard.versions.create(
                                number=latest.number + 1,
                                description=form.cleaned_data["description"],
                                created_by=actor,
                            )
                        else:
                            form.save()
                except IntegrityError:
                    form.add_error(None, "Perubahan bertentangan dengan data yang tersimpan.")
                else:
                    messages.success(request, "Perubahan berhasil disimpan.")
                    return redirect(back_url)
        if action == "hapus" and request.method == "POST":
            try:
                with transaction.atomic():
                    if isinstance(record, Curriculum):
                        # The initial blank draft is created together with the curriculum.
                        record.versions.all().delete()
                    record.delete()
            except IntegrityError:
                error = "Baris masih dirujuk oleh data lain."
            else:
                messages.success(request, "Baris berhasil dihapus.")
                return redirect(back_url)

    details = [
        (cast(models.Field, record._meta.get_field(name)).verbose_name, getattr(record, name))
        for name in spec.fields
    ]
    context_fields = {
        "kapabilitas-sumber": (("Sumber bukti", "source"),),
        "kompetensi-sumber": (("Sumber bukti", "source"),),
        "mahasiswa": (("Nama pengguna", "learner"), ("Kohort", "cohort")),
        "indikator": (("Butir kompetensi", "item"),),
        "milestone": (("Butir kompetensi", "item"),),
        "relasi": (("Butir asal", "source"),),
        "standar": (("Standar performa", "standard"), ("Versi draf", "number")),
        "blueprint": (("Versi draf blueprint", "number"),),
        "pemetaan": (("Komponen asesmen", "item"),),
        "sumber-blueprint": (("Komponen asesmen", "item"),),
        "sampling": (("Komponen asesmen", "item"),),
    }
    context = [(label, getattr(record, name)) for label, name in context_fields.get(kind, ())]
    details = context + details
    return render(
        request,
        "academics/row_action.html",
        {
            "program": program,
            "record": record,
            "action": action,
            "form": form,
            "details": details,
            "back_url": back_url,
            "error": error,
            "versioned": isinstance(record, PerformanceStandardVersion),
            "curriculum": isinstance(record, Curriculum),
        },
        status=409 if error else 200,
    )


@require_http_methods(["GET"])
@login_required
def preview_program(request: HttpRequest, program_id: int) -> HttpResponse:
    if not request.user.has_perms(
        ("accounts.access_system_workspace", "academics.add_studyprogram")
    ):
        raise PermissionDenied
    program = get_object_or_404(StudyProgram, pk=program_id, institution_id=1)
    return render(
        request,
        "academics/row_action.html",
        {
            "program": program,
            "record": program,
            "action": "lihat",
            "back_url": reverse("academics:register_program"),
            "details": [
                ("Kode", program.code),
                ("Nama program studi", program.name),
                ("Jenjang", program.get_education_stage_display()),
            ],
        },
    )
