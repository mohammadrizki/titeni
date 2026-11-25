from datetime import date

from django import forms

from apps.accounts.authentication import accounts_with_email
from apps.accounts.models import ProgramConfigurationGrant, User


class ProgramConfigurationGrantForm(forms.ModelForm):
    class Meta:
        model = ProgramConfigurationGrant
        fields = ["account", "program", "starts_on", "ends_on", "reason"]
        labels = {
            "account": "Akun",
            "program": "Program studi",
            "starts_on": "Mulai",
            "ends_on": "Selesai",
            "reason": "Alasan",
        }
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.TextInput(),
        }

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        start, end = cleaned.get("starts_on"), cleaned.get("ends_on")
        if isinstance(start, date) and isinstance(end, date) and end < start:
            self.add_error("ends_on", "Tanggal selesai harus sama atau setelah tanggal mulai.")
        account = cleaned.get("account")
        if isinstance(account, User) and not account.is_active:
            self.add_error("account", "Pilih akun yang aktif.")
        return cleaned


class AccountEmailForm(forms.ModelForm):
    email = forms.EmailField(label="Email", max_length=254)

    def clean_email(self) -> str:
        email = self.cleaned_data["email"].lower()
        accounts = accounts_with_email(email)
        if not self.instance._state.adding:
            accounts = accounts.exclude(pk=self.instance.pk)
        if accounts.exists():
            raise forms.ValidationError("Email sudah digunakan.")
        return email
