from django.urls import path

from .observations import manage
from .reviews import assign as assign_review
from .views import activity_detail, index, scale_detail

app_name = "epa"
urlpatterns = [
    path("", index, name="index"),
    path("kegiatan/<int:activity_id>/", activity_detail, name="activity"),
    path("kegiatan/<int:activity_id>/<int:version_id>/", activity_detail, name="activity_version"),
    path(
        "kegiatan/<int:activity_id>/<int:version_id>/pemberlakuan/",
        manage,
        name="manage",
    ),
    path(
        "kegiatan/<int:activity_id>/<int:version_id>/peninjauan/",
        assign_review,
        name="review_assignments",
    ),
    path("skala/<int:scale_id>/", scale_detail, name="scale"),
    path("skala/<int:scale_id>/<int:version_id>/", scale_detail, name="scale_version"),
]
