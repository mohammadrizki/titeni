from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.models import User

from .models import (
    EntrustableProfessionalActivity,
    EPACommitteeMandate,
)

WORKSPACE = "accounts.access_system_workspace"
VIEW = "epa.view_epacommitteemandate"
ADD = "epa.add_epacommitteemandate"
CHANGE = "epa.change_epacommitteemandate"
ADD_MEMBER = "epa.add_epacommitteemembership"
ADD_SCOPE = "epa.add_epacommitteescope"
DELETE_MEMBER = "epa.delete_epacommitteemembership"
DELETE_SCOPE = "epa.delete_epacommitteescope"


def active_mandates(actor: User) -> QuerySet[EPACommitteeMandate]:
    if not actor.is_active:
        return EPACommitteeMandate.objects.none()
    now = timezone.now()
    today = timezone.localdate(now)
    return EPACommitteeMandate.objects.filter(
        memberships__account=actor,
        memberships__account__is_active=True,
        starts_on__lte=today,
        ends_on__gte=today,
        issued_at__lte=now,
        revoked_at__isnull=True,
    )


def eligible_mandates(
    actor: User, activity: EntrustableProfessionalActivity
) -> QuerySet[EPACommitteeMandate]:
    return active_mandates(actor).filter(program_id=activity.program_id, scopes__activity=activity)


class MandateForm(forms.ModelForm):
    quorum = forms.IntegerField(label="Kuorum minimum", min_value=1, max_value=2147483647)

    class Meta:
        model = EPACommitteeMandate
        fields = ("program", "name", "starts_on", "ends_on", "quorum")
        labels = {"program": "Program studi"}
        widgets = {
            "starts_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "ends_on": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk is not None:
            self.fields["program"].disabled = True


class ScopeForm(forms.Form):
    activity = forms.ModelChoiceField(
        label="EPA", queryset=EntrustableProfessionalActivity.objects.none()
    )

    def __init__(self, *args, mandate: EPACommitteeMandate, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(
            forms.ModelChoiceField, self.fields["activity"]
        ).queryset = EntrustableProfessionalActivity.objects.filter(program_id=mandate.program_id)


class MemberForm(forms.Form):
    account = forms.ModelChoiceField(label="Anggota", queryset=User.objects.none())

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["account"]).queryset = User.objects.filter(
            is_active=True
        ).order_by("username")


@require_http_methods(["GET", "POST"])
@login_required
@permission_required((WORKSPACE, VIEW), raise_exception=True)
def committees(request: HttpRequest) -> HttpResponse:
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
        return redirect("accounts:epa_committee", mandate.pk)
    return render(
        request,
        "epa/committees.html",
        {
            "mandates": EPACommitteeMandate.objects.select_related("program"),
            "form": form if may_create else None,
            "today": timezone.localdate(),
        },
        status=400 if writing else 200,
    )


@require_http_methods(["GET", "POST"])
@login_required
@permission_required((WORKSPACE, VIEW), raise_exception=True)
def committee(request: HttpRequest, mandate_id: int) -> HttpResponse:
    actor = cast(User, request.user)
    mandates = EPACommitteeMandate.objects.select_related("program")
    mandate = get_object_or_404(mandates, pk=mandate_id)
    mandate_form = MandateForm(instance=mandate, prefix="mandate")
    scope_form = ScopeForm(mandate=mandate, prefix="scope")
    member_form = MemberForm(prefix="member")
    error = ""
    if request.method == "POST":
        action = request.POST.get("action", "")
        permission = {
            "scope": ADD_SCOPE,
            "member": ADD_MEMBER,
            "remove-scope": DELETE_SCOPE,
            "remove-member": DELETE_MEMBER,
            "update": CHANGE,
            "issue": CHANGE,
            "revoke": CHANGE,
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
                return redirect("accounts:epa_committee", mandate.pk)
            if mandate.issued_at is not None:
                if action == "issue" and mandate.revoked_at is None:
                    return redirect("accounts:epa_committee", mandate.pk)
                return HttpResponse("Konfigurasi mandat yang ditetapkan terkunci.", status=409)
            match action:
                case "update":
                    mandate_form = MandateForm(request.POST, instance=mandate, prefix="mandate")
                    if mandate_form.is_valid():
                        mandate_form.save()
                        return redirect("accounts:epa_committee", mandate.pk)
                case "scope":
                    scope_form = ScopeForm(request.POST, mandate=mandate, prefix="scope")
                    if scope_form.is_valid():
                        mandate.scopes.get_or_create(
                            activity=scope_form.cleaned_data["activity"],
                            defaults={"created_by": actor},
                        )
                        return redirect("accounts:epa_committee", mandate.pk)
                case "member":
                    member_form = MemberForm(request.POST, prefix="member")
                    if member_form.is_valid():
                        mandate.memberships.get_or_create(
                            account=member_form.cleaned_data["account"],
                            defaults={"created_by": actor},
                        )
                        return redirect("accounts:epa_committee", mandate.pk)
                case "remove-scope" | "remove-member":
                    row = forms.IntegerField(min_value=1, max_value=9223372036854775807)
                    try:
                        row_id = row.clean(request.POST.get("row"))
                    except forms.ValidationError:
                        return HttpResponse(status=400)
                    if action == "remove-scope":
                        get_object_or_404(mandate.scopes, pk=row_id).delete()
                    else:
                        get_object_or_404(mandate.memberships, pk=row_id).delete()
                    return redirect("accounts:epa_committee", mandate.pk)
                case "issue":
                    if mandate.ends_on < timezone.localdate():
                        error = "Masa berlaku mandat sudah berakhir."
                    elif not mandate.scopes.exists():
                        error = "Tambahkan setidaknya satu EPA dalam cakupan."
                    elif (
                        mandate.memberships.filter(account__is_active=True).count() < mandate.quorum
                    ):
                        error = "Jumlah anggota aktif belum memenuhi kuorum minimum."
                    else:
                        mandate.issued_at, mandate.issued_by = timezone.now(), actor
                        mandate.save(update_fields=("issued_at", "issued_by"))
                        return redirect("accounts:epa_committee", mandate.pk)
    return render(
        request,
        "epa/committee.html",
        {
            "mandate": mandate,
            "today": timezone.localdate(),
            "scopes": mandate.scopes.select_related("activity").order_by("activity__code"),
            "members": mandate.memberships.select_related("account").order_by("account__username"),
            "mandate_form": mandate_form
            if mandate.issued_at is None and actor.has_perm(CHANGE)
            else None,
            "scope_form": scope_form
            if mandate.issued_at is None and actor.has_perm(ADD_SCOPE)
            else None,
            "member_form": member_form
            if mandate.issued_at is None and actor.has_perm(ADD_MEMBER)
            else None,
            "may_remove_scope": mandate.issued_at is None and actor.has_perm(DELETE_SCOPE),
            "may_remove_member": mandate.issued_at is None and actor.has_perm(DELETE_MEMBER),
            "may_change": actor.has_perm(CHANGE),
            "error": error,
        },
        status=400 if request.method == "POST" else 200,
    )
