import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Curriculum, Institution, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.competencies.models import (
    CompetencyFrameworkVersion,
    CompetencyIndicator,
    CompetencyItem,
    CompetencyMilestone,
    CompetencyRelationship,
    PerformanceStandard,
)


@pytest.mark.django_db
def test_competency_drafts_scope_hierarchy_and_milestones(client: Client) -> None:
    manager = User.objects.create_user(username="manager")
    faculty = Institution.objects.create(name="Fakultas Kedokteran", updated_by=manager)
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
    stages = []
    for scope in (program, other):
        curriculum = Curriculum.objects.create(program=scope, code="2026", name="Kurikulum 2026")
        version = curriculum.versions.create(number=1, created_by=manager)
        stages.append(version.stages.create(code="a", name="Tahap A", created_by=manager))
    stage, other_stage = stages
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, starts_on=timezone.localdate(), granted_by=manager
    )
    index = reverse("academics:competencies:framework", args=[program.pk])
    assert client.get(index).status_code == 302
    manager.user_permissions.add(
        *Permission.objects.filter(
            codename__in=[
                "add_competencyframeworkversion",
                "add_competencyitem",
                "add_competencyindicator",
                "add_competencymilestone",
                "add_competencyrelationship",
                "add_performancestandardversion",
            ]
        )
    )
    client.force_login(manager)
    listing = client.get(reverse("academics:programs")).content.decode()
    tab_urls = [
        reverse("academics:periods", args=[program.pk]),
        reverse("academics:cohorts", args=[program.pk]),
        reverse("academics:curricula", args=[program.pk]),
        index,
    ]
    for tab_url in tab_urls:
        assert f'href="{tab_url}"' in listing
        response = client.get(tab_url)
        assert response.status_code == 200
        assert f'href="{tab_url}" aria-current="page"' in response.content.decode()
    denied = reverse("academics:competencies:framework", args=[other.pk])
    assert client.get(denied).status_code == 404
    assert client.post(denied).status_code == 404
    first_url = client.post(index).headers["Location"]
    second_url = client.post(index).headers["Location"]
    first, second = CompetencyFrameworkVersion.objects.order_by("number")
    assert (first.number, second.number) == (1, 2)
    assert first.created_by == manager
    assert first.framework_id == second.framework_id

    root_data = {"action": "item", "code": "root", "name": "Domain klinis"}
    assert client.post(first_url, root_data).status_code == 302
    root = first.items.get()
    child = {"action": "item", "code": "child", "name": "Komunikasi", "parent": root.pk}
    assert client.post(second_url, child).status_code == 200
    assert not second.items.exists()
    assert client.post(first_url, child).status_code == 302
    assert client.post(first_url, child).status_code == 200
    item = first.items.get(code="child")
    assert item.parent == root and item.created_by == manager
    root.parent = item
    with pytest.raises(ValidationError, match="bebas siklus"):
        root.full_clean()

    indicator = {
        "action": "indicator",
        "indicator-item": item.pk,
        "indicator-code": "pilihan",
        "indicator-description": "Merangkum pilihan dengan bahasa yang mudah dipahami",
    }
    assert client.post(second_url, indicator).status_code == 200
    assert not CompetencyIndicator.objects.exists()
    assert client.post(first_url, indicator).status_code == 302
    duplicate = client.post(first_url, indicator)
    assert duplicate.status_code == 200
    assert "Kode indikator sudah digunakan pada butir ini." in duplicate.content.decode()
    saved_indicator = CompetencyIndicator.objects.get()
    assert saved_indicator.item == item and saved_indicator.created_by == manager
    assert saved_indicator.description in client.get(first_url).content.decode()
    assert saved_indicator.description not in client.get(second_url).content.decode()

    milestone = {"action": "milestone", "item": item.pk, "expectation": "Menjelaskan pilihan"}
    assert client.post(first_url, {**milestone, "stage": other_stage.pk}).status_code == 200
    assert client.post(second_url, {**milestone, "stage": stage.pk}).status_code == 200
    assert not CompetencyMilestone.objects.exists()
    assert client.post(first_url, {**milestone, "stage": stage.pk}).status_code == 302
    saved = CompetencyMilestone.objects.get()
    assert saved.item == item and saved.stage == stage and saved.created_by == manager
    draft_page = client.get(first_url).content.decode()
    assert saved.expectation in draft_page
    assert f'href="{index}" aria-current="location"' in draft_page
    assert saved.expectation not in client.get(second_url).content.decode()
    assert CompetencyItem.objects.count() == 2

    assert client.post(second_url, {**root_data, "code": "other"}).status_code == 302
    other_item = second.items.get()
    relation = {
        "action": "relationship",
        "relationship-source": root.pk,
        "relationship-target": item.pk,
        "relationship-description": "Latihan komunikasi mendukung penerapan klinis",
    }
    invalid = client.post(first_url, {**relation, "relationship-target": root.pk})
    assert "Butir asal dan tujuan harus berbeda." in invalid.content.decode()
    assert (
        client.post(first_url, {**relation, "relationship-target": other_item.pk}).status_code
        == 200
    )
    assert not CompetencyRelationship.objects.exists()
    assert client.post(first_url, relation).status_code == 302
    assert "Relasi ini sudah tercatat." in client.post(first_url, relation).content.decode()
    saved_relation = CompetencyRelationship.objects.get()
    assert saved_relation.created_by == manager
    assert saved_relation.source == root and saved_relation.target == item

    standard = {
        "action": "standard",
        "standard-item": item.pk,
        "standard-code": "komunikasi",
        "standard-description": "Menjelaskan pilihan",
    }
    assert client.post(second_url, standard).status_code == 200
    assert not PerformanceStandard.objects.exists()
    assert client.post(first_url, standard).status_code == 302
    second_description = "Menjelaskan pilihan dan memeriksa pemahaman"
    assert (
        client.post(first_url, {**standard, "standard-description": second_description}).status_code
        == 302
    )
    saved_standard = PerformanceStandard.objects.get()
    assert saved_standard.item == item
    assert list(saved_standard.versions.values_list("number", "description")) == [
        (2, second_description),
        (1, standard["standard-description"]),
    ]
    assert saved_standard.versions.filter(created_by=manager).count() == 2
    assert second_description in client.get(first_url).content.decode()
    assert second_description not in client.get(second_url).content.decode()

    edit = reverse("academics:row_action", args=[program.pk, "butir", item.pk, "sunting"])
    delete = reverse("academics:row_action", args=[program.pk, "butir", item.pk, "hapus"])
    assert client.get(edit).status_code == 403
    role = AccessRole.objects.create(
        name="Penanggung Jawab Akademik Prodi", scope=AccessRole.Scope.PROGRAM, updated_by=manager
    )
    role.permissions.add(
        *Permission.objects.filter(
            content_type__app_label="competencies",
            codename__in=["change_competencyitem", "delete_competencyitem"],
        )
    )
    UserRoleAssignment.objects.create(
        account=manager, role=role, program=program, assigned_by=manager
    )
    page = client.get(first_url).content.decode()
    assert edit in page and delete in page
    data = {"code": item.code, "name": "Komunikasi revisi", "parent": root.pk}
    assert client.post(edit, data).headers["Location"] == first_url
    item.refresh_from_db()
    assert item.name == data["name"]
    assert client.post(delete).status_code == 409
