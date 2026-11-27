from datetime import date

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import AcademicPeriod, Cohort, Institution, Learner, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.reflection.models import (
    CoachingRecommendation,
    ReflectionAdvisorAssignment,
    ReflectionPrompt,
    ReflectionRevision,
    ReflectionShare,
)


@pytest.mark.django_db
def test_private_reflection_has_owner_only_access_and_revisions(client):
    owner = User.objects.create_user(username="owner")
    outsider = User.objects.create_superuser(username="outsider")
    faculty = Institution.objects.create(name="Fakultas", updated_by=outsider)
    program = StudyProgram.objects.create(
        institution=faculty,
        education_stage=StudyProgram.Stage.PROFESSIONAL,
        name="Profesi",
        code="prof",
        created_by=outsider,
    )
    period = AcademicPeriod.objects.create(
        program=program,
        name="Periode",
        code="p1",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
        created_by=outsider,
    )
    cohort = Cohort.objects.create(period=period, name="Cohort", code="c1", created_by=outsider)
    enrollment = cohort.enrollments.create(
        learner=Learner.objects.create(account=owner),
        enrolled_on=date(2026, 1, 1),
        created_by=outsider,
    )
    role = AccessRole.objects.create(
        name="Mahasiswa", scope=AccessRole.Scope.PROGRAM, updated_by=outsider
    )
    role.permissions.add(
        Permission.objects.get(content_type__app_label="reflection", codename="add_reflection")
    )
    UserRoleAssignment.objects.create(
        account=owner, role=role, program=program, assigned_by=outsider
    )
    client.force_login(owner)
    drafts = reverse("reflection_drafts", args=[enrollment.pk])
    assert drafts in client.get(reverse("reflection_index")).content.decode()
    created = client.post(drafts, {"revision": 0, "body": "Teks pribadi"})
    assert created.status_code == 302
    url = created["Location"]
    assert client.post(url, {"revision": 1, "body": "Teks revisi"}).status_code == 302
    assert client.post(url, {"revision": 1, "body": "Kirim ulang lama"}).status_code == 409
    assert list(ReflectionRevision.objects.values_list("body", flat=True)) == [
        "Teks revisi",
        "Teks pribadi",
    ]
    assert "no-store" in client.get(url)["Cache-Control"]
    client.force_login(outsider)
    assert client.get(url).status_code == 404
    assert client.post(url, {"revision": 2, "body": "Akses silang"}).status_code == 404

    manager = User.objects.create_user(username="manager")
    ProgramConfigurationGrant.objects.create(
        account=manager, program=program, starts_on=timezone.localdate(), granted_by=outsider
    )
    curriculum_role = AccessRole.objects.create(
        name="Pengelola Kurikulum", scope=AccessRole.Scope.PROGRAM, updated_by=outsider
    )
    UserRoleAssignment.objects.create(
        account=manager, role=curriculum_role, program=program, assigned_by=outsider
    )
    config_url = reverse("academics:reflection_prompts", args=[program.pk])
    client.force_login(manager)
    assert client.get(config_url).status_code == 403
    curriculum_role.permissions.add(Permission.objects.get(codename="view_reflectionprompt"))
    prompt_data = {"text": "Pengalaman apa yang penting?", "position": 20, "is_active": "on"}
    assert client.post(config_url, prompt_data).status_code == 403
    curriculum_role.permissions.add(Permission.objects.get(codename="add_reflectionprompt"))
    assert client.post(config_url, prompt_data).status_code == 302
    assert client.post(config_url, prompt_data).status_code == 200
    assert (
        client.post(
            config_url,
            {
                **prompt_data,
                "position": 10,
                "text": "Bukti apa yang Anda miliki?",
            },
        ).status_code
        == 302
    )
    prompt = ReflectionPrompt.objects.get(text=prompt_data["text"])
    assert prompt.updated_by == manager
    client.force_login(owner)
    assert client.get(config_url).status_code == 404
    rendered = client.get(url)
    assert rendered.context["program_prompts"] == [
        "Bukti apa yang Anda miliki?",
        "Pengalaman apa yang penting?",
    ]
    assert rendered.context["form"].initial["body"] == "Teks revisi"
    client.force_login(manager)
    edit = reverse("academics:edit_reflection_prompt", args=[program.pk, prompt.pk])
    assert client.post(edit, {**prompt_data, "is_active": ""}).status_code == 403
    curriculum_role.permissions.add(Permission.objects.get(codename="change_reflectionprompt"))
    assert client.post(edit, {**prompt_data, "is_active": ""}).status_code == 302
    client.force_login(owner)
    assert client.get(url).context["program_prompts"] == ["Bukti apa yang Anda miliki?"]
    assert ReflectionRevision.objects.count() == 2

    advisor = User.objects.create_user(username="advisor")
    advisor_role = AccessRole.objects.create(
        name="Pembimbing Refleksi", scope=AccessRole.Scope.PROGRAM, updated_by=outsider
    )
    advisor_role.permissions.add(Permission.objects.get(codename="view_reflectionshare"))
    UserRoleAssignment.objects.create(
        account=advisor, role=advisor_role, program=program, assigned_by=outsider
    )
    assignment_url = reverse("academics:reflection_advisors", args=[program.pk, enrollment.pk])
    client.force_login(manager)
    assert (
        client.post(assignment_url, {"action": "assign", "advisor": advisor.pk}).status_code == 403
    )
    curriculum_role.permissions.add(
        Permission.objects.get(codename="add_reflectionadvisorassignment")
    )
    assert (
        client.post(assignment_url, {"action": "assign", "advisor": advisor.pk}).status_code == 302
    )
    assignment = ReflectionAdvisorAssignment.objects.get(advisor=advisor)
    first = ReflectionRevision.objects.get(number=1)
    share_url = reverse("reflection_share", args=[enrollment.pk, first.pk])
    client.force_login(advisor)
    assert client.get(url).status_code == 404
    assert (
        client.post(share_url, {"action": "share", "assignment": assignment.pk}).status_code == 404
    )
    client.force_login(owner)
    assert (
        client.post(share_url, {"action": "share", "assignment": assignment.pk}).status_code == 302
    )
    share = ReflectionShare.objects.get(revision=first)
    read_url = reverse("shared_reflection", args=[share.pk])
    client.force_login(advisor)
    shared = client.get(read_url)
    assert shared.status_code == 200 and "Teks pribadi" in shared.content.decode()
    assert "Teks revisi" not in shared.content.decode()
    assert "no-store" in shared["Cache-Control"]
    coaching_url = reverse("reflection_coaching", args=[share.pk])
    assert client.post(coaching_url, {"body": "Pesan pembimbing"}).status_code == 404
    coaching_permission = Permission.objects.get(codename="add_reflectioncoachingmessage")
    advisor_role.permissions.add(coaching_permission)
    role.permissions.add(coaching_permission)
    assert client.post(coaching_url, {"body": "Pesan pembimbing"}).status_code == 302
    client.force_login(owner)
    assert client.post(coaching_url, {"body": "Jawaban mahasiswa"}).status_code == 302
    assert "Pesan pembimbing" in client.get(coaching_url).content.decode()
    recommendation_data = {
        "action": "recommend",
        "body": "Ulangi latihan dengan umpan balik.",
        "due_on": "2027-01-15",
    }
    assert client.post(coaching_url, recommendation_data).status_code == 404
    client.force_login(advisor)
    assert client.post(coaching_url, recommendation_data).status_code == 404
    advisor_role.permissions.add(Permission.objects.get(codename="add_coachingrecommendation"))
    assert client.post(coaching_url, recommendation_data).status_code == 302
    recommendation = CoachingRecommendation.objects.get()
    assert recommendation.author == advisor and recommendation.due_on == date(2027, 1, 15)
    complete = {
        "action": "complete",
        "recommendation": recommendation.pk,
        "note": "Latihan dicoba.",
    }
    assert client.post(coaching_url, complete).status_code == 404
    client.force_login(owner)
    assert client.post(coaching_url, complete).status_code == 404
    role.permissions.add(Permission.objects.get(codename="complete_coachingrecommendation"))
    assert client.post(coaching_url, complete).status_code == 302
    assert client.post(coaching_url, {**complete, "note": "Ulang terkirim"}).status_code == 302
    recommendation.refresh_from_db()
    assert (
        recommendation.completed_at is not None
        and recommendation.completion_note == "Latihan dicoba."
    )
    client.force_login(outsider)
    assert client.get(read_url).status_code == 404
    client.force_login(owner)
    assert client.post(share_url, {"action": "revoke", "share": share.pk}).status_code == 302
    share.refresh_from_db()
    assert share.revoked_at is not None
    client.force_login(advisor)
    assert client.get(read_url).status_code == 404
    assert client.get(coaching_url).status_code == 404
    client.force_login(owner)
    history = client.get(coaching_url).content.decode()
    assert "Jawaban mahasiswa" in history and "Latihan dicoba." in history
    assert client.post(coaching_url, {"body": "Setelah pencabutan"}).status_code == 404
    assert (
        client.post(share_url, {"action": "share", "assignment": assignment.pk}).status_code == 302
    )
    new_share = ReflectionShare.objects.get(revision=first, revoked_at__isnull=True)
    client.force_login(manager)
    assert (
        client.post(assignment_url, {"action": "revoke", "assignment": assignment.pk}).status_code
        == 302
    )
    client.force_login(advisor)
    assert client.get(reverse("shared_reflection", args=[new_share.pk])).status_code == 404
