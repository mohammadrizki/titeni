import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import synchronize_roles
from apps.competencies.models import CompetencyFramework
from apps.epa.models import EntrustableProfessionalActivity, SupervisionScale


@pytest.mark.django_db
def test_epa_drafts_have_versioned_scales_and_program_scoped_competencies(client: Client):
    admin = User.objects.create_superuser(username="admin-epa")
    actor = User.objects.create_user(username="pengelola-epa")
    reader = User.objects.create_user(username="pembaca-epa")
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    program, foreign = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=stage,
            created_by=admin,
        )
        for code, stage in (
            ("vis", StudyProgram.Stage.PROFESSIONAL),
            ("s1", StudyProgram.Stage.UNDERGRADUATE),
        )
    ]
    synchronize_roles(admin, apply=True)
    curriculum_role = AccessRole.objects.get(name="Pengelola Kurikulum")
    read_role = AccessRole.objects.create(
        name="Pembaca konfigurasi EPA", scope=AccessRole.Scope.PROGRAM, updated_by=admin
    )
    read_role.permissions.set(
        Permission.objects.filter(content_type__app_label="epa", codename__startswith="view_")
    )
    for account, role in ((actor, curriculum_role), (reader, read_role)):
        ProgramConfigurationGrant.objects.create(
            account=account, program=program, starts_on=timezone.localdate(), granted_by=admin
        )
        UserRoleAssignment.objects.create(
            account=account, role=role, program=program, assigned_by=admin
        )
    framework = CompetencyFramework.objects.create(program=program)
    selected_framework = framework.versions.create(number=1, created_by=admin)
    old_framework = framework.versions.create(number=2, created_by=admin)
    selected = selected_framework.items.create(code="inti", name="Komunikasi", created_by=admin)
    another_version = old_framework.items.create(code="lama", name="Versi lain", created_by=admin)
    foreign_framework = CompetencyFramework.objects.create(program=foreign).versions.create(
        number=1, created_by=admin
    )
    foreign_scale = SupervisionScale.objects.create(program=foreign, code="lain", created_by=admin)
    foreign_scale_version = foreign_scale.versions.create(number=1, name="Lain", created_by=admin)
    index = reverse("academics:epa:index", args=[program.pk])
    foreign_index = reverse("academics:epa:index", args=[foreign.pk])

    client.force_login(reader)
    assert "Belum ada EPA" in client.get(index).content.decode()
    assert client.post(index, {"action": "activity", "activity-code": "visite"}).status_code == 403
    client.force_login(actor)
    assert client.get(foreign_index).status_code == 404
    scale_create = {"action": "scale", "scale-code": "klinis"}
    scale_url = client.post(index, scale_create).headers["Location"]
    assert client.post(index, scale_create).status_code == 400
    scale = SupervisionScale.objects.get(program=program, code="klinis")
    first_scale_url = client.post(scale_url, {"name": "Skala klinis"}).headers["Location"]
    first_scale = scale.versions.get(number=1)
    level = {"position": 1, "label": "Observasi", "description": "Amati pembimbing"}
    assert client.post(first_scale_url, level).status_code == 302
    assert client.post(first_scale_url, level).status_code == 400
    assert client.post(first_scale_url, {**level, "position": 0}).status_code == 400
    second_scale_url = client.post(scale_url, {"name": "Skala klinis revisi"}).headers["Location"]
    assert "Belum ada tingkat supervisi" in client.get(second_scale_url).content.decode()

    activity_url = client.post(index, {"action": "activity", "activity-code": "visite"}).headers[
        "Location"
    ]
    activity = EntrustableProfessionalActivity.objects.get(program=program)
    data = {
        "title": "Memimpin visite",
        "description": "Merangkum temuan dan menyusun rencana tindak lanjut.",
        "framework": selected_framework.pk,
        "scale": first_scale.pk,
    }
    assert client.post(activity_url, {**data, "framework": foreign_framework.pk}).status_code == 400
    assert client.post(activity_url, {**data, "scale": foreign_scale_version.pk}).status_code == 400
    version_url = client.post(activity_url, data).headers["Location"]
    version = activity.versions.get(number=1)
    assert version.scale == first_scale
    assert version.framework == selected_framework
    mapping = {"item": selected.pk, "kind": "core"}
    assert client.post(version_url, {**mapping, "item": another_version.pk}).status_code == 400
    assert client.post(version_url, mapping).status_code == 302
    assert client.post(version_url, mapping).status_code == 400
    assert version.competencies.get().item == selected
    assert client.post(activity_url, data).status_code == 302
    assert not activity.versions.get(number=2).competencies.exists()
    assert first_scale.levels.count() == 1
    client.force_login(reader)
    assert "Komunikasi" in client.get(version_url).content.decode()
    assert client.post(version_url, mapping).status_code == 403
    assert not EntrustableProfessionalActivity.objects.filter(program=foreign).exists()
