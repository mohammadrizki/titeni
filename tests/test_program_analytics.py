from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pytest_django.asserts import assertContains

from apps.academics.models import (
    AcademicPeriod,
    Cohort,
    Curriculum,
    Institution,
    Learner,
    LearnerEnrollment,
    StudyProgram,
)
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.adaptive.models import (
    AdaptiveAttemptOption,
    AdaptivePolicyVersion,
    AttemptReservation,
    ConfirmedAttemptSlot,
    EvaluationRulePublication,
    EvaluationRuleRetirement,
    EvaluationRuleVersion,
    EvidenceEvaluation,
    ProgramAnalyticsReport,
)
from apps.adaptive.program_analytics import build_snapshot, day_start
from apps.assessments.models import (
    AssessmentAttempt,
    AssessmentBlueprint,
    AssessmentEvent,
    AssessmentParticipation,
    AssessmentSamplingRule,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyFramework, PerformanceStandard
from apps.evidence.models import (
    ArtifactMap,
    ArtifactMapPublication,
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceType,
    LearnerEvidenceBaseline,
)


@pytest.mark.django_db
def test_program_analytics_freezes_safe_aggregates_and_denies_other_scopes(client: Client) -> None:
    admin = User.objects.create_superuser(username="admin-analitik")
    kaprodi = User.objects.create_user(username="kaprodi-analitik")
    curriculum_manager = User.objects.create_user(username="kurikulum-analitik")
    outsider = User.objects.create_user(username="nonanggota-analitik")
    synchronize_roles(admin, apply=True)
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program, foreign = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=name,
            education_stage=StudyProgram.Stage.UNDERGRADUATE,
            created_by=admin,
        )
        for code, name in (("a", "Prodi A"), ("b", "Prodi B"))
    ]
    today = timezone.localdate()
    for account, name, target in (
        (kaprodi, "Penanggung Jawab Akademik Prodi", program),
        (curriculum_manager, "Pengelola Kurikulum", program),
        (outsider, "Penanggung Jawab Akademik Prodi", foreign),
    ):
        UserRoleAssignment.objects.create(
            account=account,
            role=AccessRole.objects.get(name=name),
            program=target,
            assigned_by=admin,
        )
    for account, target in ((kaprodi, program), (outsider, foreign)):
        ProgramConfigurationGrant.objects.create(
            account=account, program=target, starts_on=today, granted_by=admin
        )
    starts, ends = today - timedelta(days=15), today - timedelta(days=2)
    period = AcademicPeriod.objects.create(
        program=program,
        code="p",
        name="Periode tertutup",
        starts_on=starts,
        ends_on=ends,
        created_by=admin,
    )
    foreign_period = AcademicPeriod.objects.create(
        program=foreign,
        code="p",
        name="Periode luar",
        starts_on=starts,
        ends_on=ends,
        created_by=admin,
    )
    open_period = AcademicPeriod.objects.create(
        program=program,
        code="new",
        name="Periode berjalan",
        starts_on=ends,
        ends_on=today,
        created_by=admin,
    )
    cohorts = [
        Cohort.objects.create(period=period, code=code, name=code, created_by=admin)
        for code in ("a", "b")
    ]
    framework = CompetencyFramework.objects.create(program=program)
    blueprint = AssessmentBlueprint.objects.create(program=program)
    artifact_map = ArtifactMap.objects.create(program=program)
    frameworks, versions, maps = [], [], []
    for number in (1, 2):
        version = framework.versions.create(number=number, created_by=admin)
        frameworks.append(version)
        blueprint_version = blueprint.versions.create(
            framework_version=version, number=number, created_by=admin
        )
        versions.append(blueprint_version)
        map_version = artifact_map.versions.create(
            blueprint_version=blueprint_version, number=number, snapshot={}, created_by=admin
        )
        maps.append(
            ArtifactMapPublication.objects.create(
                artifact_map=artifact_map,
                version=map_version,
                effective_on=starts + timedelta(days=number - 1),
                requirements=[],
                created_by=admin,
            )
        )
    learners = [
        Learner.objects.create(account=User.objects.create_user(username=f"mahasiswa-rahasia-{i}"))
        for i in range(10)
    ]

    def baselines(cohort, published):
        return [
            LearnerEvidenceBaseline.objects.create(
                enrollment=LearnerEnrollment.objects.create(
                    learner=learner,
                    cohort=cohort,
                    enrolled_on=starts,
                    created_by=admin,
                ),
                publication=published,
                created_by=admin,
            )
            for learner in learners
        ]

    original = baselines(cohorts[0], maps[0])
    repeat = LearnerEvidenceBaseline.objects.create(
        enrollment=LearnerEnrollment.objects.create(
            learner=learners[0],
            cohort=cohorts[1],
            enrolled_on=starts,
            created_by=admin,
        ),
        publication=maps[0],
        created_by=admin,
    )
    second_version = [
        LearnerEvidenceBaseline.objects.create(
            enrollment=LearnerEnrollment.objects.create(
                learner=learner,
                cohort=cohorts[1],
                enrolled_on=starts,
                created_by=admin,
            ),
            publication=maps[1],
            created_by=admin,
        )
        for learner in learners[1:6]
    ]
    timestamp = day_start(starts + timedelta(days=1))
    inside = day_start(ends) + timedelta(hours=23, minutes=59)
    outside = day_start(ends + timedelta(days=1))

    def rules(version, code, name, *, demonstration=False, retired=False):
        item = version.items.create(code=code, name=name, created_by=admin)
        standard = PerformanceStandard.objects.create(item=item, code="s").versions.create(
            number=1, description="Standar", created_by=admin
        )
        rule = EvaluationRuleVersion.objects.create(
            standard=standard,
            number=1,
            minimum_attempts=1,
            minimum_contexts=1,
            minimum_verifiers=1,
            demonstration=demonstration,
            created_by=admin,
        )
        publication = EvaluationRulePublication.objects.create(
            rule=rule, minimum_below=1, minimum_meets=1, created_by=admin
        )
        EvaluationRulePublication.objects.filter(pk=publication.pk).update(created_at=timestamp)
        if retired:
            record = EvaluationRuleRetirement.objects.create(
                rule=rule, reason="Usang", created_by=admin
            )
            EvaluationRuleRetirement.objects.filter(pk=record.pk).update(created_at=inside)
        return rule, publication

    def evaluate(rule, records, sufficiency, performance, when=inside):
        items = EvidenceEvaluation.objects.bulk_create(
            [
                EvidenceEvaluation(
                    baseline=baseline,
                    rule=rule,
                    sufficiency=sufficiency,
                    performance=performance,
                    snapshot={"private": "Catatan rahasia"},
                    engine_version=1,
                    created_by=admin,
                )
                for baseline in records
            ]
        )
        EvidenceEvaluation.objects.filter(pk__in=[item.pk for item in items]).update(
            created_at=when
        )
        return items

    safe, published = rules(frameworks[0], "komunikasi", "Komunikasi")
    earlier = evaluate(safe, original[:5], "sufficient", "closed", timestamp + timedelta(hours=1))
    evaluate(safe, original[:5], "insufficient", "undetermined")
    evaluate(safe, [repeat], "insufficient", "undetermined")
    evaluate(safe, original[5:], "sufficient", "open")
    evaluate(safe, original[:1], "sufficient", "closed", outside)
    hidden, _ = rules(frameworks[0], "kecil", "Kategori kecil rahasia")
    evaluate(hidden, original[:9], "sufficient", "closed")
    evaluate(hidden, original[9:], "sufficient", "open")
    retired, _ = rules(frameworks[0], "usang", "Aturan dihentikan", retired=True)
    evaluate(retired, original, "sufficient", "closed", timestamp + timedelta(hours=1))
    demo, _ = rules(frameworks[0], "sim", "Demonstrasi", demonstration=True)
    evaluate(demo, original, "sufficient", "closed")
    newer, _ = rules(frameworks[1], "komunikasi", "Komunikasi")
    evaluate(newer, second_version, "sufficient", "closed")

    curriculum = Curriculum.objects.create(program=program, code="c", name="Kurikulum")
    stage = curriculum.versions.create(number=1, created_by=admin).stages.create(
        code="s", name="Tahap", created_by=admin
    )
    component = versions[0].items.create(
        code="i",
        name="Asesmen",
        method="Observasi",
        purpose="Evaluasi",
        stage=stage,
        timing="Akhir",
        created_by=admin,
    )
    event = AssessmentEvent.objects.create(
        component=component, name="Tambahan", occurred_on=ends, created_by=admin
    )
    sampling = AssessmentSamplingRule.objects.create(
        item=component, context="Klinik", minimum_observations=1, created_by=admin
    )
    source = EvidenceSource.objects.create(
        program=program,
        code="obs",
        name="Observasi",
        acquisition="Form",
        verification="Telaah",
        created_by=admin,
    )
    evidence_type = EvidenceType.objects.create(
        program=program, code="catatan", name="Catatan", created_by=admin
    )
    capability = EvidenceSourceCapability.objects.create(
        source=source, evidence_type=evidence_type, created_by=admin
    )
    source_link = BlueprintItemEvidenceSource.objects.create(
        item=component, capability=capability, created_by=admin
    )
    policy = AdaptivePolicyVersion.objects.create(
        rule_publication=published,
        number=1,
        maximum_attempts=2,
        review_within_days=7,
        created_by=admin,
    )
    option = AdaptiveAttemptOption.objects.create(
        policy=policy,
        sampling=sampling,
        source_link=source_link,
        priority=1,
        maximum_per_option=1,
        adds_attempt=True,
        created_by=admin,
    )
    slot = ConfirmedAttemptSlot.objects.create(
        option=option, event=event, capacity=10, created_by=admin
    )
    for i, evaluation in enumerate(earlier):
        reservation = AttemptReservation.objects.create(
            baseline=evaluation.baseline,
            evaluation=evaluation,
            slot=slot,
            event=event,
            gap_targets=["a", "b"],
            created_by=admin,
        )
        AttemptReservation.objects.filter(pk=reservation.pk).update(created_at=timestamp)
        participation = AssessmentParticipation.objects.create(
            event=event, enrollment=original[i].enrollment
        )
        attempt = AssessmentAttempt.objects.create(
            participation=participation, number=1, created_by=admin
        )
        AttemptReservation.objects.filter(pk=reservation.pk).update(
            attempt=attempt, linked_by=admin, linked_at=inside
        )
    extra_eval = EvidenceEvaluation.objects.filter(baseline=original[5], rule=safe).first()
    extra = AttemptReservation.objects.create(
        baseline=original[5],
        evaluation=extra_eval,
        slot=slot,
        event=event,
        gap_targets=[],
        created_by=admin,
    )
    AttemptReservation.objects.filter(pk=extra.pk).update(created_at=timestamp)
    assert build_snapshot(period)["burden"] == {}
    AttemptReservation.objects.filter(pk=extra.pk).update(created_at=outside)

    repeat_event = AssessmentEvent.objects.create(
        component=component, name="Percobaan kedua", occurred_on=ends, created_by=admin
    )
    repeat_slot = ConfirmedAttemptSlot.objects.create(
        option=option, event=repeat_event, capacity=10, created_by=admin
    )
    repeat_reservation = AttemptReservation.objects.create(
        baseline=original[0],
        evaluation=earlier[0],
        slot=repeat_slot,
        event=repeat_event,
        gap_targets=[],
        created_by=admin,
    )
    repeat_participation = AssessmentParticipation.objects.create(
        event=repeat_event, enrollment=original[0].enrollment
    )
    repeat_attempt = AssessmentAttempt.objects.create(
        participation=repeat_participation, number=1, created_by=admin
    )
    AttemptReservation.objects.filter(pk=repeat_reservation.pk).update(
        created_at=timestamp, attempt=repeat_attempt, linked_by=admin, linked_at=inside
    )
    assert build_snapshot(period)["burden"] == {}
    AttemptReservation.objects.filter(pk=repeat_reservation.pk).update(created_at=outside)

    route = "academics:program_analytics_period"
    url = reverse(route, args=[program.pk, period.pk])
    client.force_login(curriculum_manager)
    assert client.get(url).status_code == 404
    client.force_login(outsider)
    assert client.post(url).status_code == 404
    client.force_login(kaprodi)
    assert client.post(reverse(route, args=[program.pk, foreign_period.pk])).status_code == 404
    assert client.post(reverse(route, args=[program.pk, open_period.pk])).status_code == 404
    period_list = client.get(reverse("academics:program_analytics", args=[program.pk]))
    assertContains(
        period_list,
        '<a href="' + url + '">Buka laporan<span class="sr-only"> Periode tertutup</span></a>',
        html=True,
    )
    assert client.get(url).status_code == 200
    assert not ProgramAnalyticsReport.objects.exists()
    assert client.post(url).status_code == 302
    report = ProgramAnalyticsReport.objects.get()
    assert report.minimum_group_size == 5
    assert report.snapshot == {
        "competencies": [
            {
                "code": "komunikasi",
                "name": "Komunikasi",
                "version": 1,
                "evaluated": 10,
                "insufficient": 5,
                "performance_known": 5,
                "open": 5,
            },
            {
                "code": "komunikasi",
                "name": "Komunikasi",
                "version": 2,
                "evaluated": 5,
                "insufficient": 0,
                "performance_known": 5,
                "open": 0,
            },
        ],
        "burden": {"learners": 5, "total": 5, "linked": 5, "released": 0, "reserved": 0},
    }
    result_page = client.get(url)
    content = result_page.content.decode()
    assert 'id="main" tabindex="-1"' in content
    for region in ("analytics-gaps-title", "analytics-burden-title"):
        assert f'role="region" aria-labelledby="{region}" tabindex="0"' in content
        assert f'<table class="data-table" aria-labelledby="{region}">' in content
    assert "5 dari 10" in content
    assert "Laporan agregat periode ini berhasil disimpan." in content
    assert 'role="status"' in content
    assert "Laporan agregat periode ini berhasil disimpan." not in client.get(url).content.decode()
    for private in (
        "mahasiswa-rahasia",
        "Kategori kecil rahasia",
        "Catatan rahasia",
        "Aturan dihentikan",
    ):
        assert private not in content
    evaluate(safe, original[:1], "sufficient", "closed", inside)
    assert len(build_snapshot(period)["competencies"]) == 1
    assert client.post(url).status_code == 302
    assert ProgramAnalyticsReport.objects.count() == 1
    assert ProgramAnalyticsReport.objects.get().snapshot == report.snapshot
    ProgramConfigurationGrant.objects.create(
        account=curriculum_manager, program=program, starts_on=today, granted_by=admin
    )
    client.force_login(curriculum_manager)
    assert client.get(url).status_code == 200
