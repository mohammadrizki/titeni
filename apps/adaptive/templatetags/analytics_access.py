from django import template

from apps.accounts.models import User
from apps.adaptive.analytics_views import analytics_programs

register = template.Library()


@register.simple_tag
def has_analytics_programs(user: User) -> bool:
    return analytics_programs(user).exists()
