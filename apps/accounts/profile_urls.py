from django.urls import path

from apps.accounts.profile import ProfilePasswordChangeView, edit_profile

app_name = "profile"
urlpatterns = [
    path("", edit_profile, name="edit"),
    path("kata-sandi/", ProfilePasswordChangeView.as_view(), name="change_password"),
]
