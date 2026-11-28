from dataclasses import dataclass, field
from typing import cast

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .guide_content import RoleGuide
from .models import AccessRole, User
from .role_catalog import ROLE_CATALOG


@dataclass
class AssignedGuide:
    role: AccessRole
    guide: RoleGuide | None
    programs: list[str] = field(default_factory=list)


@never_cache
@login_required
@require_safe
def index(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    assignments = actor.role_assignments.select_related("role", "program").order_by(
        "role__name", "program__name", "pk"
    )
    guides: dict[int, AssignedGuide] = {}
    for assignment in assignments:
        role = assignment.role
        if role.pk not in guides:
            definition = ROLE_CATALOG.get(role.name)
            guide = definition.guide if definition and role.scope == definition.scope else None
            guides[role.pk] = AssignedGuide(role=role, guide=guide)
        if assignment.program is not None:
            guides[role.pk].programs.append(assignment.program.name)
    return render(request, "accounts/role_guide.html", {"role_guides": list(guides.values())})
