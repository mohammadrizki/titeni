from django.urls import path

from apps.competencies import views

app_name = "competencies"
urlpatterns = [
    path("", views.framework, name="framework"),
    path("draf/<int:version_id>/", views.draft, name="draft"),
]
