from typing import Any, cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from django.forms.models import ModelChoiceIteratorValue
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.models import AccessRole, User


class GroupedPermissionCheckboxes(forms.CheckboxSelectMultiple):
    template_name = "accounts/permission_checkboxes.html"

    def optgroups(self, name, value, attrs=None):
        labels = {
            "academics": "Academic",
            "accounts": "Accounts",
            "competencies": "Kompetensi",
            "evidence": "Bukti",
            "adaptive": "Evaluasi bukti",
            "reflection": "Refleksi",
            "learning": "Rencana belajar",
            "assessments": "Asesmen",
        }
        groups: dict[str, list[dict[str, Any]]] = {}
        for _, options, _ in super().optgroups(name, value, attrs):
            for option in options:
                choice = option["value"]
                assert isinstance(choice, ModelChoiceIteratorValue)
                permission = cast(Permission, choice.instance)  # type: ignore[attr-defined]
                app_label = permission.content_type.app_label
                groups.setdefault(app_label, []).append(option)
        return [
            (labels.get(app_label, app_label.replace("_", " ").title()), options, index)
            for index, (app_label, options) in enumerate(groups.items())
        ]


class AccessRoleForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        label="Hak akses",
        queryset=Permission.objects.filter(
            content_type__app_label__in=[
                "accounts",
                "academics",
                "assessments",
                "competencies",
                "evidence",
                "adaptive",
                "reflection",
                "learning",
            ]
        )
        .select_related("content_type")
        .order_by("content_type__app_label", "name", "pk"),
        widget=GroupedPermissionCheckboxes,
        required=False,
    )

    class Meta:
        model = AccessRole
        fields = ["name", "permissions", "scope"]


@require_http_methods(["GET", "POST"])
@login_required
def role_matrix(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    role = None
    role_id = request.GET.get("sunting")
    if role_id is not None:
        if not role_id.isascii() or not role_id.isdecimal() or len(role_id) > 19:
            raise Http404
        role = get_object_or_404(AccessRole, pk=int(role_id))
    form = AccessRoleForm(request.POST if request.method == "POST" else None, instance=role)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.updated_by = actor
        try:
            with transaction.atomic():
                if role_id is None:
                    updated.save()
                else:
                    original = get_object_or_404(AccessRole.objects.select_for_update(), pk=role_id)
                    if original.scope != updated.scope and original.assignments.exists():
                        form.add_error(
                            "scope", "Ruang lingkup peran yang sudah ditugaskan tidak dapat diubah."
                        )
                        return render_role_matrix(request, form, role)
                    updated.save(force_update=True)
                form.save_m2m()
        except IntegrityError:
            if not AccessRole.objects.filter(name=updated.name).exclude(pk=updated.pk).exists():
                raise
            form.add_error("name", "Nama peran sudah digunakan.")
        else:
            messages.success(request, "Peran berhasil disimpan.")
            return redirect("accounts:roles")
    return render_role_matrix(request, form, role)


def render_role_matrix(
    request: HttpRequest, form: AccessRoleForm, role: AccessRole | None
) -> HttpResponse:
    permissions = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "name", "pk"
    )
    roles = AccessRole.objects.prefetch_related(Prefetch("permissions", queryset=permissions))
    if role is not None:
        roles = roles.exclude(pk=role.pk)
    return render(request, "accounts/roles.html", {"form": form, "editing": role, "roles": roles})


@require_http_methods(["GET", "POST"])
@login_required
def delete_role(request: HttpRequest, role_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    role = get_object_or_404(AccessRole, pk=role_id)
    if request.method == "POST":
        try:
            with transaction.atomic():
                role.delete()
        except ProtectedError:
            return render(
                request, "accounts/delete_role.html", {"role": role, "protected": True}, status=409
            )
        messages.success(request, "Peran berhasil dihapus.")
        return redirect("accounts:roles")
    return render(request, "accounts/delete_role.html", {"role": role})
