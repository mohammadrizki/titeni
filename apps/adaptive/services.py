import json
from collections import Counter

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.accounts.access import configurable_programs, program_role_permissions
from apps.accounts.models import User
from apps.evidence.matching import baseline_requirements, candidates, resolve_placement
from apps.evidence.models import EvidenceRecord, LearnerEvidenceBaseline
from apps.learning.models import ReassessmentRequirement

from .automatic_adjustment import adjust_pending_reservations
from .models import (
    AssessorFinding,
    AssessorFindingRevision,
    EvaluationEvidence,
    EvaluationRulePublication,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
)
from .performance import PerformanceThresholds, StandardFinding, evaluate_performance

ENGINE_VERSION = 6
PUBLISH_PERMISSION = "adaptive.add_evaluationrulepublication"


def preview(baseline: LearnerEvidenceBaseline, rule: EvaluationRuleVersion) -> dict:
    version = baseline.publication.version.blueprint_version
    target = rule.standard.standard.item
    program_id = baseline.enrollment.cohort.period.program_id
    if (
        version.framework_version_id != target.version_id
        or target.version.framework.program_id != program_id
        or version.blueprint.program_id != program_id
        or baseline.publication.artifact_map.program_id != program_id
    ):
        raise ValidationError(
            "Standar dan baseline harus memakai versi kerangka dan prodi yang sama."
        )

    as_of = timezone.localdate()
    reassessment = None
    if not rule.demonstration:
        reassessment = (
            ReassessmentRequirement.objects.filter(
                completion__approval__draft__evaluation__baseline=baseline,
                completion__approval__draft__evaluation__rule__standard__standard__item=target,
            )
            .select_related("completion")
            .order_by("-completion__reported_at", "-pk")
            .first()
        )
    cutoff = timezone.localdate(reassessment.completion.reported_at) if reassessment else None
    requirements = baseline_requirements(baseline)
    target_numbers = {
        req.number
        for req in requirements
        if req.entry.get("competency_id") == target.pk
        or any(item.get("competency_id") == target.pk for item in req.entry.get("targets", []))
    }

    records = (
        EvidenceRecord.objects.eligible_for_reconciliation()
        .filter(
            attempt__participation__enrollment_id=baseline.enrollment_id,
            attempt__participation__event__component__version__blueprint__program_id=program_id,
        )
        .select_related(
            "source_link__capability__source",
            "attempt__participation__event",
            "placement",
            "verification",
        )
        .order_by("pk")
    )
    evidence = []
    excluded_by_age = []
    pending_placements = []
    historical_evidence = []
    for record in records:
        choices = candidates(record, requirements)
        requirement, placement = resolve_placement(record, baseline, choices)
        occurred_on = record.attempt.participation.event.occurred_on
        relevant = (
            requirement.number in target_numbers
            if requirement is not None
            else any(choice.requirement.number in target_numbers for choice in choices)
        )
        if not relevant:
            continue
        if cutoff and occurred_on <= cutoff:
            historical_evidence.append(
                {"record": record.pk, "occurred_on": occurred_on.isoformat()}
            )
            continue
        age = (as_of - occurred_on).days
        if (cutoff and age < 0) or (
            rule.maximum_age_days is not None and not 0 <= age <= rule.maximum_age_days
        ):
            excluded_by_age.append({"record": record.pk, "occurred_on": occurred_on.isoformat()})
            continue
        if requirement is None:
            possible = [
                choice.requirement.number
                for choice in choices
                if choice.requirement.number in target_numbers
            ]
            if possible:
                pending_placements.append({"record": record.pk, "requirements": possible})
        else:
            evidence.append(
                {
                    "record": record.pk,
                    "attempt": record.attempt_id,
                    "reference": record.reference,
                    "revision": record.revision_number,
                    "occurred_on": occurred_on.isoformat(),
                    "source": record.source_link.capability.source_id,
                    "source_label": str(record.source_link.capability.source),
                    "context": record.context.strip().casefold(),
                    "verifier": str(record.verification.created_by_id),
                    "verification": record.verification.pk,
                    "requirement": requirement.number,
                    "placement": placement.pk if placement else None,
                }
            )

    criteria = [
        ("Percobaan unik", len({row["attempt"] for row in evidence}), rule.minimum_attempts),
        (
            "Konteks unik",
            len({row["context"] for row in evidence if row["context"]}),
            rule.minimum_contexts,
        ),
        ("Verifikator unik", len({row["verifier"] for row in evidence}), rule.minimum_verifiers),
    ]
    if rule.minimum_sources is not None:
        criteria.append(
            ("Sumber unik", len({row["source"] for row in evidence}), rule.minimum_sources)
        )
    placed_counts = Counter(row["requirement"] for row in evidence)
    pending_counts = Counter(number for row in pending_placements for number in row["requirements"])
    coverage = [
        {
            "number": req.number,
            "label": req.label,
            "context": req.entry.get("context", ""),
            "minimum": req.minimum,
            "count": placed_counts[req.number],
            "pending": pending_counts[req.number],
        }
        for req in requirements
        if req.number in target_numbers
    ]
    sufficiency = EvidenceEvaluation.Sufficiency.REVIEW
    if target_numbers:
        if all(count >= minimum for _, count, minimum in criteria):
            sufficiency = EvidenceEvaluation.Sufficiency.SUFFICIENT
        elif not pending_placements:
            sufficiency = EvidenceEvaluation.Sufficiency.INSUFFICIENT
    assessor_findings = []
    performance = EvidenceEvaluation.Performance.UNDETERMINED
    performance_reason = "Belum tersedia hasil performa terstruktur terhadap standar ini."
    publication = None
    if not rule.demonstration:
        publication = getattr(rule, "publication", None)
        if publication is None:
            raise ValidationError("Aturan produksi belum diterbitkan.")
        latest = AssessorFindingRevision.objects.filter(finding_id=OuterRef("pk"))
        findings = (
            AssessorFinding.objects.filter(
                assignment__record_id__in=[row["record"] for row in evidence],
                assignment__standard_id=rule.standard_id,
            )
            .select_related("assignment__record", "assignment__assessor")
            .annotate(
                revision_pk=Subquery(latest.values("pk")[:1]),
                revision_number=Subquery(latest.values("number")[:1]),
                revision_outcome=Subquery(latest.values("outcome")[:1]),
                revision_rationale=Subquery(latest.values("rationale")[:1]),
                revision_reason=Subquery(latest.values("reason")[:1]),
            )
            .order_by("pk")
        )
        assessor_findings = [
            {
                "id": finding.pk,
                "revision_id": finding.revision_pk,
                "revision_number": finding.revision_number or 1,
                "revision_reason": finding.revision_reason,
                "attempt": finding.assignment.record.attempt_id,
                "record": finding.assignment.record_id,
                "assessor": str(finding.assignment.assessor_id),
                "assessor_name": str(finding.assignment.assessor),
                "outcome": finding.revision_outcome or finding.outcome,
                "rationale": finding.revision_rationale or finding.rationale,
            }
            for finding in findings
        ]
        result = evaluate_performance(
            sufficiency,
            (
                (
                    finding.assignment.record.attempt_id,
                    StandardFinding(finding.revision_outcome or finding.outcome),
                )
                for finding in findings
            ),
            PerformanceThresholds(publication.minimum_below, publication.minimum_meets),
        )
        performance = result.status
        if result.reason == "conflicting_findings":
            sufficiency = EvidenceEvaluation.Sufficiency.REVIEW
        elif result.reason == "too_few_performance_findings":
            sufficiency = (
                EvidenceEvaluation.Sufficiency.REVIEW
                if pending_placements
                else EvidenceEvaluation.Sufficiency.INSUFFICIENT
            )
        performance_reason = {
            "evidence_not_sufficient": "Bukti belum cukup untuk menafsirkan performa.",
            "conflicting_findings": "Temuan asesor bertentangan dan perlu ditinjau.",
            "below_standard": "Temuan asesor berada di bawah standar.",
            "meets_standard": "Temuan asesor memenuhi standar.",
            "too_few_performance_findings": "Jumlah temuan asesor belum memenuhi ambang.",
        }[result.reason]
    return {
        **(
            {
                "reassessment": reassessment.pk,
                "reassessment_cutoff": cutoff.isoformat(),
                "historical_evidence": historical_evidence,
            }
            if reassessment and cutoff
            else {}
        ),
        "target": str(target),
        "publication": publication.pk if publication else None,
        "minimum_below": publication.minimum_below if publication else None,
        "minimum_meets": publication.minimum_meets if publication else None,
        "assessor_findings": assessor_findings,
        "rule_number": rule.number,
        "as_of": as_of.isoformat(),
        "maximum_age_days": rule.maximum_age_days,
        "excluded_by_age": excluded_by_age,
        "standard": rule.standard.description,
        "demonstration": rule.demonstration,
        "criteria": [
            {"label": label, "count": count, "minimum": minimum}
            for label, count, minimum in criteria
        ],
        "sufficiency": sufficiency,
        "performance": performance,
        "performance_reason": performance_reason,
        "pending_placement": bool(pending_placements),
        "pending_placements": pending_placements,
        "coverage": coverage,
        "target_requirements": sorted(target_numbers),
        "evidence": evidence,
    }


def preview_token(
    baseline: LearnerEvidenceBaseline, rule: EvaluationRuleVersion, actor: User, snapshot: dict
) -> str:
    payload = json.dumps(
        [ENGINE_VERSION, baseline.pk, rule.pk, str(actor.pk), snapshot],
        sort_keys=True,
        separators=(",", ":"),
    )
    return salted_hmac("titeni.adaptive.preview", payload, algorithm="sha256").hexdigest()


class StaleSimulationPreview(Exception):
    pass


@transaction.atomic
def record_evaluation(
    baseline: LearnerEvidenceBaseline,
    rule: EvaluationRuleVersion,
    actor: User,
    token: str,
) -> EvidenceEvaluation:
    LearnerEvidenceBaseline.objects.select_for_update().get(pk=baseline.pk)
    rule = EvaluationRuleVersion.objects.select_for_update().get(pk=rule.pk)
    if EvaluationRuleRetirement.objects.filter(rule=rule).exists():
        raise ValidationError("Pilih aturan evaluasi yang masih aktif.")
    snapshot = preview(baseline, rule)
    if not constant_time_compare(token, preview_token(baseline, rule, actor, snapshot)):
        raise StaleSimulationPreview
    evaluation = persist_evaluation(baseline, rule, actor, snapshot)
    adjust_pending_reservations(baseline, [evaluation])
    return evaluation


def persist_evaluation(
    baseline: LearnerEvidenceBaseline,
    rule: EvaluationRuleVersion,
    actor: User,
    snapshot: dict,
    *,
    trigger: EvidenceEvaluation.Trigger = EvidenceEvaluation.Trigger.MANUAL,
    trigger_record: EvidenceRecord | None = None,
) -> EvidenceEvaluation:
    evaluation = EvidenceEvaluation.objects.create(
        baseline=baseline,
        trigger=trigger,
        trigger_record=trigger_record,
        rule=rule,
        sufficiency=snapshot["sufficiency"],
        performance=snapshot["performance"],
        snapshot=snapshot,
        engine_version=ENGINE_VERSION,
        created_by=actor,
    )
    EvaluationEvidence.objects.bulk_create(
        EvaluationEvidence(evaluation=evaluation, record_id=row["record"])
        for row in snapshot["evidence"]
    )
    return evaluation


def require_production_rule_authority(rule: EvaluationRuleVersion, actor: User) -> None:
    program_id = rule.standard.standard.item.version.framework.program_id
    if (
        PUBLISH_PERMISSION not in program_role_permissions(actor, program_id)
        or not configurable_programs(actor).filter(pk=program_id).exists()
    ):
        raise PermissionDenied


@transaction.atomic
def retire_rule(rule: EvaluationRuleVersion, actor: User, reason: str) -> EvaluationRuleRetirement:
    rule = EvaluationRuleVersion.objects.select_for_update().get(pk=rule.pk)
    reason = reason.strip()
    if not 0 < len(reason) <= 500:
        raise ValidationError("Isi alasan penghentian.")
    if not rule.demonstration:
        require_production_rule_authority(rule, actor)
        if not EvaluationRulePublication.objects.filter(rule=rule).exists():
            raise ValidationError("Pilih aturan produksi yang sudah diterbitkan.")
    retirement, _ = EvaluationRuleRetirement.objects.get_or_create(
        rule=rule, defaults={"created_by": actor, "reason": reason}
    )
    return retirement


@transaction.atomic
def publish_rule(
    rule: EvaluationRuleVersion, actor: User, minimum_below: int, minimum_meets: int
) -> EvaluationRulePublication:
    rule = EvaluationRuleVersion.objects.select_for_update().get(pk=rule.pk)
    require_production_rule_authority(rule, actor)
    if (
        rule.demonstration
        or min(minimum_below, minimum_meets) < 1
        or EvaluationRuleRetirement.objects.filter(rule=rule).exists()
    ):
        raise ValidationError("Pilih draf produksi dan isi ambang performa yang valid.")
    publication, created = EvaluationRulePublication.objects.get_or_create(
        rule=rule,
        defaults={
            "created_by": actor,
            "minimum_below": minimum_below,
            "minimum_meets": minimum_meets,
        },
    )
    if not created and (
        publication.minimum_below != minimum_below or publication.minimum_meets != minimum_meets
    ):
        raise ValidationError("Buat versi baru untuk mengubah ambang aturan terbit.")
    return publication
