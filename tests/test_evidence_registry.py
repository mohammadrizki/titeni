import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import ProgramConfigurationGrant, User
from apps.competencies.models import CompetencyFramework
from apps.evidence.models import (
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceSourceCompetency,
    EvidenceType,
)


@pytest.mark.django_db
def test_evidence_registry_keeps_sources_types_and_mappings_program_scoped(client: Client) -> None:
    manager = User.objects.create_user(username="registry-manager")
    faculty = Institution.objects.create(name="Fakultas", updated_by=manager)
    program, other = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=manager,
        )
        for code in ("kedokteran", "lain")
    ]
    competencies = []
    for scope in (program, other):
        framework = CompetencyFramework.objects.create(program=scope)
        draft = framework.versions.create(number=1, created_by=manager)
        competencies.append(draft.items.create(code="kom", name="Komunikasi", created_by=manager))
    own_competency, foreign_competency = competencies
    foreign_type = EvidenceType.objects.create(
        program=other, code="umpan", name="Jenis prodi lain", created_by=manager
    )
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, granted_by=manager, starts_on=timezone.localdate()
    )
    url = reverse("academics:evidence:registry", args=[program.pk])
    assert client.get(url).status_code == 302
    manager.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[
                "add_evidencesource",
                "add_evidencetype",
                "add_evidencesourcecapability",
                "add_evidencesourcecompetency",
            ]
        )
    )
    client.force_login(manager)
    assert client.get(reverse("academics:evidence:registry", args=[other.pk])).status_code == 404

    source_data = {
        "action": "source",
        "source-code": "observasi",
        "source-name": "Observasi klinis",
        "source-acquisition": "Pengisian formulir oleh supervisor",
        "source-verification": "Pemeriksaan identitas pengamat",
    }
    assert client.post(url, source_data).status_code == 302
    assert "Kode sumber sudah digunakan" in client.post(url, source_data).content.decode()
    source = EvidenceSource.objects.get()
    assert source.program == program and source.created_by == manager
    type_data = {"action": "type", "type-code": "umpan", "type-name": "Umpan balik"}
    assert client.post(url, type_data).status_code == 302
    evidence_type = EvidenceType.objects.get(program=program)
    capability = {
        "action": "capability",
        "capability-source": source.pk,
        "capability-evidence_type": evidence_type.pk,
    }
    forged = {**capability, "capability-evidence_type": foreign_type.pk}
    assert client.post(url, forged).status_code == 200
    assert not EvidenceSourceCapability.objects.exists()
    assert client.post(url, capability).status_code == 302
    assert "Kapabilitas ini sudah tercatat." in client.post(url, capability).content.decode()
    mapping = {
        "action": "competency",
        "competency-source": source.pk,
        "competency-competency": own_competency.pk,
    }
    forged_mapping = {**mapping, "competency-competency": foreign_competency.pk}
    assert client.post(url, forged_mapping).status_code == 200
    assert not EvidenceSourceCompetency.objects.exists()
    assert client.post(url, mapping).status_code == 302
    assert EvidenceSourceCompetency.objects.get().competency == own_competency
    page = client.get(url).content.decode()
    assert "Observasi klinis" in page and "Jenis prodi lain" not in page
    preview = reverse("academics:row_action", args=[program.pk, "sumber-bukti", source.pk, "lihat"])
    assert preview in page
    assert source.verification in client.get(preview).content.decode()
