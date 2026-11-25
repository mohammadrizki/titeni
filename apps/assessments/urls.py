from django.urls import path

from apps.assessments import views

app_name = "assessments"
urlpatterns = [
    path("", views.blueprints, name="blueprints"),
    path("draf/<int:version_id>/", views.blueprint_draft, name="blueprint_draft"),
]
