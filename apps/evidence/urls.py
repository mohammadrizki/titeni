from django.urls import path

from apps.evidence.artifact_map import (
    artifact_map,
    artifact_maps,
    save_artifact_map,
    saved_artifact_map,
)
from apps.evidence.plans import plan_drafts
from apps.evidence.publications import publish_artifact_map
from apps.evidence.reconciliation import reconcile
from apps.evidence.requirements import evidence_requirements
from apps.evidence.views import registry

app_name = "evidence"
urlpatterns = [
    path("", registry, name="registry"),
    path(
        "rencana-individual/<int:enrollment_id>/rekonsiliasi/",
        reconcile,
        name="reconcile",
    ),
    path("rencana-individual/<int:enrollment_id>/", plan_drafts, name="plan_drafts"),
    path(
        "rencana-individual/<int:enrollment_id>/<int:plan_id>/",
        plan_drafts,
        name="plan_draft",
    ),
    path("peta-artefak/", artifact_maps, name="artifact_maps"),
    path("peta-artefak/<int:version_id>/", artifact_map, name="artifact_map"),
    path("peta-artefak/<int:version_id>/simpan/", save_artifact_map, name="save_artifact_map"),
    path(
        "peta-artefak/<int:version_id>/persyaratan/",
        evidence_requirements,
        name="evidence_requirements",
    ),
    path("peta-artefak/tersimpan/<int:map_id>/", saved_artifact_map, name="saved_artifact_map"),
    path(
        "peta-artefak/tersimpan/<int:map_id>/terbitkan/",
        publish_artifact_map,
        name="publish_artifact_map",
    ),
]
