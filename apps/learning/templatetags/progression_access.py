from django import template

from apps.accounts.models import User
from apps.learning.progression import own_progression_reviews
from apps.learning.progression_voting import member_mandates, student_decisions

register = template.Library()


@register.simple_tag
def has_progression_reviews(user: User) -> bool:
    return user.is_authenticated and own_progression_reviews(user).exists()


@register.simple_tag
def has_progression_mandate(user: User) -> bool:
    return user.is_authenticated and member_mandates(user).exists()


@register.simple_tag
def has_progression_decision(user: User) -> bool:
    return user.is_authenticated and student_decisions(user).exists()
