from dataclasses import dataclass
from typing import cast

from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import is_password_usable
from django.db.models import Exists, F, OuterRef, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.academics.models import (
    AcademicPeriod,
    Cohort,
    CurriculumStage,
    Institution,
    LearnerEnrollment,
)
from apps.accounts.access import (
    configurable_programs,
    has_program_permission,
    program_role_permissions,
)
from apps.accounts.models import AccessRole, ProgramConfigurationGrant, User, UserRoleAssignment
from apps.accounts.role_catalog import (
    ACADEMIC_MANAGER_ROLE,
    ASSESSMENT_MANAGER_ROLE,
    CURRICULUM_MANAGER_ROLE,
    ENROLLMENT_READ_PERMISSION,
    FACULTY_ADMIN_ROLE,
    PORTFOLIO_MANAGER_ROLE,
    PROGRAM_LEAD_ROLE,
    STUDENT_ROLE,
    SUPERUSER,
)
from apps.assessments.models import BlueprintItem
from apps.competencies.models import CompetencyItem
from apps.evidence.models import (
    ArtifactMapPublication,
    EvidenceSourceCapability,
    LearnerEvidenceBaseline,
)


@dataclass(frozen=True)
class Step:
    title: str
    roles: tuple[str, ...]
    instruction: str
    route: str
    system_target: bool = False

    @property
    def role_names(self) -> str:
        return ", ".join(self.roles)


ACADEMIC_OPERATORS = (ACADEMIC_MANAGER_ROLE, PROGRAM_LEAD_ROLE)
INSTITUTION_STEPS = (
    Step(
        "Isi profil fakultas",
        (FACULTY_ADMIN_ROLE, SUPERUSER),
        "Buka Administrasi Sistem → Profil Fakultas dan simpan nama.",
        "academics:faculty",
    ),
    Step(
        "Daftarkan prodi pertama",
        (FACULTY_ADMIN_ROLE, SUPERUSER),
        "Buka Administrasi Sistem → Program Studi. Isi kode, nama, dan jenjang prodi.",
        "academics:register_program",
    ),
    Step(
        "Siapkan akses petugas akademik pertama",
        (SUPERUSER, FACULTY_ADMIN_ROLE),
        "Superuser membuat akun petugas dan menugaskan peran pada prodi yang tepat di "
        "Administrasi Sistem → Pengguna. Administrator Fakultas memberi tiap petugas "
        "penugasan yang berlaku melalui Administrasi Sistem → Penugasan.",
        "accounts:program_grants",
    ),
)
PROGRAM_STEPS = (
    Step(
        "Buat periode akademik",
        ACADEMIC_OPERATORS,
        "Pilih prodi di Akademik, lalu isi Periode akademik beserta tanggal mulai dan selesai.",
        "academics:periods",
    ),
    Step(
        "Buat kohort",
        ACADEMIC_OPERATORS,
        "Buka Kohort dan hubungkan angkatan ke periodenya.",
        "academics:cohorts",
    ),
    Step(
        "Siapkan tahap kurikulum",
        (CURRICULUM_MANAGER_ROLE, PROGRAM_LEAD_ROLE),
        "Buka Kurikulum. Buat kurikulum dan versinya, lalu tambahkan tahap.",
        "academics:curricula",
    ),
    Step(
        "Susun kerangka kompetensi",
        (CURRICULUM_MANAGER_ROLE, PROGRAM_LEAD_ROLE),
        "Buka Kompetensi. Buat versi kerangka dan tambahkan butir yang akan dinilai.",
        "academics:competencies:framework",
    ),
    Step(
        "Siapkan sumber bukti",
        (PORTFOLIO_MANAGER_ROLE, PROGRAM_LEAD_ROLE),
        "Daftarkan jenis dan sumber di Sumber bukti, lalu hubungkan keduanya sebagai kapabilitas.",
        "academics:evidence:registry",
    ),
    Step(
        "Buat komponen blueprint asesmen",
        (ASSESSMENT_MANAGER_ROLE, PROGRAM_LEAD_ROLE),
        "Di Blueprint asesmen, pilih versi kompetensi, tambahkan komponen, lalu petakan "
        "kompetensi, sumber bukti, dan aturan pengambilan sampel sesuai rancangan prodi.",
        "academics:assessments:blueprints",
    ),
    Step(
        "Terbitkan peta artefak",
        (PROGRAM_LEAD_ROLE,),
        "Buka Peta Artefak. Periksa pratinjau dari blueprint, simpan versinya, pilih "
        "setidaknya satu persyaratan yang berlaku, lalu terbitkan. Gunakan tanggal efektif "
        "pada atau sebelum tanggal pendaftaran mahasiswa agar baseline terbentuk.",
        "academics:evidence:artifact_maps",
    ),
    Step(
        "Siapkan akun dan peran Mahasiswa",
        (SUPERUSER,),
        "Di Administrasi Sistem → Pengguna, buat akun aktif dengan email dan kata sandi. "
        "Buka Tambah peran dan pilih Mahasiswa serta prodi yang sesuai.",
        "accounts:directory",
        system_target=True,
    ),
    Step(
        "Daftarkan mahasiswa ke kohort",
        ACADEMIC_OPERATORS,
        "Di Akademik → Kohort, buka daftar mahasiswa pada kohort yang tepat. Daftarkan "
        "akun menggunakan email yang sama dan tanggal pendaftaran yang sesuai. "
        "Hubungi pengelola prodi jika pendaftaran sudah ada saat peta pertama diterbitkan. "
        "Baseline dibuat saat pendaftaran.",
        "academics:cohorts",
    ),
    Step(
        "Mahasiswa siap memulai",
        ACADEMIC_OPERATORS,
        "Pastikan pendaftaran memiliki baseline bukti. Mahasiswa masuk dengan emailnya, "
        "memilih pendaftaran di Refleksi Pribadi atau Rencana Belajar, lalu mulai "
        "menulis refleksi atau membuat tujuan belajar.",
        "academics:cohorts",
    ),
)


def assigned_roles(actor: User) -> tuple[set[str], dict[int, set[str]]]:
    system: set[str] = set()
    programs: dict[int, set[str]] = {}
    for scope, name, program_id in actor.role_assignments.values_list(
        "role__scope", "role__name", "program_id"
    ):
        if scope == AccessRole.Scope.SYSTEM and program_id is None:
            system.add(name)
        elif scope == AccessRole.Scope.PROGRAM and program_id is not None:
            programs.setdefault(program_id, set()).add(name)
    return system, programs


def responsible(actor: User, step: Step, roles: set[str]) -> bool:
    return (actor.is_superuser and SUPERUSER in step.roles) or not (roles - {SUPERUSER}).isdisjoint(
        step.roles
    )


@never_cache
@require_safe
@login_required
def guide(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    system_roles, program_roles = assigned_roles(actor)
    roles = set().union(*program_roles.values())
    return render(
        request,
        "core/onboarding_guide.html",
        {
            "institution_steps": [
                step for step in INSTITUTION_STEPS if responsible(actor, step, system_roles)
            ],
            "program_steps": [step for step in PROGRAM_STEPS if responsible(actor, step, roles)],
            "is_student": STUDENT_ROLE in roles,
        },
    )


def institution_progress(actor: User) -> tuple[bool | None, ...]:
    today = timezone.localdate()
    grants = ProgramConfigurationGrant.objects.filter(
        account__is_active=True, starts_on__lte=today, revoked_at__isnull=True
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    academic_assignment = UserRoleAssignment.objects.filter(
        account_id=OuterRef("account_id"),
        program_id=OuterRef("program_id"),
        role__scope=AccessRole.Scope.PROGRAM,
        role__permissions__content_type__app_label="academics",
        role__permissions__codename="add_learnerenrollment",
    )
    return (
        Institution.objects.exists() if actor.has_perm("academics.change_institution") else None,
        Institution.objects.filter(studyprogram__isnull=False).exists()
        if actor.has_perm("academics.add_studyprogram")
        else None,
        grants.filter(Exists(academic_assignment)).exists()
        if actor.has_perm("accounts.add_programconfigurationgrant")
        else None,
    )


def student_progress(program_id: int) -> tuple[bool, bool, bool]:
    assignments = UserRoleAssignment.objects.filter(
        program_id=program_id,
        role__scope=AccessRole.Scope.PROGRAM,
        role__name=STUDENT_ROLE,
        account__is_active=True,
    ).exclude(account__email="")
    permissions = set(
        assignments.values_list(
            "role__permissions__content_type__app_label", "role__permissions__codename"
        ).distinct()
    )
    has_student_access = {
        ("reflection", "add_reflection"),
        ("learning", "add_learninggoal"),
    } <= permissions

    accounts = User.objects.filter(pk__in=assignments.values("account_id")).exclude(password="")
    enrollments = LearnerEnrollment.objects.filter(cohort__period__program_id=program_id)
    # All readiness conditions refer to the same enrollment and the same student account.
    ready = enrollments.filter(
        learner__account__in=accounts,
        evidence_baseline__publication__artifact_map__program_id=program_id,
        evidence_baseline__publication__version__blueprint_version__blueprint__program_id=(
            program_id
        ),
    )
    return (
        has_student_access
        and any(map(is_password_usable, accounts.values_list("password", flat=True).iterator())),
        enrollments.exists(),
        has_student_access
        and any(
            map(
                is_password_usable,
                ready.values_list("learner__account__password", flat=True).iterator(),
            )
        ),
    )


def program_progress(actor: User, program_id: int) -> tuple[bool | None, ...]:
    enrollment_status: tuple[bool | None, ...] = (None, None, None)
    if has_program_permission(actor, program_id, ENROLLMENT_READ_PERMISSION):
        enrollment_status = student_progress(program_id)
    return (
        AcademicPeriod.objects.filter(program_id=program_id).exists(),
        Cohort.objects.filter(period__program_id=program_id).exists(),
        CurriculumStage.objects.filter(version__curriculum__program_id=program_id).exists(),
        CompetencyItem.objects.filter(version__framework__program_id=program_id).exists(),
        EvidenceSourceCapability.objects.filter(
            source__program_id=program_id, evidence_type__program_id=program_id
        ).exists(),
        BlueprintItem.objects.filter(version__blueprint__program_id=program_id).exists(),
        ArtifactMapPublication.objects.filter(artifact_map__program_id=program_id).exists(),
        *enrollment_status,
    )


def student_recap(actor: User, program_ids: set[int]) -> list[dict]:
    matching_baseline = LearnerEvidenceBaseline.objects.filter(
        enrollment_id=OuterRef("pk"),
        publication__artifact_map__program_id=OuterRef("cohort__period__program_id"),
        publication__version__blueprint_version__blueprint__program_id=OuterRef(
            "cohort__period__program_id"
        ),
    )
    enrollments = LearnerEnrollment.objects.filter(
        learner__account=actor,
        cohort__period__program_id__in=program_ids,
    ).values(
        "pk",
        program_id=F("cohort__period__program_id"),
        program_name=F("cohort__period__program__name"),
        cohort_name=F("cohort__name"),
        has_baseline=Exists(matching_baseline),
    )
    access = {program_id: program_role_permissions(actor, program_id) for program_id in program_ids}
    recap = []
    for enrollment in enrollments:
        permissions = access[enrollment["program_id"]]
        recap.append(
            {
                **enrollment,
                "can_reflect": "reflection.add_reflection" in permissions,
                "can_plan": "learning.add_learninggoal" in permissions,
            }
        )
    return recap


@dataclass(frozen=True)
class ChecklistItem:
    step: Step
    done: bool
    url: str


def checklist_item(step: Step, done: bool, program_id: int | None = None) -> ChecklistItem:
    args = [] if step.system_target or program_id is None else [program_id]
    return ChecklistItem(step, done, "" if done else reverse(step.route, args=args))


@never_cache
@require_safe
def home(request: HttpRequest) -> HttpResponse:
    if not request.user.is_authenticated:
        return render(request, "core/home.html")

    actor = cast(User, request.user)
    system_roles, program_roles = assigned_roles(actor)
    student_program_ids = {
        program_id for program_id, roles in program_roles.items() if STUDENT_ROLE in roles
    }
    institution_steps = (
        [
            checklist_item(step, done)
            for step, done in zip(INSTITUTION_STEPS, institution_progress(actor), strict=True)
            if done is not None and responsible(actor, step, system_roles)
        ]
        if actor.has_perm("accounts.access_system_workspace")
        else []
    )
    programs = [
        item
        for item in configurable_programs(actor)
        if any(
            responsible(actor, step, program_roles.get(item.pk, set())) for step in PROGRAM_STEPS
        )
    ]
    selected = request.GET.get("prodi")
    program = next((item for item in programs if str(item.pk) == selected), None)
    if program is None and programs:
        program = programs[0]
    program_steps = (
        [
            checklist_item(step, done, program.pk)
            for step, done in zip(PROGRAM_STEPS, program_progress(actor, program.pk), strict=True)
            if done is not None and responsible(actor, step, program_roles.get(program.pk, set()))
        ]
        if program is not None
        else []
    )
    return render(
        request,
        "core/home.html",
        {
            "institution_steps": institution_steps,
            "programs": programs,
            "program": program,
            "program_steps": program_steps,
            "show_onboarding": bool(institution_steps or program_steps or student_program_ids),
            "is_student": bool(student_program_ids),
            "student_recap": student_recap(actor, student_program_ids)
            if student_program_ids
            else [],
        },
    )
