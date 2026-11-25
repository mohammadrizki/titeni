import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Curriculum, Institution, StudyProgram
from apps.accounts.models import ProgramConfigurationGrant, User
from apps.assessments.models import (
    AssessmentBlueprintVersion,
    AssessmentSamplingRule,
    BlueprintItemCompetency,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyFramework, CompetencyMilestone
from apps.evidence.models import (
    ArtifactMapVersion,
    EvidenceRequirementTemplate,
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceSourceCompetency,
    EvidenceType,
)


@pytest.mark.django_db
def test_blueprint_preserves_versioned_mapping_and_program_scope(client: Client) -> None:
    manager = User.objects.create_user(username="manager")
    institution = Institution.objects.create(name="Fakultas Kedokteran", updated_by=manager)
    programs = []
    stages = []
    items = []
    for code in ("kedokteran", "lain"):
        program = StudyProgram.objects.create(
            institution=institution,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=manager,
        )
        curriculum = Curriculum.objects.create(program=program, code="2026", name="Kurikulum")
        version = curriculum.versions.create(number=1, created_by=manager)
        stages.append(version.stages.create(code="a", name="Tahap A", created_by=manager))
        framework = CompetencyFramework.objects.create(program=program)
        draft = framework.versions.create(number=1, created_by=manager)
        items.append(draft.items.create(code="komunikasi", name="Komunikasi", created_by=manager))
        programs.append(program)
    program, other = programs
    stage, other_stage = stages
    competency, other_competency = items
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, starts_on=timezone.localdate(), granted_by=manager
    )
    index = reverse("academics:assessments:blueprints", args=[program.pk])
    assert client.get(index).status_code == 302
    client.force_login(manager)
    denied = reverse("academics:assessments:blueprints", args=[other.pk])
    assert (
        client.post(denied, {"framework_version": other_competency.version_id}).status_code == 404
    )
    assert client.post(index, {"framework_version": other_competency.version_id}).status_code == 200
    assert not AssessmentBlueprintVersion.objects.exists()
    data = {"framework_version": competency.version_id}
    first_url = client.post(index, data).headers["Location"]
    second_url = client.post(index, data).headers["Location"]
    first, second = AssessmentBlueprintVersion.objects.order_by("number")
    assert (first.number, second.number) == (1, 2)
    assert first.framework_version_id == competency.version_id
    assert first.blueprint_id == second.blueprint_id and first.created_by == manager
    component = {
        "action": "item",
        "code": "osce-1",
        "name": "Komunikasi klinis",
        "method": "OSCE",
        "purpose": "Mengamati komunikasi",
        "stage": stage.pk,
        "timing": "Akhir tahap",
    }
    assert client.post(first_url, {**component, "stage": other_stage.pk}).status_code == 200
    assert not first.items.exists()
    assert client.post(first_url, component).status_code == 302
    duplicate = client.post(first_url, component)
    assert "Kode komponen sudah digunakan" in duplicate.content.decode()
    item = first.items.get()
    mapping = {"action": "mapping", "item": item.pk, "competency": competency.pk}
    assert client.post(second_url, mapping).status_code == 200
    assert client.post(first_url, {**mapping, "competency": other_competency.pk}).status_code == 200
    assert not BlueprintItemCompetency.objects.exists()
    assert client.post(first_url, mapping).status_code == 302
    assert "Pemetaan ini sudah tercatat." in client.post(first_url, mapping).content.decode()
    saved = BlueprintItemCompetency.objects.get()
    assert saved.item == item and saved.competency == competency and saved.created_by == manager
    assert item.name in client.get(first_url).content.decode()
    assert item.name not in client.get(second_url).content.decode()

    indicator = competency.indicators.create(
        code="jelas", description="Menjelaskan pilihan klinis", created_by=manager
    )
    peer = competency.version.items.create(code="lain", name="Butir lain", created_by=manager)
    peer_indicator = peer.indicators.create(code="lain", description="Lain", created_by=manager)
    foreign_indicator = other_competency.indicators.create(
        code="jelas", description="Indikator prodi lain", created_by=manager
    )
    mismatch = client.post(first_url, {**mapping, "indicator": peer_indicator.pk})
    assert "Indikator harus berasal dari butir yang dipilih." in mismatch.content.decode()
    assert client.post(first_url, {**mapping, "indicator": foreign_indicator.pk}).status_code == 200
    assert BlueprintItemCompetency.objects.count() == 1
    targeted = {**mapping, "indicator": indicator.pk}
    assert client.post(first_url, targeted).status_code == 302
    duplicate = client.post(first_url, targeted)
    assert "Pemetaan indikator ini sudah tercatat." in duplicate.content.decode()
    assert BlueprintItemCompetency.objects.filter(indicator__isnull=True).count() == 1
    assert BlueprintItemCompetency.objects.get(indicator=indicator).created_by == manager
    assert indicator.description in client.get(first_url).content.decode()

    sampling = {
        "action": "sampling",
        "sampling-item": item.pk,
        "sampling-context": "Konsultasi rawat jalan",
        "sampling-minimum_observations": 3,
    }
    assert client.post(second_url, sampling).status_code == 200
    invalid = client.post(first_url, {**sampling, "sampling-minimum_observations": 0})
    assert "Jumlah minimum observasi harus lebih dari nol." in invalid.content.decode()
    assert not AssessmentSamplingRule.objects.exists()
    assert client.post(first_url, sampling).status_code == 302
    duplicate = client.post(first_url, sampling)
    assert "Rancangan sampling untuk konteks ini sudah tercatat." in duplicate.content.decode()
    rule = AssessmentSamplingRule.objects.get()
    assert rule.item == item and rule.created_by == manager and rule.minimum_observations == 3
    assert rule.context in client.get(first_url).content.decode()
    assert rule.context not in client.get(second_url).content.decode()

    capabilities = []
    for scope in (program, other):
        source = EvidenceSource.objects.create(
            program=scope,
            code="observasi",
            name="Observasi",
            acquisition="Formulir",
            verification="Verifikasi supervisor",
            created_by=manager,
        )
        evidence_type = EvidenceType.objects.create(
            program=scope,
            code="catatan",
            name="Catatan observasi",
            created_by=manager,
        )
        capabilities.append(
            EvidenceSourceCapability.objects.create(
                source=source,
                evidence_type=evidence_type,
                created_by=manager,
            )
        )
    own, foreign = capabilities
    evidence = {"action": "source", "source-item": item.pk, "source-capability": own.pk}
    assert client.post(second_url, evidence).status_code == 200
    assert client.post(first_url, {**evidence, "source-capability": foreign.pk}).status_code == 200
    assert not BlueprintItemEvidenceSource.objects.exists()
    assert client.post(first_url, evidence).status_code == 302
    duplicate = client.post(first_url, evidence)
    assert "Sumber dan jenis bukti ini sudah tercatat" in duplicate.content.decode()
    link = BlueprintItemEvidenceSource.objects.get()
    assert link.item == item and link.capability == own and link.created_by == manager
    assert "Catatan observasi" in client.get(first_url).content.decode()
    manager.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="evidence",
            codename__in=["change_evidencesourcecapability", "delete_evidencesourcecapability"],
        )
    )
    capability_args = [program.pk, "kapabilitas-sumber", own.pk]
    edit = reverse("academics:row_action", args=[*capability_args, "sunting"])
    delete = reverse("academics:row_action", args=[*capability_args, "hapus"])
    assert client.post(edit, {"evidence_type": foreign.evidence_type_id}).status_code == 409
    assert client.post(delete).status_code == 409
    assert BlueprintItemEvidenceSource.objects.filter(pk=link.pk).exists()

    registry_source = EvidenceSource.objects.create(
        program=program,
        code="refleksi",
        name="Catatan refleksi",
        acquisition="Formulir",
        verification="Pembimbing",
        created_by=manager,
    )
    EvidenceSourceCompetency.objects.create(
        source=registry_source, competency=competency, created_by=manager
    )
    CompetencyMilestone.objects.create(
        item=competency, stage=stage, expectation="Menjelaskan langkah klinis", created_by=manager
    )
    map_url = reverse("academics:evidence:artifact_map", args=[program.pk, first.pk])
    assert map_url in client.get(first_url).content.decode()
    maps_url = reverse("academics:evidence:artifact_maps", args=[program.pk])
    assert maps_url in client.get(reverse("academics:programs")).content.decode()
    map_listing = client.get(maps_url).content.decode()
    assert f'href="{maps_url}" aria-current="page"' in map_listing
    assert map_url in map_listing
    denied_maps = reverse("academics:evidence:artifact_maps", args=[other.pk])
    assert client.get(denied_maps).status_code == 404
    response = client.get(map_url)
    assert response.status_code == 200
    page = response.content.decode()
    for expected in (
        item.name,
        indicator.description,
        rule.context,
        "Catatan observasi",
        registry_source.name,
        "Menjelaskan langkah klinis",
        "Belum dipetakan",
    ):
        assert expected in page
    empty_url = reverse("academics:evidence:artifact_map", args=[program.pk, second.pk])
    assert item.name not in client.get(empty_url).content.decode()
    forged_url = reverse("academics:evidence:artifact_map", args=[other.pk, first.pk])
    assert client.get(forged_url).status_code == 404
    assert client.post(map_url).status_code == 405

    requirements_url = reverse(
        "academics:evidence:evidence_requirements", args=[program.pk, first.pk]
    )
    assert requirements_url in page
    requirement = {
        "code": "catatan-klinis",
        "name": "Catatan tambahan",
        "competency": competency.pk,
        "capability": own.pk,
        "minimum_count": 2,
        "context": "Rawat jalan",
    }
    assert (
        client.post(
            requirements_url, {**requirement, "competency": other_competency.pk}
        ).status_code
        == 200
    )
    assert (
        client.post(requirements_url, {**requirement, "capability": foreign.pk}).status_code == 200
    )
    assert client.post(requirements_url, {**requirement, "minimum_count": 0}).status_code == 200
    assert not EvidenceRequirementTemplate.objects.exists()
    assert client.post(requirements_url, requirement).status_code == 302
    assert (
        "Kode persyaratan sudah digunakan"
        in client.post(requirements_url, requirement).content.decode()
    )
    saved_requirement = EvidenceRequirementTemplate.objects.get()
    assert saved_requirement.blueprint_version == first and saved_requirement.created_by == manager
    assert saved_requirement.name in client.get(map_url).content.decode()
    assert saved_requirement.name not in client.get(empty_url).content.decode()

    second_type = EvidenceType.objects.create(
        program=program,
        code="formulir",
        name="Formulir observasi",
        created_by=manager,
    )
    second_capability = EvidenceSourceCapability.objects.create(
        source=own.source, evidence_type=second_type, created_by=manager
    )
    assert (
        client.post(first_url, {**evidence, "source-capability": second_capability.pk}).status_code
        == 302
    )
    assert (
        client.post(
            first_url,
            {
                **sampling,
                "sampling-context": "Rawat inap",
                "sampling-minimum_observations": 2,
            },
        ).status_code
        == 302
    )
    assert (
        client.post(
            first_url, {**component, "code": "belum-lengkap", "name": "Komponen belum lengkap"}
        ).status_code
        == 302
    )
    preview = client.get(map_url)
    assert "Usulan persyaratan dari blueprint" in preview.content.decode()
    proposals = preview.context["snapshot"]["blueprint_proposals"]
    assert len(proposals) == 2
    assert {row["component_id"] for row in proposals} == {item.pk}
    assert {row["context"]: row["minimum_observations"] for row in proposals} == {
        rule.context: 3,
        "Rawat inap": 2,
    }
    for proposal in proposals:
        assert {source["capability_id"] for source in proposal["sources"]} == {
            own.pk,
            second_capability.pk,
        }
        assert {target["indicator_id"] for target in proposal["targets"]} == {None, indicator.pk}
    empty_map = client.get(empty_url)
    assert not empty_map.context["snapshot"]["blueprint_proposals"]

    save_map_url = reverse("academics:evidence:save_artifact_map", args=[program.pk, first.pk])
    assert client.get(save_map_url).status_code == 405
    saved_url = client.post(save_map_url).headers["Location"]
    saved_map = ArtifactMapVersion.objects.get()
    assert (
        saved_map.number == 1
        and saved_map.blueprint_version == first
        and saved_map.created_by == manager
    )
    assert saved_url in client.get(map_url).content.decode()
    assert saved_url in client.get(maps_url).content.decode()
    item.name = "Komponen yang telah dikoreksi"
    item.save(update_fields=["name"])
    assert item.name in client.get(map_url).content.decode()
    saved_requirement.name = "Catatan setelah koreksi"
    saved_requirement.save(update_fields=["name"])
    history_page = client.get(saved_url).content.decode()
    assert "Catatan tambahan" in history_page and saved_requirement.name not in history_page
    assert "Komunikasi klinis" in history_page and item.name not in history_page
    assert client.post(saved_url).status_code == 405
    next_url = client.post(save_map_url).headers["Location"]
    assert next_url != saved_url and item.name in client.get(next_url).content.decode()
    assert list(ArtifactMapVersion.objects.values_list("number", flat=True)) == [2, 1]
    forged_saved = reverse("academics:evidence:saved_artifact_map", args=[other.pk, saved_map.pk])
    assert client.get(forged_saved).status_code == 404

    assert "Usulan persyaratan dari blueprint" in history_page
    assert "Rawat inap" in history_page
    assert saved_map.snapshot["blueprint_proposals"] == proposals
    legacy_snapshot = saved_map.snapshot.copy()
    del legacy_snapshot["blueprint_proposals"]
    legacy = saved_map.artifact_map.versions.create(
        number=3, blueprint_version=first, snapshot=legacy_snapshot, created_by=manager
    )
    legacy_url = reverse("academics:evidence:saved_artifact_map", args=[program.pk, legacy.pk])
    legacy_page = client.get(legacy_url)
    assert legacy_page.status_code == 200
    assert "Usulan persyaratan dari blueprint" not in legacy_page.content.decode()
