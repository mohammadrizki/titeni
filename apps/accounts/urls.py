from django.urls import path

from apps.accounts import role_assignments, roles, users, views

app_name = "accounts"
urlpatterns = [
    path("peran/", roles.role_matrix, name="roles"),
    path("peran/<int:role_id>/hapus/", roles.delete_role, name="delete_role"),
    path("penugasan-prodi/", views.program_grants, name="program_grants"),
    path(
        "penugasan-prodi/<int:grant_id>/cabut/",
        views.revoke_program_grant,
        name="revoke_program_grant",
    ),
    path("", views.system_workspace, name="system"),
    path(
        "akun/<uuid:account_id>/reset/", users.reset_account_password, name="reset_account_password"
    ),
    path("akun/<uuid:account_id>/hapus/", users.delete_account, name="delete_account"),
    path("akun/<uuid:account_id>/peran/", role_assignments.assign_roles, name="assign_roles"),
    path("akun/", users.account_directory, name="directory"),
]
