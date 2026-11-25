from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.authentication import EmailAuthenticationForm
from apps.evidence.external import receive_external_evidence

urlpatterns = [
    path("impor-hasil-ujian/", include("apps.assessments.exam_imports.urls")),
    path("integrasi/v1/bukti/", receive_external_evidence, name="receive_external_evidence"),
    path("", TemplateView.as_view(template_name="core/home.html"), name="home"),
    path(
        "masuk/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html", authentication_form=EmailAuthenticationForm
        ),
        name="login",
    ),
    path("keluar/", auth_views.LogoutView.as_view(), name="logout"),
    path("administrasi/", include("apps.accounts.urls")),
    path("profil/", include("apps.accounts.profile_urls")),
    path("akademik/", include("apps.academics.urls")),
]
