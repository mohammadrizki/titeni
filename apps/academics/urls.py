from django.urls import include, path

from apps.academics import cohorts, curriculum, row_actions, views
from apps.adaptive import analytics_views
from apps.learning.academic_advisors import manage_advisors
from apps.learning.progression import assign as assign_progression_review
from apps.reflection.prompt_views import manage_prompts
from apps.reflection.sharing import advisors

app_name = "academics"
urlpatterns = [
    path(
        "prodi/<int:program_id>/analitik/",
        analytics_views.report,
        name="program_analytics",
    ),
    path(
        "prodi/<int:program_id>/analitik/<int:period_id>/",
        analytics_views.report,
        name="program_analytics_period",
    ),
    path(
        "prodi/<int:program_id>/progresi/<int:enrollment_id>/",
        assign_progression_review,
        name="assign_progression_review",
    ),
    path(
        "prodi/<int:program_id>/pembimbing-akademik/<int:enrollment_id>/",
        manage_advisors,
        name="academic_advisors",
    ),
    path(
        "prodi/<int:program_id>/pembimbing-refleksi/<int:enrollment_id>/",
        advisors,
        name="reflection_advisors",
    ),
    path("prodi/<int:program_id>/pemantik-refleksi/", manage_prompts, name="reflection_prompts"),
    path(
        "prodi/<int:program_id>/pemantik-refleksi/<int:prompt_id>/",
        manage_prompts,
        name="edit_reflection_prompt",
    ),
    path("prodi/<int:program_id>/sumber-bukti/", include("apps.evidence.urls")),
    path(
        "prodi/<int:program_id>/baris/<slug:kind>/<int:row_id>/<slug:action>/",
        row_actions.row_action,
        name="row_action",
    ),
    path(
        "pendaftaran-prodi/<int:program_id>/pratinjau/",
        row_actions.preview_program,
        name="preview_program",
    ),
    path("prodi/<int:program_id>/blueprint/", include("apps.assessments.urls")),
    path("prodi/<int:program_id>/epa/", include("apps.epa.urls")),
    path("prodi/<int:program_id>/kompetensi/", include("apps.competencies.urls")),
    path("prodi/<int:program_id>/kohort/", cohorts.cohorts, name="cohorts"),
    path(
        "prodi/<int:program_id>/kohort/<int:cohort_id>/mahasiswa/",
        cohorts.enrollments,
        name="enrollments",
    ),
    path("prodi/<int:program_id>/kurikulum/", curriculum.curricula, name="curricula"),
    path(
        "prodi/<int:program_id>/kurikulum/<int:curriculum_id>/draf/",
        curriculum.new_curriculum_version,
        name="new_curriculum_version",
    ),
    path(
        "prodi/<int:program_id>/kurikulum/versi/<int:version_id>/",
        curriculum.curriculum_version,
        name="curriculum_version",
    ),
    path("", views.programs, name="programs"),
    path("fakultas/", views.faculty, name="faculty"),
    path("pendaftaran-prodi/", views.register_program, name="register_program"),
    path("pendaftaran-prodi/<int:program_id>/hapus/", views.delete_program, name="delete_program"),
    path("prodi/<int:program_id>/periode/", views.periods, name="periods"),
]
