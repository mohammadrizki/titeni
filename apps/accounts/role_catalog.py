from dataclasses import dataclass

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import transaction

from . import guide_content
from .models import AccessRole, User


def permissions(app: str, actions: str, *models: str) -> frozenset[str]:
    return frozenset(f"{app}.{action}_{model}" for action in actions.split() for model in models)


ACADEMIC = permissions("academics", "view add change delete", "academicperiod", "cohort")
ENROLLMENT = permissions("academics", "view add change", "learnerenrollment")
CURRICULUM = (
    permissions("reflection", "view add change", "reflectionprompt")
    | permissions("academics", "view add change delete", "curriculum", "curriculumstage")
    | permissions("academics", "view add", "curriculumversion")
    | permissions("competencies", "view add", "competencyframework", "competencyframeworkversion")
    | permissions(
        "competencies",
        "view add change delete",
        "competencyitem",
        "competencyindicator",
        "competencymilestone",
        "competencyrelationship",
        "performancestandardversion",
    )
)
PROGRAM_ANALYTICS = permissions("adaptive", "view", "programanalyticsreport")
EPA_CONFIGURATION = permissions(
    "epa",
    "view add",
    "entrustableprofessionalactivity",
    "epaversion",
    "epacompetencylink",
    "supervisionscale",
    "supervisionscaleversion",
    "supervisionlevel",
)
BLUEPRINT = permissions(
    "assessments", "view add", "assessmentblueprint", "assessmentblueprintversion"
) | permissions(
    "assessments",
    "view add change delete",
    "blueprintitem",
    "blueprintitemcompetency",
    "assessmentsamplingrule",
    "blueprintitemevidencesource",
)
REGISTRY = permissions(
    "evidence",
    "view add change delete",
    "evidencesource",
    "evidencetype",
    "evidencesourcecapability",
    "evidencesourcecompetency",
    "evidencerequirementtemplate",
)
EVIDENCE_READ = frozenset(
    {
        "academics.view_learnerenrollment",
        "assessments.view_assessmentevent",
        "assessments.view_assessmentattempt",
        "evidence.view_evidencerecord",
    }
)
PLAN_READ = EVIDENCE_READ | {"evidence.view_learnerevidenceplan"}
OPERATE_ASSESSMENTS = EVIDENCE_READ | {
    "assessments.add_assessmentevent",
    "assessments.add_assessmentattempt",
    "assessments.view_examresultimport",
    "assessments.add_examresultimport",
    "evidence.add_evidencerecord",
}
PORTFOLIO = (
    PLAN_READ
    | REGISTRY
    | {
        "evidence.view_artifactmapversion",
        "evidence.add_artifactmapversion",
        "evidence.add_learnerevidenceplan",
        "evidence.add_evidenceplacement",
    }
)
# Longitudinal review reuses scoped evaluation permissions and the recipient
# permissions in Pembimbing Refleksi for shared material.
ADAPTATION = PLAN_READ | {
    "adaptive.view_evidenceevaluation",
    "adaptive.add_evidenceevaluation",
    "adaptive.add_evaluationruleversion",
    "adaptive.add_evaluationruleretirement",
    "adaptive.add_assessorfindingassignment",
    "adaptive.view_adaptivepolicyversion",
    "adaptive.add_adaptivepolicyversion",
    "adaptive.add_adaptiveattemptoption",
    "adaptive.add_confirmedattemptslot",
    "adaptive.add_attemptreservation",
    "adaptive.release_attemptreservation",
    "adaptive.link_attemptreservation",
    "adaptive.view_attemptfulfillmentcheck",
    "adaptive.add_scheduledassessorassignment",
    "adaptive.view_adaptiveescalation",
    "adaptive.change_adaptiveescalation",
}
FACULTY = (
    frozenset(
        {
            "accounts.access_system_workspace",
            "accounts.add_programconfigurationgrant",
            "accounts.change_programconfigurationgrant",
            "academics.change_institution",
            "academics.add_studyprogram",
            "academics.change_studyprogram",
        }
    )
    | permissions("epa", "view add change", "epacommitteemandate")
    | permissions("epa", "view", "epacommitteeparticipation", "epacommitteeballot")
    | permissions("epa", "add", "epacommitteechair", "epaappealpolicy")
    | permissions("epa", "change", "epaappeal")
    | permissions("epa", "add delete", "epacommitteemembership", "epacommitteescope")
    | permissions("learning", "view add change", "progressioncommitteemandate")
    | permissions("learning", "view", "progressionballot")
    | permissions("learning", "add", "progressionappealpolicy")
    | permissions("learning", "change", "progressionappeal")
    | permissions("learning", "add delete", "progressioncommitteemembership")
)
# Only these institution-wide operations accept permissions from a system role.
SYSTEM_ROLE_PERMISSIONS = FACULTY | {"academics.delete_studyprogram"}


@dataclass(frozen=True)
class RoleDefinition:
    scope: AccessRole.Scope
    grants: frozenset[str]
    guide: guide_content.RoleGuide


PROGRAM = AccessRole.Scope.PROGRAM
PROGRAM_LEAD_ROLE = "Penanggung Jawab Akademik Prodi"
FACULTY_ADMIN_ROLE = "Administrator Fakultas"
ACADEMIC_MANAGER_ROLE = "Pengelola Akademik"
CURRICULUM_MANAGER_ROLE = "Pengelola Kurikulum"
ASSESSMENT_MANAGER_ROLE = "Pengelola Asesmen"
PORTFOLIO_MANAGER_ROLE = "Pengelola Portofolio"
STUDENT_ROLE = "Mahasiswa"
SUPERUSER = "Superuser"
# Shared by the enrollment views and onboarding checklist.
ENROLLMENT_READ_PERMISSION = "academics.view_learnerenrollment"
SYNTHESIS_REVIEWER_ROLE = "Peninjau Sintesis"
ROLE_CATALOG = {
    FACULTY_ADMIN_ROLE: RoleDefinition(
        AccessRole.Scope.SYSTEM, FACULTY, guide_content.faculty_admin
    ),
    PROGRAM_LEAD_ROLE: RoleDefinition(
        PROGRAM,
        ACADEMIC
        | ENROLLMENT
        | CURRICULUM
        | EPA_CONFIGURATION
        | PROGRAM_ANALYTICS
        | BLUEPRINT
        | OPERATE_ASSESSMENTS
        | PORTFOLIO
        | ADAPTATION
        | {
            "evidence.add_artifactmappublication",
            "reflection.add_reflectionadvisorassignment",
            "learning.add_interventionapproval",
            "epa.add_epapublication",
            "epa.add_epaassessorassignment",
            "epa.add_epareviewassignment",
            "learning.add_academicadvisorassignment",
            "learning.add_progressionreviewassignment",
            "learning.view_longitudinalsynthesis",
            "adaptive.add_evaluationrulepublication",
        },
        guide_content.program_lead,
    ),
    ACADEMIC_MANAGER_ROLE: RoleDefinition(
        PROGRAM, ACADEMIC | ENROLLMENT, guide_content.academic_manager
    ),
    CURRICULUM_MANAGER_ROLE: RoleDefinition(
        PROGRAM,
        CURRICULUM | EPA_CONFIGURATION | PROGRAM_ANALYTICS,
        guide_content.curriculum_manager,
    ),
    ASSESSMENT_MANAGER_ROLE: RoleDefinition(
        PROGRAM, BLUEPRINT | OPERATE_ASSESSMENTS, guide_content.assessment_manager
    ),
    PORTFOLIO_MANAGER_ROLE: RoleDefinition(PROGRAM, PORTFOLIO, guide_content.portfolio_manager),
    "Verifikator Bukti": RoleDefinition(
        PROGRAM,
        EVIDENCE_READ | {"evidence.add_evidenceverification"},
        guide_content.evidence_verifier,
    ),
    "Asesor": RoleDefinition(
        PROGRAM,
        frozenset({"adaptive.add_assessorfinding", "epa.add_epaobservation"}),
        guide_content.assessor,
    ),
    "Peninjau Progresi": RoleDefinition(
        PROGRAM, frozenset({"learning.add_progressionreview"}), guide_content.progression_reviewer
    ),
    "Peninjau EPA": RoleDefinition(
        PROGRAM, frozenset({"epa.add_entrustmentreview"}), guide_content.epa_reviewer
    ),
    "Pengelola Adaptasi": RoleDefinition(PROGRAM, ADAPTATION, guide_content.adaptation_manager),
    "Dosen": RoleDefinition(PROGRAM, frozenset(), guide_content.lecturer),
    SYNTHESIS_REVIEWER_ROLE: RoleDefinition(
        PROGRAM,
        frozenset({"learning.view_longitudinalsynthesis", "learning.add_longitudinalsynthesis"}),
        guide_content.synthesis_reviewer,
    ),
    "Pembimbing Refleksi": RoleDefinition(
        PROGRAM,
        frozenset(
            {
                "reflection.view_reflectionshare",
                "reflection.add_reflectioncoachingmessage",
                "reflection.add_coachingrecommendation",
                "learning.add_learninggoalreview",
                "learning.add_interventiondraft",
                "learning.add_reassessmentrequirement",
            }
        ),
        guide_content.reflection_advisor,
    ),
    STUDENT_ROLE: RoleDefinition(
        PROGRAM,
        frozenset(
            {
                "reflection.add_reflection",
                "epa.view_entrustmentdecision",
                "epa.add_epaappeal",
                "learning.view_progressiondecision",
                "learning.add_progressionappeal",
                "learning.add_learninggoal",
                "learning.change_learninggoal",
                "learning.add_learninggoalshare",
                "learning.add_interventioncompletionreport",
                "reflection.add_reflectioncoachingmessage",
                "reflection.complete_coachingrecommendation",
            }
        ),
        guide_content.student,
    ),
}


def synchronize_roles(actor: User, *, apply: bool) -> list[tuple[str, int, int, bool]]:
    if not (actor.is_superuser and actor.is_active):
        raise PermissionDenied
    grants = frozenset().union(*(definition.grants for definition in ROLE_CATALOG.values()))
    lookup = {
        f"{permission.content_type.app_label}.{permission.codename}": permission
        for permission in Permission.objects.select_related("content_type")
    }
    if missing := grants - lookup.keys():
        raise ValueError(f"Izin belum tersedia. Jalankan migrasi: {', '.join(sorted(missing))}")

    report = []
    with transaction.atomic():
        roles = {
            role.name: role
            for role in AccessRole.objects.select_for_update().filter(name__in=ROLE_CATALOG)
        }
        for name, definition in ROLE_CATALOG.items():
            role = roles.get(name)
            if role and role.scope != definition.scope and role.assignments.exists():
                raise ValueError(f"Ruang lingkup peran {name} bertentangan dengan penugasan aktif.")
            previous = (
                {
                    f"{app}.{code}"
                    for app, code in role.permissions.values_list(
                        "content_type__app_label", "codename"
                    )
                }
                if role
                else set()
            )
            created = role is None
            added, removed = definition.grants - previous, previous - definition.grants
            report.append((name, len(added), len(removed), created))
            if not apply:
                continue
            if role is None:
                role = AccessRole.objects.create(
                    name=name, scope=definition.scope, updated_by=actor
                )
            elif added or removed or role.scope != definition.scope:
                role.scope = definition.scope
                role.updated_by = actor
                role.save(update_fields=["scope", "updated_by", "updated_at"])
            if added or removed:
                role.permissions.set(lookup[key] for key in definition.grants)
    return report
