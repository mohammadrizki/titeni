from datetime import date
from io import BytesIO
from urllib.parse import urlencode
from zipfile import ZipFile

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.academics.models import Curriculum, Institution, StudyProgram
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.assessments.exam_imports.adapters import ADAPTERS
from apps.assessments.models import (
    AssessmentBlueprint,
    AssessmentEvent,
    ExamImportProtocol,
    ExamResultImport,
)
from apps.competencies.models import CompetencyFramework


def moodle_fixture() -> bytes:
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationships = "http://schemas.openxmlformats.org/package/2006/relationships"
    office_rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            f'<Relationships xmlns="{relationships}"><Relationship Id="rId1" '
            f'Type="{office_rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="{namespace}" xmlns:r="{office_rel}"><sheets>'
            '<sheet name="Nilai" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{relationships}"><Relationship Id="rId1" '
            f'Type="{office_rel}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'<worksheet xmlns="{namespace}"><sheetData>'
            '<row r="1"><c r="A1" t="inlineStr"><is><t>Judul</t></is></c></row>'
            '<row r="3"><c r="A3" t="inlineStr"><is><t>Email address</t></is></c>'
            '<c r="B3" t="inlineStr"><is><t>Grade/100.00</t></is></c></row>'
            '<row r="4"><c r="A4" t="inlineStr"><is><t>sintetis@example.test</t></is></c>'
            '<c r="B4" t="inlineStr"><is><t>81.5</t></is></c></row>'
            '<row r="5"><c r="C5" t="inlineStr"><is><t>Overall average</t></is></c>'
            '<c r="B5"><v>81.5</v></c></row>'
            "</sheetData></worksheet>",
        )
    return output.getvalue()


def test_moodle_skips_title_and_summary_and_keeps_grade_scale() -> None:
    parsed = ADAPTERS["moodle"].read(moodle_fixture(), {})
    assert not parsed.errors
    (result,) = parsed.results
    assert (result.row, result.participant, result.score, result.maximum) == (
        4,
        "sintetis@example.test",
        "81.5",
        "100.00",
    )


@pytest.mark.django_db
def test_exam_imports_use_scoped_event_and_keep_independent_adapters(client: Client) -> None:
    actor = User.objects.create_user(username="operator")
    faculty = Institution.objects.create(name="Fakultas", updated_by=actor)
    events = []
    for code in ("med", "lain"):
        program = StudyProgram.objects.create(
            institution=faculty,
            code=code,
            name=code,
            education_stage=StudyProgram.Stage.PROFESSIONAL,
            created_by=actor,
        )
        ProgramConfigurationGrant.objects.create(
            account=actor, program=program, granted_by=actor, starts_on=timezone.localdate()
        )
        curriculum = Curriculum.objects.create(program=program, code="k", name="Kurikulum")
        curriculum_version = curriculum.versions.create(number=1, created_by=actor)
        stage = curriculum_version.stages.create(code="t", name="Tahap", created_by=actor)
        framework = CompetencyFramework.objects.create(program=program)
        framework_version = framework.versions.create(number=1, created_by=actor)
        blueprint = AssessmentBlueprint.objects.create(program=program)
        version = blueprint.versions.create(
            framework_version=framework_version,
            number=1,
            created_by=actor,
        )
        component = version.items.create(
            code="ujian",
            name="Ujian",
            method="Tertulis",
            purpose="Evaluasi",
            stage=stage,
            timing="Akhir",
            created_by=actor,
        )
        events.append(
            AssessmentEvent.objects.create(
                component=component,
                name=f"Ujian {code}",
                occurred_on=date(2026, 1, 1),
                created_by=actor,
            )
        )
    event, foreign = events
    program = event.component.version.blueprint.program
    role = AccessRole.objects.create(name="Impor", scope=AccessRole.Scope.PROGRAM, updated_by=actor)
    permitted = Permission.objects.filter(
        content_type__app_label="assessments",
        codename__in=["view_examresultimport", "add_examresultimport"],
    )
    role.permissions.add(*permitted)
    examtool = reverse("exam_imports:adapter", args=["examtool"])
    moodle = reverse("exam_imports:adapter", args=["moodle"])
    other = reverse("exam_imports:adapter", args=["aplikasi-c"])
    settings_url = reverse("exam_imports:settings")
    index = reverse("exam_imports:index")

    def selection(url: str, target: AssessmentEvent) -> str:
        query = urlencode(
            {
                "method": target.component.method,
                "component": target.component_id,
                "event": target.pk,
            }
        )
        return f"{url}?{query}"

    assert client.get(moodle).status_code == 302
    client.force_login(actor)
    navigation = client.get(reverse("home")).content.decode()
    assert "Impor Hasil Ujian" in navigation
    assert f'href="{index}"' in navigation
    assert all(url not in navigation for url in (examtool, moodle, other))
    assert settings_url not in navigation
    assert client.get(settings_url).status_code == 403
    assert client.post(settings_url, {}).status_code == 403
    body = (
        b"Nomor Peserta;Nama Peserta;Sesi;Jumlah Raw Nilai;Nilai Akhir\n"
        b"0007;Nama sintetis;1;45;90,5\n0007;Nama sintetis;2;40;80\n"
    )

    def upload(url: str, target: AssessmentEvent, data: bytes, filename: str, **options):
        return client.post(
            selection(url, target),
            {
                "action": "preview",
                "file": SimpleUploadedFile(filename, data),
                **options,
            },
        )

    assert client.post(examtool, {"action": "preview"}).status_code == 403
    UserRoleAssignment.objects.create(account=actor, role=role, program=program, assigned_by=actor)
    assert client.get(moodle).headers["Location"] == index
    first = client.get(index).content.decode()
    assert 'id="exam-method"' in first and 'id="exam-component"' not in first
    assert "Pilih aplikasi" not in first
    method = {"method": event.component.method}
    second = client.get(index, method).content.decode()
    assert 'id="exam-component"' in second and 'id="exam-date"' not in second
    assert "Pilih aplikasi" not in second
    component_query: dict[str, str | int] = {**method, "component": event.component_id}
    third = client.get(index, component_query).content.decode()
    assert 'id="exam-date"' in third and "Pilih aplikasi" not in third
    fourth = client.get(index, {**component_query, "event": event.pk}).content.decode()
    assert "Pilih aplikasi" in fourth and selection(examtool, event).replace("&", "&amp;") in fourth
    assert upload(examtool, foreign, body, "nilai.csv").status_code == 404
    forged = selection(examtool, event).replace(
        f"component={event.component_id}", f"component={foreign.component_id}"
    )
    assert client.get(forged).status_code == 404
    assert client.post(examtool, {"action": "preview"}).status_code == 400
    preview = upload(examtool, event, body, "nilai.csv")
    assert preview.context["token"]
    assert not ExamResultImport.objects.exists()
    post = {"action": "import", "preview_token": preview.context["token"]}
    assert client.post(selection(moodle, event), post).status_code == 400
    target = client.post(selection(examtool, event), post).headers["Location"]
    assert client.post(selection(examtool, event), post).headers["Location"] == target
    batch = ExamResultImport.objects.get()
    assert batch.event == event and batch.adapter == "examtool" and batch.created_by == actor
    assert list(batch.results.values_list("participant", "score", "raw_score", "session")) == [
        ("0007", "90.5", "45", "1"),
        ("0007", "80", "40", "2"),
    ]
    assert "Nama sintetis" not in client.get(target).content.decode()
    denied_actor = User.objects.create_user(username="other")
    denied_actor.user_permissions.add(*permitted)
    ProgramConfigurationGrant.objects.create(
        account=denied_actor,
        program=foreign.component.version.blueprint.program,
        granted_by=actor,
        starts_on=timezone.localdate(),
    )
    client.force_login(denied_actor)
    assert client.get(target).status_code == 404
    client.force_login(actor)

    assert upload(moodle, event, moodle_fixture(), "nilai.xlsx").context["token"]
    admin = User.objects.create_superuser(username="superuser")
    client.force_login(admin)
    response = client.get(settings_url)
    assert response.status_code == 200
    assert all(item in response.content.decode() for item in ("Moodle", "ExamTool"))
    settings_data = {
        "name": "Aplikasi C",
        "delimiter": "comma",
        "participant": "ID",
        "score": "Nilai",
    }
    assert client.post(settings_url, {**settings_data, "score": "ID"}).status_code == 200
    assert not ExamImportProtocol.objects.filter(slug="aplikasi-c").exists()
    assert client.post(settings_url, settings_data).status_code == 302
    custom = ExamImportProtocol.objects.get(slug="aplikasi-c")
    assert custom.options["delimiter"] == "," and custom.options["score"] == "Nilai"
    assert custom.updated_by == admin and not custom.active
    assert client.get(other).status_code == 404

    def set_active(protocol: ExamImportProtocol, enabled: bool) -> None:
        edit_url = reverse("exam_imports:edit_protocol", args=[protocol.pk])
        assert (
            client.post(
                edit_url,
                {
                    "action": "toggle",
                    "active": "1" if enabled else "0",
                },
            ).headers["Location"]
            == settings_url
        )

    set_active(custom, True)
    client.force_login(actor)
    assert other not in client.get(reverse("home")).content.decode()
    assert (
        selection(other, event).replace("&", "&amp;")
        in client.get(index, {**component_query, "event": event.pk}).content.decode()
    )
    invalid = upload(other, event, b"ID,Nilai\nA,abc\n", "nilai.csv")
    assert invalid.context["results"].errors and not invalid.context["token"]
    generic = upload(other, event, b"ID,Nilai\nA,78\n", "nilai.csv")
    client.force_login(admin)
    edit = reverse("exam_imports:edit_protocol", args=[custom.pk])
    assert (
        client.post(edit, {**settings_data, "delimiter": "semicolon", "active": "on"}).status_code
        == 302
    )
    client.force_login(actor)
    stale = {"action": "import", "preview_token": generic.context["token"]}
    assert client.post(selection(other, event), stale).status_code == 409
    generic = upload(other, event, b"ID;Nilai\nA;78\n", "nilai.csv")
    assert (
        client.post(
            selection(other, event), {"action": "import", "preview_token": generic.context["token"]}
        ).status_code
        == 302
    )
    assert ExamResultImport.objects.get(adapter="aplikasi-c").source_label == "Aplikasi C"

    client.force_login(admin)
    for protocol in ExamImportProtocol.objects.all():
        set_active(protocol, False)
    admin_nav = client.get(reverse("home")).content.decode()
    assert ">Impor Hasil Ujian</a>" not in admin_nav
    assert settings_url in admin_nav
    client.force_login(actor)
    assert client.get(examtool).status_code == 404
    assert client.post(selection(examtool, event), post).status_code == 404
    assert client.get(target).status_code == 200
    assert target in client.get(reverse("exam_imports:index")).content.decode()
