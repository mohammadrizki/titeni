from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User

from .models import ProgressionCommitteeMandate, ProgressionCommitteeMembership

WORKSPACE = "accounts.access_system_workspace"
VIEW = "learning.view_progressioncommitteemandate"
ADD = "learning.add_progressioncommitteemandate"
CHANGE = "learning.change_progressioncommitteemandate"
ADD_MEMBER = "learning.add_progressioncommitteemembership"
DELETE_MEMBER = "learning.delete_progressioncommitteemembership"


class MandateForm(forms.ModelForm):
    quorum = forms.IntegerField(label="Kuorum minimum", min_value=1, max_value=2147483647)

    class Meta:
        model = ProgressionCommitteeMandate
        fields = ("program", "name", "starts_on", "ends_on", "quorum")
        labels = {"program": "Program studi"}
        widgets = {
            field: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for field in ("starts_on", "ends_on")
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk is not None:
            self.fields["program"].disabled = True

    def clean(self) -> dict:
        data = super().clean() or {}
        start, end = data.get("starts_on"), data.get("ends_on")
        if start and end and end < start:
            self.add_error("ends_on", "Tanggal berakhir harus pada atau setelah awal.")
        return data


class MemberForm(forms.Form):
    account = forms.ModelChoiceField(
        label="Anggota", queryset=User.objects.filter(is_active=True).order_by("username")
    )


class IssueForm(forms.Form):
    chair = forms.ModelChoiceField(
        label="Ketua komite", queryset=ProgressionCommitteeMembership.objects.none()
    )

    def __init__(self, *args, mandate: ProgressionCommitteeMandate, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["chair"]).queryset = (
            mandate.memberships.filter(account__is_active=True)
            .select_related("account")
            .order_by("account__username")
        )


@require_http_methods(["GET", "POST"])
@login_required
@permission_required((WORKSPACE, VIEW), raise_exception=True)
def index(request: HttpRequest) -> HttpResponse:
    actor = cast(User, request.user)
    writing = request.method == "POST"
    may_create = actor.has_perm(ADD)
    if writing and not may_create:
        raise PermissionDenied
    form = MandateForm(request.POST if writing else None)
    if writing and form.is_valid():
        mandate = form.save(commit=False)
        mandate.created_by = actor
        mandate.save()
        return redirect("accounts:progression_committee", mandate.pk)
    return render(
        request,
        "learning/progression_committees.html",
        {
            "mandates": ProgressionCommitteeMandate.objects.select_related("program"),
            "form": form if may_create else None,
            "today": timezone.localdate(),
        },
        status=400 if writing else 200,
    )


@require_http_methods(["GET", "POST"])
@login_required
@permission_required((WORKSPACE, VIEW), raise_exception=True)
def detail(request: HttpRequest, mandate_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    mandates = ProgressionCommitteeMandate.objects.select_related(
        "program", "chair__account", "issued_by", "revoked_by"
    )
    mandate = get_object_or_404(mandates, pk=mandate_id)
    writing = request.method == "POST"
    action = request.POST.get("action", "") if writing else ""
    form = MandateForm(request.POST if action == "update" else None, instance=mandate)
    member_form = MemberForm(request.POST if action == "member" else None)
    issue_form = IssueForm(request.POST if action == "issue" else None, mandate=mandate)
    error = ""
    if writing:
        permission = {
            "update": CHANGE,
            "issue": CHANGE,
            "revoke": CHANGE,
            "member": ADD_MEMBER,
            "remove-member": DELETE_MEMBER,
        }.get(action)
        if permission is None:
            return HttpResponse(status=400)
        if not actor.has_perm(permission):
            raise PermissionDenied
        with transaction.atomic():
            mandate = get_object_or_404(mandates.select_for_update(of=("self",)), pk=mandate_id)
            if action == "revoke":
                if mandate.issued_at is None:
                    return HttpResponse("Mandat belum ditetapkan.", status=409)
                if mandate.revoked_at is None:
                    mandate.revoked_at, mandate.revoked_by = timezone.now(), actor
                    mandate.save(update_fields=("revoked_at", "revoked_by"))
                return redirect("accounts:progression_committee", mandate.pk)
            if mandate.issued_at is not None:
                if (
                    action == "issue"
                    and mandate.revoked_at is None
                    and request.POST.get("chair") == str(mandate.chair_id)
                ):
                    return redirect("accounts:progression_committee", mandate.pk)
                return HttpResponse("Konfigurasi mandat yang ditetapkan terkunci.", status=409)
            if action == "update":
                form = MandateForm(request.POST, instance=mandate)
                if form.is_valid():
                    form.save()
                    return redirect("accounts:progression_committee", mandate.pk)
                mandate.refresh_from_db()
            elif action == "member" and member_form.is_valid():
                mandate.memberships.get_or_create(
                    account=member_form.cleaned_data["account"], defaults={"added_by": actor}
                )
                return redirect("accounts:progression_committee", mandate.pk)
            elif action == "remove-member":
                row = forms.IntegerField(min_value=1, max_value=9223372036854775807)
                try:
                    row_id = row.clean(request.POST.get("row"))
                except forms.ValidationError:
                    return HttpResponse(status=400)
                get_object_or_404(mandate.memberships, pk=row_id).delete()
                return redirect("accounts:progression_committee", mandate.pk)
            elif action == "issue":
                issue_form = IssueForm(request.POST, mandate=mandate)
                if mandate.ends_on < timezone.localdate():
                    error = "Masa berlaku mandat sudah berakhir."
                elif mandate.memberships.filter(account__is_active=True).count() < mandate.quorum:
                    error = "Jumlah anggota aktif belum memenuhi kuorum minimum."
                elif issue_form.is_valid():
                    mandate.chair = issue_form.cleaned_data["chair"]
                    mandate.issued_at, mandate.issued_by = timezone.now(), actor
                    mandate.save(update_fields=("chair", "issued_at", "issued_by"))
                    return redirect("accounts:progression_committee", mandate.pk)
    is_draft = mandate.issued_at is None
    return render(
        request,
        "learning/progression_committee.html",
        {
            "mandate": mandate,
            "today": timezone.localdate(),
            "members": mandate.memberships.select_related("account").order_by("account__username"),
            "form": form if is_draft and actor.has_perm(CHANGE) else None,
            "issue_form": issue_form if is_draft and actor.has_perm(CHANGE) else None,
            "member_form": member_form if is_draft and actor.has_perm(ADD_MEMBER) else None,
            "may_remove_member": is_draft and actor.has_perm(DELETE_MEMBER),
            "may_revoke": not is_draft and mandate.revoked_at is None and actor.has_perm(CHANGE),
            "error": error,
        },
        status=400 if writing else 200,
    )
