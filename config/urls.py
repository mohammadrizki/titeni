from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import TemplateView

from apps.accounts.authentication import EmailAuthenticationForm
from apps.adaptive.analytics_views import index as program_analytics
from apps.adaptive.assessor_views import assessor_artifact, assessor_assignments
from apps.epa import participation as epa_participation
from apps.epa.appeals import resolve as epa_resolve_appeal
from apps.epa.ballots import discussion as epa_discussion
from apps.epa.decisions import publish as epa_publish_decision
from apps.epa.decisions import student_decision, student_decisions
from apps.epa.observations import observations as epa_observations
from apps.epa.reviews import draft as epa_review_draft
from apps.epa.reviews import queue as epa_review_queue
from apps.evidence.external import receive_external_evidence
from apps.learning import progression_voting
from apps.learning.academic_advisors import review_queue as academic_review_queue
from apps.learning.interventions import (
    approve_intervention,
    intervention_drafts,
    report_intervention_completion,
    verify_intervention_completion,
)
from apps.learning.progression import draft as progression_review_draft
from apps.learning.progression import queue as progression_review_queue
from apps.learning.sharing import goal_shares, review_goal, review_queue
from apps.learning.views import plan
from apps.reflection.sharing import coaching, share_revision, shared_reflections
from apps.reflection.views import drafts, index

urlpatterns = [
    path("analitik-prodi/", program_analytics, name="program_analytics"),
    path("sidang-progresi/", progression_voting.queue, name="progression_committee_queue"),
    path(
        "sidang-progresi/<int:mandate_id>/",
        progression_voting.cases,
        name="progression_committee_cases",
    ),
    path(
        "sidang-progresi/<int:mandate_id>/pendaftaran/<int:enrollment_id>/",
        progression_voting.review,
        name="progression_committee_case",
    ),
    path("keputusan-progresi/", progression_voting.decisions, name="progression_decisions"),
    path(
        "keputusan-progresi/<int:decision_id>/",
        progression_voting.decision_detail,
        name="progression_decision",
    ),
    path("peninjauan-progresi/", progression_review_queue, name="progression_review_queue"),
    path(
        "peninjauan-progresi/<int:assignment_id>/",
        progression_review_draft,
        name="progression_review_draft",
    ),
    path("keputusan-epa/", student_decisions, name="epa_student_decisions"),
    path("keputusan-epa/<int:decision_id>/", student_decision, name="epa_student_decision"),
    path("suara-epa/<int:ballot_id>/terbitkan/", epa_publish_decision, name="epa_publish_decision"),
    path("suara-epa/<int:ballot_id>/hasil-banding/", epa_resolve_appeal, name="epa_resolve_appeal"),
    path("komite-epa/", epa_participation.mandates, name="epa_participation_mandates"),
    path("komite-epa/<int:mandate_id>/", epa_participation.cases, name="epa_participation_cases"),
    path(
        "komite-epa/<int:mandate_id>/versi/<int:publication_id>/pendaftaran/<int:enrollment_id>/",
        epa_participation.participate,
        name="epa_participate",
    ),
    path(
        "komite-epa/<int:mandate_id>/versi/<int:publication_id>/"
        "pendaftaran/<int:enrollment_id>/pembahasan/",
        epa_discussion,
        name="epa_committee_discussion",
    ),
    path("peninjauan-epa/", epa_review_queue, name="epa_review_queue"),
    path("peninjauan-epa/<int:assignment_id>/", epa_review_draft, name="epa_review_draft"),
    path("observasi-epa/", epa_observations, name="epa_observations"),
    path(
        "observasi-epa/<int:assignment_id>/",
        epa_observations,
        name="epa_observation_assignment",
    ),
    path("pembimbing-akademik/", academic_review_queue, name="academic_review_queue"),
    path(
        "intervensi/prodi/<int:program_id>/baseline/<int:baseline_id>/",
        approve_intervention,
        name="intervention_approvals",
    ),
    path("intervensi/", intervention_drafts, name="intervention_index"),
    path("intervensi/<int:assignment_id>/", intervention_drafts, name="intervention_drafts"),
    path(
        "intervensi/<int:assignment_id>/pelaksanaan/<int:report_id>/verifikasi/",
        verify_intervention_completion,
        name="verify_intervention_completion",
    ),
    path("rencana-belajar/tinjauan/", review_queue, name="learning_review_queue"),
    path("rencana-belajar/tinjauan/<int:share_id>/", review_goal, name="learning_goal_review"),
    path(
        "rencana-belajar/<int:enrollment_id>/<int:goal_id>/berbagi/",
        goal_shares,
        name="learning_goal_shares",
    ),
    path(
        "rencana-belajar/<int:enrollment_id>/intervensi/<int:approval_id>/pelaksanaan/",
        report_intervention_completion,
        name="intervention_completion_report",
    ),
    path("rencana-belajar/", plan, name="learning_index"),
    path("rencana-belajar/<int:enrollment_id>/", plan, name="learning_plan"),
    path("rencana-belajar/<int:enrollment_id>/<int:goal_id>/", plan, name="learning_goal"),
    path("refleksi/coaching/<int:share_id>/", coaching, name="reflection_coaching"),
    path("refleksi/dibagikan/", shared_reflections, name="shared_reflections"),
    path("refleksi/dibagikan/<int:share_id>/", shared_reflections, name="shared_reflection"),
    path(
        "refleksi/<int:enrollment_id>/bagikan/<int:revision_id>/",
        share_revision,
        name="reflection_share",
    ),
    path("refleksi/", index, name="reflection_index"),
    path("refleksi/<int:enrollment_id>/", drafts, name="reflection_drafts"),
    path("refleksi/<int:enrollment_id>/<int:reflection_id>/", drafts, name="reflection_draft"),
    path("penugasan-asesor/", assessor_assignments, name="assessor_assignments"),
    path(
        "penugasan-asesor/<int:assignment_id>/lampiran/<int:artifact_id>/",
        assessor_artifact,
        name="assessor_artifact",
    ),
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
