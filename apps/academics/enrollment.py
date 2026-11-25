from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics.models import Cohort, Learner, LearnerEnrollment, StudyProgram
from apps.accounts.authentication import accounts_with_email
from apps.accounts.models import User
from apps.evidence.baselines import initialize_baseline


@transaction.atomic
def enroll_account(
    cohort: Cohort, *, email: str, enrolled_on: date, actor: User
) -> LearnerEnrollment:
    program_id = cohort.period.program_id
    StudyProgram.objects.select_for_update().get(pk=program_id)
    account = accounts_with_email(email).filter(is_active=True).select_for_update().first()
    if account is None:
        raise ValidationError("Akun aktif dengan email ini tidak ditemukan.")
    learner, _ = Learner.objects.get_or_create(account=account)
    enrollment, created = cohort.enrollments.get_or_create(
        learner=learner, defaults={"enrolled_on": enrolled_on, "created_by": actor}
    )
    if not created:
        raise ValidationError("Mahasiswa sudah terdaftar pada kohort ini.")
    initialize_baseline(enrollment, program_id=program_id, actor=actor)
    return enrollment
