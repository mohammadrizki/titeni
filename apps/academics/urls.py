from django.urls import include, path

from apps.academics import cohorts, curriculum, views

app_name = "academics"
urlpatterns = [
    path("prodi/<int:program_id>/blueprint/", include("apps.assessments.urls")),
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
