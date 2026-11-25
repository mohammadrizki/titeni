from apps.academics.models import LearnerEnrollment
from apps.accounts.models import User
from apps.evidence.models import ArtifactMapPublication, LearnerEvidenceBaseline


def initialize_baseline(
    enrollment: LearnerEnrollment, *, program_id: int, actor: User
) -> LearnerEvidenceBaseline | None:
    """Resolve the publication while enrollment holds the program transaction lock."""
    publication = ArtifactMapPublication.objects.filter(
        artifact_map__program_id=program_id,
        effective_on__lte=enrollment.enrolled_on,
    ).first()
    if publication is None:
        return None
    baseline, _ = LearnerEvidenceBaseline.objects.get_or_create(
        enrollment=enrollment, defaults={"publication": publication, "created_by": actor}
    )
    return baseline
