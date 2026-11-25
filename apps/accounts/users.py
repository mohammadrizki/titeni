from typing import cast
from uuid import UUID

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import BaseUserCreationForm, SetPasswordForm, UsernameField
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.accounts.authentication import accounts_with_email
from apps.accounts.forms import AccountEmailForm
from apps.accounts.models import User, UserRoleAssignment


class CreateAccountForm(AccountEmailForm, BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["username", "email", "is_active"]
        field_classes = {"username": UsernameField}
        labels = {"username": "Nama pengguna", "email": "Email", "is_active": "Aktif"}

    field_order = ["username", "email", "is_active", "password1", "password2"]


class EditAccountForm(AccountEmailForm):
    class Meta(CreateAccountForm.Meta):
        pass

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.is_superuser:
            self.fields["is_active"].disabled = True


def require_superuser(actor: User) -> None:
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied


def account_directory_queryset():
    assignments = UserRoleAssignment.objects.select_related("role", "program")
    return (
        User.objects.order_by("username")
        .only("username", "email", "is_active", "is_superuser")
        .prefetch_related("groups", Prefetch("role_assignments", queryset=assignments))
    )


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "HEAD", "POST"])
@login_required
@permission_required(
    ("accounts.access_system_workspace", "accounts.view_user"), raise_exception=True
)
def account_directory(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    edit_id = request.GET.get("sunting")
    editing = None
    form: CreateAccountForm | EditAccountForm | None = None
    if edit_id is not None:
        require_superuser(actor)
        try:
            account_id = UUID(edit_id)
        except ValueError as error:
            raise Http404 from error
        editing = get_object_or_404(account_directory_queryset(), pk=account_id)
        form = EditAccountForm(request.POST if request.method == "POST" else None, instance=editing)
    elif actor.is_superuser:
        form = CreateAccountForm(request.POST if request.method == "POST" else None)

    if request.method == "POST":
        if form is None:
            return HttpResponseNotAllowed(["GET", "HEAD"])
        if form.is_valid():
            try:
                with transaction.atomic():
                    if editing is None:
                        form.save()
                    else:
                        updated = form.save(commit=False)
                        changed = User.objects.filter(pk=editing.pk).update(
                            username=updated.username,
                            email=updated.email,
                            is_active=updated.is_active,
                        )
                        if not changed:
                            raise Http404
            except IntegrityError:
                duplicates = User.objects.filter(username=form.cleaned_data["username"])
                if editing is not None:
                    duplicates = duplicates.exclude(pk=editing.pk)
                if duplicates.exists():
                    form.add_error("username", "Nama pengguna sudah digunakan.")
                else:
                    emails = accounts_with_email(form.cleaned_data["email"])
                    if editing is not None:
                        emails = emails.exclude(pk=editing.pk)
                    if not emails.exists():
                        raise
                    form.add_error("email", "Email sudah digunakan.")
            else:
                messages.success(request, "Pengguna berhasil disimpan.")
                return redirect("accounts:directory")

    accounts = account_directory_queryset()
    if editing is not None:
        accounts = accounts.exclude(pk=editing.pk)
    page = Paginator(accounts, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/directory.html",
        {
            "page": page,
            "form": form,
            "editing": editing,
        },
    )


@sensitive_post_parameters("new_password1", "new_password2")
@require_http_methods(["GET", "POST"])
@login_required
def reset_account_password(request: HttpRequest, account_id: UUID) -> HttpResponse:
    actor = cast(User, request.user)
    require_superuser(actor)
    account = get_object_or_404(User, pk=account_id)
    form = SetPasswordForm(account, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        account.set_password(form.cleaned_data["new_password1"])
        if not User.objects.filter(pk=account.pk).update(password=account.password):
            raise Http404
        if account.pk == actor.pk:
            update_session_auth_hash(request, account)
        messages.success(request, "Kata sandi pengguna berhasil direset.")
        return redirect("accounts:directory")
    return render(request, "accounts/reset_password.html", {"account": account, "form": form})


@require_http_methods(["GET", "POST"])
@login_required
def delete_account(request: HttpRequest, account_id: UUID) -> HttpResponse:
    actor = cast(User, request.user)
    require_superuser(actor)
    account = get_object_or_404(User, pk=account_id)
    if account.is_superuser:
        raise PermissionDenied
    if request.method == "POST":
        try:
            with transaction.atomic():
                account = get_object_or_404(User.objects.select_for_update(), pk=account_id)
                if account.is_superuser:
                    raise PermissionDenied
                account.delete()
        except ProtectedError:
            return render(
                request,
                "accounts/delete_account.html",
                {"account": account, "protected": True},
                status=409,
            )
        messages.success(request, "Pengguna berhasil dihapus.")
        return redirect("accounts:directory")
    return render(request, "accounts/delete_account.html", {"account": account})
