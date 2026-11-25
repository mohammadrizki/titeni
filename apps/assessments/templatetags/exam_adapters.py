from django import template

from apps.assessments.models import ExamImportProtocol

register = template.Library()


@register.simple_tag
def has_active_exam_protocols() -> bool:
    return ExamImportProtocol.objects.filter(active=True).exists()
