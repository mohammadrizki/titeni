from django import template
from django.db.models import Model
from django.urls import reverse

from apps.academics.models import StudyProgram
from apps.academics.row_actions import ROWS, editable, permission
from apps.accounts.access import program_role_permissions
from apps.accounts.models import User

register = template.Library()


@register.inclusion_tag("academics/row_buttons.html", takes_context=True)
def academic_row(
    context: template.Context, record: Model, kind: str, program: StudyProgram, user: User
) -> dict:
    cache_key = f"academic_row_permissions:{user.pk}:{program.pk}"
    role_permissions = context.render_context.get(cache_key)
    if role_permissions is None:
        role_permissions = program_role_permissions(user, program.pk)
        context.render_context[cache_key] = role_permissions
    spec = ROWS[kind]

    def url(action: str) -> str:
        return reverse("academics:row_action", args=[program.pk, kind, record.pk, action])

    def allowed(action: str) -> bool:
        required = permission(spec, action)
        return user.has_perm(required) or required in role_permissions

    return {
        "preview_url": url("lihat"),
        "edit_url": url("sunting") if allowed("change") and editable(record) else "",
        "delete_url": url("hapus") if allowed("delete") else "",
    }
