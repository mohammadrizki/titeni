from django import forms

from apps.academics.models import CurriculumStage, StudyProgram
from apps.assessments.models import (
    AssessmentBlueprintVersion,
    BlueprintItem,
    BlueprintItemCompetency,
)
from apps.competencies.models import CompetencyFrameworkVersion


class BlueprintVersionForm(forms.ModelForm):
    class Meta:
        model = AssessmentBlueprintVersion
        fields = ["framework_version"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["framework_version"]
        assert isinstance(field, forms.ModelChoiceField)
        field.queryset = CompetencyFrameworkVersion.objects.filter(
            framework__program=program
        ).select_related("framework__program")


class BlueprintStageField(forms.ModelChoiceField):
    def label_from_instance(self, obj: CurriculumStage) -> str:
        return f"{obj.version} · {obj.code} · {obj.name}"


class BlueprintItemForm(forms.ModelForm):
    stage = BlueprintStageField(label="Tahap kurikulum", queryset=CurriculumStage.objects.none())

    class Meta:
        model = BlueprintItem
        fields = ["code", "name", "method", "purpose", "stage", "timing"]

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.version = version
        field = self.fields["stage"]
        assert isinstance(field, forms.ModelChoiceField)
        field.queryset = CurriculumStage.objects.filter(
            version__curriculum__program_id=version.blueprint.program_id
        ).select_related("version__curriculum")

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if self.instance.version.items.filter(code=code).exists():
            raise forms.ValidationError("Kode komponen sudah digunakan pada draf ini.")
        return code


class BlueprintMappingForm(forms.ModelForm):
    class Meta:
        model = BlueprintItemCompetency
        fields = ["item", "competency"]

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        competency = self.fields["competency"]
        assert isinstance(item, forms.ModelChoiceField)
        assert isinstance(competency, forms.ModelChoiceField)
        item.queryset = version.items.all()
        competency.queryset = version.framework_version.items.all()
