from django import forms

from apps.academics.models import CurriculumStage, StudyProgram
from apps.assessments.models import (
    AssessmentBlueprintVersion,
    AssessmentSamplingRule,
    BlueprintItem,
    BlueprintItemCompetency,
    BlueprintItemEvidenceSource,
)
from apps.competencies.models import CompetencyFrameworkVersion, CompetencyIndicator
from apps.evidence.models import EvidenceSourceCapability


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


class BlueprintIndicatorField(forms.ModelChoiceField):
    def label_from_instance(self, obj: CompetencyIndicator) -> str:
        return f"{obj.item.code} · {obj}"


class BlueprintMappingForm(forms.ModelForm):
    indicator = BlueprintIndicatorField(
        label="Indikator kompetensi", queryset=CompetencyIndicator.objects.none(), required=False
    )

    class Meta:
        model = BlueprintItemCompetency
        fields = ["item", "competency", "indicator"]

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        competency = self.fields["competency"]
        assert isinstance(item, forms.ModelChoiceField)
        assert isinstance(competency, forms.ModelChoiceField)
        indicator = self.fields["indicator"]
        assert isinstance(indicator, forms.ModelChoiceField)
        indicator.queryset = CompetencyIndicator.objects.filter(
            item__version=version.framework_version
        ).select_related("item")
        item.queryset = version.items.all()
        competency.queryset = version.framework_version.items.all()


class SamplingRuleForm(forms.ModelForm):
    class Meta:
        model = AssessmentSamplingRule
        fields = ["item", "context", "minimum_observations"]

    def clean_minimum_observations(self) -> int:
        minimum = self.cleaned_data["minimum_observations"]
        if minimum < 1:
            raise forms.ValidationError("Jumlah minimum observasi harus lebih dari nol.")
        return minimum

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        assert isinstance(item, forms.ModelChoiceField)
        item.queryset = version.items.all()


class BlueprintEvidenceSourceForm(forms.ModelForm):
    class Meta:
        model = BlueprintItemEvidenceSource
        fields = ["item", "capability"]

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        capability = self.fields["capability"]
        assert isinstance(item, forms.ModelChoiceField)
        assert isinstance(capability, forms.ModelChoiceField)
        item.queryset = version.items.all()
        capability.queryset = EvidenceSourceCapability.objects.filter(
            source__program_id=version.blueprint.program_id,
            evidence_type__program_id=version.blueprint.program_id,
        ).select_related("source", "evidence_type")
