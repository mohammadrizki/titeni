from django.urls import path

from apps.accounts import role_assignments, roles, users, views
from apps.epa.appeals import assign as epa_assign_appeal
from apps.epa.appeals import queue as epa_appeals
from apps.epa.ballots import audit as epa_ballot_audit
from apps.epa.ballots import chair as epa_chair
from apps.epa.committees import committee, committees
from apps.epa.decisions import policies as epa_appeal_policies
from apps.epa.participation import audit as epa_participation_audit
from apps.learning import progression_appeals, progression_committees, progression_voting

app_name = "accounts"
urlpatterns = [
    path(
        "kebijakan-banding-progresi/",
        progression_appeals.policies,
        name="progression_appeal_policies",
    ),
    path("banding-progresi/", progression_appeals.queue, name="progression_appeals"),
    path(
        "banding-progresi/<int:appeal_id>/",
        progression_appeals.assign,
        name="assign_progression_appeal",
    ),
    path(
        "komite-progresi/<int:mandate_id>/suara/",
        progression_voting.audit,
        name="progression_ballot_audit",
    ),
    path("komite-progresi/", progression_committees.index, name="progression_committees"),
    path(
        "komite-progresi/<int:mandate_id>/",
        progression_committees.detail,
        name="progression_committee",
    ),
    path("kebijakan-banding-epa/", epa_appeal_policies, name="epa_appeal_policies"),
    path("banding-epa/", epa_appeals, name="epa_appeals"),
    path("banding-epa/<int:appeal_id>/", epa_assign_appeal, name="epa_assign_appeal"),
    path("komite-epa/", committees, name="epa_committees"),
    path("komite-epa/<int:mandate_id>/", committee, name="epa_committee"),
    path(
        "komite-epa/<int:mandate_id>/riwayat/",
        epa_participation_audit,
        name="epa_participation_audit",
    ),
    path("komite-epa/<int:mandate_id>/ketua/", epa_chair, name="epa_committee_chair"),
    path("komite-epa/<int:mandate_id>/suara/", epa_ballot_audit, name="epa_ballot_audit"),
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
