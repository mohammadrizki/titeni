from typing import cast

from django import forms

from apps.academics.models import StudyProgram
from apps.competencies.models import CompetencyFrameworkVersion, CompetencyItem

from .models import (
    EntrustableProfessionalActivity,
    EPACompetencyLink,
    EPAVersion,
    SupervisionLevel,
    SupervisionScale,
    SupervisionScaleVersion,
)


class ActivityForm(forms.ModelForm):
    class Meta:
        model = EntrustableProfessionalActivity
        fields = ("code",)

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if EntrustableProfessionalActivity.objects.filter(
            program=self.instance.program, code=code
        ).exists():
            raise forms.ValidationError("Kode EPA sudah digunakan.")
        return code


class ScaleForm(forms.ModelForm):
    class Meta:
        model = SupervisionScale
        fields = ("code",)

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if SupervisionScale.objects.filter(program=self.instance.program, code=code).exists():
            raise forms.ValidationError("Kode skala sudah digunakan.")
        return code


class ActivityVersionForm(forms.ModelForm):
    class Meta:
        model = EPAVersion
        fields = ("title", "description", "practice_scope", "limitations", "framework", "scale")

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(
            forms.ModelChoiceField, self.fields["framework"]
        ).queryset = CompetencyFrameworkVersion.objects.filter(
            framework__program=program
        ).select_related("framework__program")
        cast(forms.ModelChoiceField, self.fields["scale"]).queryset = (
            SupervisionScaleVersion.objects.filter(scale__program=program)
            .select_related("scale")
            .order_by("scale__code", "-number")
        )


class ScaleVersionForm(forms.ModelForm):
    class Meta:
        model = SupervisionScaleVersion
        fields = ("name",)


class LevelForm(forms.ModelForm):
    position = forms.IntegerField(label="Urutan", min_value=1, max_value=2147483647)

    class Meta:
        model = SupervisionLevel
        fields = ("position", "label", "description")

    def clean_position(self) -> int:
        position = self.cleaned_data["position"]
        if self.instance.version.levels.filter(position=position).exists():
            raise forms.ValidationError("Urutan sudah digunakan dalam versi ini.")
        return position


class CompetencyForm(forms.ModelForm):
    class Meta:
        model = EPACompetencyLink
        fields = ("item", "kind")

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        cast(forms.ModelChoiceField, self.fields["item"]).queryset = CompetencyItem.objects.filter(
            version_id=self.instance.version.framework_id
        )

    def clean_item(self) -> CompetencyItem:
        item = self.cleaned_data["item"]
        if self.instance.version.competencies.filter(item=item).exists():
            raise forms.ValidationError("Kompetensi sudah dipetakan dalam versi ini.")
        return item
