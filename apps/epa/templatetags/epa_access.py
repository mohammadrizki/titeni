from django import template

from apps.accounts.models import User
from apps.epa.committees import active_mandates
from apps.epa.decisions import own_decisions
from apps.epa.observations import own_assignments
from apps.epa.reviews import own_review_assignments

register = template.Library()


@register.simple_tag
def has_epa_assignments(user: User) -> bool:
    return user.is_authenticated and own_assignments(user).exists()


@register.simple_tag
def has_epa_reviews(user: User) -> bool:
    return user.is_authenticated and own_review_assignments(user).exists()


@register.simple_tag
def has_epa_committee_mandates(user: User) -> bool:
    return user.is_authenticated and active_mandates(user).exists()


@register.simple_tag
def has_epa_decisions(user: User) -> bool:
    return user.is_authenticated and own_decisions(user).exists()
