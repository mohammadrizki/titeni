import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Curriculum, Institution, StudyProgram
from apps.accounts.models import ProgramConfigurationGrant, User
from apps.assessments.models import AssessmentBlueprintVersion, BlueprintItemCompetency
from apps.competencies.models import CompetencyFramework


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
