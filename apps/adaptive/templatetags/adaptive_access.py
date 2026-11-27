from django import template

from apps.accounts.models import User
from apps.adaptive.assessor_views import assessor_programs

register = template.Library()


@register.simple_tag
def can_open_assessor_assignments(user: User) -> bool:
    return user.is_authenticated and assessor_programs(user).exists()
