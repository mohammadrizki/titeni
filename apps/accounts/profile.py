from typing import cast

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UsernameField
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.accounts.authentication import accounts_with_email
from apps.accounts.forms import AccountEmailForm
from apps.accounts.models import User


class ProfileForm(AccountEmailForm):
    current_password = forms.CharField(
        label="Kata sandi saat ini",
        required=False,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="Wajib diisi jika email berubah.",
    )

    class Meta:
        model = User
        fields = ["username", "email"]
        field_classes = {"username": UsernameField}
        labels = {"username": "Nama pengguna"}

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        email = cleaned.get("email")
        if (
            email
            and email != self.instance.email.lower()
            and not self.instance.check_password(self.cleaned_data.get("current_password", ""))
        ):
            self.add_error("current_password", "Masukkan kata sandi saat ini untuk mengubah email.")
        return cleaned


@sensitive_post_parameters("current_password")
@require_http_methods(["GET", "HEAD", "POST"])
@login_required
def edit_profile(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    form = ProfileForm(request.POST if request.method == "POST" else None, instance=actor)
    if request.method == "POST" and form.is_valid():
        username, email = form.cleaned_data["username"], form.cleaned_data["email"]
        try:
            with transaction.atomic():
                saved = User.objects.filter(pk=actor.pk, password=actor.password).update(
                    username=username, email=email
                )
        except IntegrityError:
            if accounts_with_email(email).exclude(pk=actor.pk).exists():
                form.add_error("email", "Email sudah digunakan.")
            elif User.objects.filter(username=username).exclude(pk=actor.pk).exists():
                form.add_error("username", "Nama pengguna sudah digunakan.")
            else:
                raise
        else:
            if saved:
                messages.success(request, "Profil Anda berhasil disimpan.")
                return redirect("profile:edit")
            form.add_error(None, "Kata sandi telah berubah. Muat ulang halaman dan coba lagi.")
    return render(request, "accounts/profile.html", {"form": form})


class ProfilePasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/change_password.html"
    success_url = reverse_lazy("profile:edit")
    success_message = "Kata sandi Anda berhasil diubah."
