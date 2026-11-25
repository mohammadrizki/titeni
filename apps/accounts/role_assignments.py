from typing import cast
from uuid import UUID

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.academics.models import StudyProgram
from apps.accounts.models import AccessRole, User, UserRoleAssignment
from apps.accounts.users import require_superuser


class RoleAssignmentForm(forms.Form):
    roles = forms.ModelMultipleChoiceField(
        label="Peran",
        queryset=AccessRole.objects.exclude(scope=AccessRole.Scope.OTHER),
        widget=forms.CheckboxSelectMultiple,
    )
    program = forms.ModelChoiceField(
        label="Program studi",
        queryset=StudyProgram.objects.all(),
        required=False,
        help_text="Wajib diisi jika memilih peran berlingkup program studi.",
    )


@require_http_methods(["GET", "POST"])
@login_required
def assign_roles(request: HttpRequest, account_id: UUID) -> HttpResponse:
    actor = cast(User, request.user)
    require_superuser(actor)
    account = get_object_or_404(User, pk=account_id)
    form = RoleAssignmentForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            selected = form.cleaned_data["roles"]
            roles = list(
                AccessRole.objects.select_for_update()
                .filter(pk__in=selected.values("pk"))
                .order_by("pk")
            )
            program = form.cleaned_data["program"]
            has_program_role = any(role.scope == AccessRole.Scope.PROGRAM for role in roles)
            if len(roles) != len(selected) or any(
                role.scope == AccessRole.Scope.OTHER for role in roles
            ):
                form.add_error("roles", "Pilihan peran berubah. Pilih kembali peran yang tersedia.")
            elif has_program_role and not program:
                form.add_error("program", "Pilih program studi untuk peran berlingkup prodi.")
            else:
                account = get_object_or_404(User.objects.select_for_update(), pk=account_id)
                if has_program_role:
                    program = get_object_or_404(
                        StudyProgram.objects.select_for_update(), pk=program.pk
                    )
                created = 0
                for role in roles:
                    _, added = UserRoleAssignment.objects.get_or_create(
                        account=account,
                        role=role,
                        program=program if role.scope == AccessRole.Scope.PROGRAM else None,
                        defaults={"assigned_by": actor},
                    )
                    created += added
                if created:
                    messages.success(request, "Penugasan peran berhasil disimpan.")
                else:
                    messages.info(request, "Peran yang dipilih sudah ditugaskan.")
                return redirect("accounts:directory")
    return render(request, "accounts/assign_roles.html", {"account": account, "form": form})
