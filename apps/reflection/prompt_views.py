from typing import cast

from django import forms
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.access import (
    configurable_programs,
    has_program_permission,
    require_program_permission,
)
from apps.accounts.models import User

from .models import ReflectionPrompt


class PromptForm(forms.ModelForm):
    class Meta:
        model = ReflectionPrompt
        fields = ("text", "position", "is_active")


@require_http_methods(["GET", "POST"])
@login_required
def manage_prompts(
    request: HttpRequest, program_id: int, prompt_id: int | None = None
) -> HttpResponse:
    actor = cast(User, request.user)
    program = get_object_or_404(configurable_programs(actor), pk=program_id)
    require_program_permission(actor, program_id, "reflection.view_reflectionprompt")
    prompts = ReflectionPrompt.objects.filter(program=program)
    editing = None
    writing = request.method == "POST"
    action = "change" if prompt_id is not None else "add"
    can_write = has_program_permission(actor, program_id, f"reflection.{action}_reflectionprompt")
    if writing:
        require_program_permission(actor, program_id, f"reflection.{action}_reflectionprompt")
    with transaction.atomic():
        if prompt_id is not None:
            scoped = prompts.select_for_update() if writing else prompts
            editing = get_object_or_404(scoped, pk=prompt_id)
        form = PromptForm(request.POST if writing else None, instance=editing)
        if writing and form.is_valid():
            prompt = form.save(commit=False)
            prompt.program = program
            prompt.updated_by = actor
            try:
                with transaction.atomic():
                    prompt.save()
            except IntegrityError:
                if not prompts.filter(text=prompt.text).exclude(pk=prompt.pk).exists():
                    raise
                form.add_error("text", "Pemantik ini sudah ada di prodi.")
            else:
                return redirect("academics:reflection_prompts", program_id=program_id)
    return render(
        request,
        "reflection/prompts.html",
        {
            "program": program,
            "prompts": prompts,
            "editing": editing,
            "form": form,
            "can_write": can_write,
            "can_edit": has_program_permission(
                actor, program_id, "reflection.change_reflectionprompt"
            ),
        },
    )
