from django.urls import path

from apps.assessments.exam_imports import protocols, views

app_name = "exam_imports"
urlpatterns = [
    path("", views.index, name="index"),
    path("pengaturan/", protocols.settings, name="settings"),
    path("pengaturan/<int:protocol_id>/", protocols.settings, name="edit_protocol"),
    path("batch/<int:batch_id>/", views.batch_results, name="batch"),
    path("<slug:adapter_slug>/", views.exam_import, name="adapter"),
]
