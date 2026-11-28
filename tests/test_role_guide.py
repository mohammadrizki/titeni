import re

import pytest
from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertContains, assertNotContains

from apps.academics.models import Institution, StudyProgram
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.role_catalog import ROLE_CATALOG, synchronize_roles


@pytest.mark.django_db
def test_guide_shows_all_and_only_assigned_roles(client: Client) -> None:
    admin = User.objects.create_superuser(username="admin-panduan")
    lecturer = User.objects.create_user(username="dosen-panduan")
    other = User.objects.create_user(username="pengguna-panduan-lain")
    faculty = Institution.objects.create(name="Fakultas", updated_by=admin)
    first, second = [
        StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=name,
            education_stage=StudyProgram.Stage.UNDERGRADUATE,
            created_by=admin,
        )
        for code, name in (("a", "Prodi A"), ("b", "Prodi B"))
    ]
    synchronize_roles(admin, apply=True)
    assert all(definition.guide.steps for definition in ROLE_CATALOG.values())
    assessor = AccessRole.objects.get(name="Asesor")
    synthesis = AccessRole.objects.get(name="Peninjau Sintesis")
    local = AccessRole.objects.create(
        name="Fungsi lokal", scope=AccessRole.Scope.PROGRAM, updated_by=admin
    )
    for account, role, program in (
        (lecturer, assessor, first),
        (lecturer, assessor, second),
        (lecturer, synthesis, first),
        (lecturer, local, first),
        (other, AccessRole.objects.get(name="Penanggung Jawab Akademik Prodi"), second),
    ):
        UserRoleAssignment.objects.create(
            account=account, role=role, program=program, assigned_by=admin
        )

    url = reverse("role_guide")
    assert client.get(url).status_code == 302
    assertNotContains(client.get(reverse("home")), f'href="{url}"')
    client.force_login(lecturer)
    response = client.get(url, {"role": "Penanggung Jawab Akademik Prodi"})
    guides = response.context["role_guides"]
    assert [item.role.name for item in guides] == ["Asesor", "Fungsi lokal", "Peninjau Sintesis"]
    assert guides[0].programs == ["Prodi A", "Prodi B"]
    assertContains(response, "Mencatat temuan terstruktur dan observasi tempat kerja")
    assertContains(response, "Penugasan Peninjau Sintesis")
    assertContains(response, "Panduan tersendiri untuk peran ini belum tersedia")
    assertNotContains(response, ROLE_CATALOG["Penanggung Jawab Akademik Prodi"].guide.summary)
    assertContains(response, f'<h2 class="section-title" id="peran-{assessor.pk}"', count=1)
    assert "no-store" in response.headers["Cache-Control"]
    navs = re.findall(
        r'<nav aria-label="Menu aplikasi".*?</nav>', response.content.decode(), flags=re.S
    )
    assert len(navs) == 2
    for nav in navs:
        assert re.search(
            rf'<a class="nav-link role-guide-link" href="{url}" aria-current="page">'
            r"Panduan</a>\s*</nav>$",
            nav,
        )

    client.force_login(other)
    assert [item.role.name for item in client.get(url).context["role_guides"]] == [
        "Penanggung Jawab Akademik Prodi"
    ]
    client.force_login(admin)
    empty = client.get(url)
    assert empty.context["role_guides"] == []
    assertContains(empty, "Belum ada peran yang ditugaskan")
