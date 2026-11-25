from django.urls import path

from apps.assessments import acquisition, evidence_artifacts, evidence_import, views

app_name = "assessments"
urlpatterns = [
    path("pelaksanaan/", acquisition.events, name="events"),
    path("pelaksanaan/<int:event_id>/", acquisition.attempts, name="attempts"),
    path(
        "pelaksanaan/<int:event_id>/percobaan/<int:attempt_id>/",
        acquisition.attempt_evidence,
        name="attempt_evidence",
    ),
    path(
        "pelaksanaan/<int:event_id>/percobaan/<int:attempt_id>/bukti/<int:record_id>/",
        acquisition.verify_evidence,
        name="verify_evidence",
    ),
    path(
        "pelaksanaan/<int:event_id>/percobaan/<int:attempt_id>/impor/",
        evidence_import.import_evidence,
        name="import_evidence",
    ),
    path(
        "pelaksanaan/<int:event_id>/percobaan/<int:attempt_id>/bukti/<int:record_id>/lampiran/",
        evidence_artifacts.upload_artifact,
        name="upload_artifact",
    ),
    path(
        "pelaksanaan/<int:event_id>/percobaan/<int:attempt_id>/bukti/<int:record_id>/lampiran/<int:artifact_id>/",
        evidence_artifacts.download_artifact,
        name="download_artifact",
    ),
    path("", views.blueprints, name="blueprints"),
    path("draf/<int:version_id>/", views.blueprint_draft, name="blueprint_draft"),
]
