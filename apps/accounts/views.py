from typing import cast

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from apps.accounts.forms import ProgramConfigurationGrantForm
from apps.accounts.models import ProgramConfigurationGrant, User


@require_safe
@login_required
@permission_required("accounts.access_system_workspace", raise_exception=True)
def system_workspace(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/system_workspace.html")


@require_http_methods(["GET", "POST"])
@login_required
@permission_required(
    ("accounts.access_system_workspace", "accounts.add_programconfigurationgrant"),
    raise_exception=True,
)
def program_grants(request: HttpRequest) -> HttpResponse:
    form = ProgramConfigurationGrantForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        grant = form.save(commit=False)
        if grant.account_id == request.user.pk:
            form.add_error("account", "Pemberi izin harus berbeda dari penerima.")
        else:
            grant.granted_by = cast(User, request.user)
            grant.save()
            return redirect("accounts:program_grants")
    grants = ProgramConfigurationGrant.objects.select_related("account", "program").order_by(
        "-granted_at", "-pk"
    )
    page = Paginator(grants, 25).get_page(request.GET.get("page"))
    return render(request, "accounts/program_grants.html", {"form": form, "page": page})


@require_POST
@login_required
@permission_required(
    (
        "accounts.access_system_workspace",
        "accounts.add_programconfigurationgrant",
        "accounts.change_programconfigurationgrant",
    ),
    raise_exception=True,
)
def revoke_program_grant(request: HttpRequest, grant_id: int) -> HttpResponse:
    grant = get_object_or_404(ProgramConfigurationGrant, pk=grant_id)
    ProgramConfigurationGrant.objects.filter(pk=grant.pk, revoked_at__isnull=True).update(
        revoked_at=timezone.now(), revoked_by=request.user
    )
    return redirect("accounts:program_grants")
