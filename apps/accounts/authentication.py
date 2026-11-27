from typing import cast

from django import forms
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import Permission
from django.db.models import QuerySet, Value
from django.db.models.functions import Lower
from django.http import HttpRequest

from apps.accounts.models import AccessRole, User
from apps.accounts.role_catalog import SYSTEM_ROLE_PERMISSIONS


def accounts_with_email(email: str) -> QuerySet[User]:
    return (
        User.objects.exclude(email="")
        .alias(login_email=Lower("email"))
        .filter(login_email=Lower(Value(email)))
    )


class EmailBackend(ModelBackend):
    def get_user_permissions(self, user_obj, obj=None) -> set[str]:
        permissions = super().get_user_permissions(user_obj, obj)
        if obj is not None or not user_obj.is_authenticated or not user_obj.is_active:
            return permissions
        if not hasattr(user_obj, "_system_role_perm_cache"):
            assigned = Permission.objects.filter(
                accessrole__scope=AccessRole.Scope.SYSTEM,
                accessrole__assignments__account=user_obj,
                accessrole__assignments__program__isnull=True,
            ).values_list("content_type__app_label", "codename")
            user_obj._system_role_perm_cache = {
                f"{app}.{code}" for app, code in assigned
            } & SYSTEM_ROLE_PERMISSIONS
        return permissions | user_obj._system_role_perm_cache

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> User | None:
        email = kwargs.get("email", username)
        if not email or password is None:
            return None
        try:
            user = accounts_with_email(email.strip()).get()
        except User.DoesNotExist:
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Email atau kata sandi salah.",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = cast(forms.EmailField, self.fields["username"])
        field.max_length = 254
        field.widget.attrs["maxlength"] = 254
