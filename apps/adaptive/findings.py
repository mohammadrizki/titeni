from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.competencies.models import PerformanceStandardVersion
from apps.evidence.matching import baseline_requirements, candidates, resolve_placement
from apps.evidence.models import EvidenceRecord, LearnerEvidenceBaseline

from .models import (
    AssessorFinding,
    AssessorFindingAssignment,
    AssessorFindingRevision,
    EvidenceEvaluation,
)
from .recalculation import reevaluate_for_evidence

ASSESSOR_PERMISSION = "adaptive.add_assessorfinding"
ASSIGN_PERMISSION = "adaptive.add_assessorfindingassignment"


def assignment_target(
    baseline: LearnerEvidenceBaseline, record: EvidenceRecord, standard: PerformanceStandardVersion
) -> bool:
    requirements = baseline_requirements(baseline)
    requirement, _ = resolve_placement(record, baseline, candidates(record, requirements))
    if requirement is None:
        return False
    item = standard.standard.item
    return (
        item.version_id == baseline.publication.version.blueprint_version.framework_version_id
        and (
            requirement.entry.get("competency_id") == item.pk
            or any(
                target.get("competency_id") == item.pk
                for target in requirement.entry.get("targets", [])
            )
        )
    )


@transaction.atomic
def assign_finding(
    baseline: LearnerEvidenceBaseline,
    record: EvidenceRecord,
    standard: PerformanceStandardVersion,
    assessor: User,
    actor: User,
) -> None:
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        ASSIGN_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied
    record = EvidenceRecord.objects.select_for_update().get(pk=record.pk)
    eligible = EvidenceRecord.objects.eligible_for_reconciliation().filter(
        pk=record.pk,
        attempt__participation__enrollment_id=baseline.enrollment_id,
        attempt__participation__event__component__version__blueprint__program_id=program_id,
    )
    if not (
        configurable_programs(assessor).filter(pk=program_id).exists()
        and ASSESSOR_PERMISSION in program_role_permissions(assessor, program_id)
        and eligible.exists()
        and assignment_target(record=record, baseline=baseline, standard=standard)
    ):
        raise ValidationError("Pilih bukti yang sesuai dengan standar dan asesor berizin prodi.")
    AssessorFindingAssignment.objects.get_or_create(
        record=record, standard=standard, assessor=assessor, defaults={"created_by": actor}
    )


def require_eligible_assignment(assignment: AssessorFindingAssignment, actor: User) -> None:
    record = EvidenceRecord.objects.select_for_update().get(pk=assignment.record_id)
    program_id = record.attempt.participation.enrollment.cohort.period.program_id
    if (
        assignment.assessor_id != actor.pk
        or ASSESSOR_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied
    if not EvidenceRecord.objects.eligible_for_reconciliation().filter(pk=record.pk).exists():
        raise ValidationError("Penugasan ini sudah tidak dapat diisi.")


@transaction.atomic
def submit_finding(
    assignment: AssessorFindingAssignment, actor: User, outcome: str, rationale: str
) -> None:
    require_eligible_assignment(assignment, actor)
    finding = AssessorFinding(assignment=assignment, outcome=outcome, rationale=rationale)
    finding.full_clean()
    finding.save()
    reevaluate_for_evidence(assignment.record, actor, EvidenceEvaluation.Trigger.FINDING)


@transaction.atomic
def revise_finding(
    finding: AssessorFinding,
    actor: User,
    outcome: str,
    rationale: str,
    reason: str,
    previous_number: int,
) -> None:
    require_eligible_assignment(finding.assignment, actor)
    latest = finding.revisions.first()
    number = latest.number if latest else 1
    if previous_number != number:
        raise ValidationError("Temuan sudah dikoreksi. Tinjau versi terbaru sebelum menyimpan.")
    revision = AssessorFindingRevision(
        finding=finding,
        number=number + 1,
        outcome=outcome,
        rationale=rationale.strip(),
        reason=reason.strip(),
    )
    revision.full_clean()
    revision.save()
    reevaluate_for_evidence(
        finding.assignment.record, actor, EvidenceEvaluation.Trigger.FINDING_CORRECTION
    )
