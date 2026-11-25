from django import forms

from apps.academics.models import StudyProgram
from apps.assessments.models import AssessmentBlueprintVersion
from apps.competencies.models import CompetencyItem
from apps.evidence.models import (
    EvidenceRequirementTemplate,
    EvidenceSource,
    EvidenceSourceCapability,
    EvidenceSourceCompetency,
    EvidenceType,
)


class SourceForm(forms.ModelForm):
    class Meta:
        model = EvidenceSource
        fields = ["code", "name", "acquisition", "verification"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.program = program

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if EvidenceSource.objects.filter(program=self.instance.program, code=code).exists():
            raise forms.ValidationError("Kode sumber sudah digunakan pada prodi ini.")
        return code


class EvidenceTypeForm(forms.ModelForm):
    class Meta:
        model = EvidenceType
        fields = ["code", "name"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.program = program

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if EvidenceType.objects.filter(program=self.instance.program, code=code).exists():
            raise forms.ValidationError("Kode jenis sudah digunakan pada prodi ini.")
        return code


class CapabilityForm(forms.ModelForm):
    class Meta:
        model = EvidenceSourceCapability
        fields = ["source", "evidence_type"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        source = self.fields["source"]
        evidence_type = self.fields["evidence_type"]
        assert isinstance(source, forms.ModelChoiceField)
        assert isinstance(evidence_type, forms.ModelChoiceField)
        source.queryset = EvidenceSource.objects.filter(program=program)
        evidence_type.queryset = EvidenceType.objects.filter(program=program)


class CompetencyChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: CompetencyItem) -> str:
        return f"Draf versi {obj.version.number} · {obj}"


class SourceCompetencyForm(forms.ModelForm):
    competency = CompetencyChoiceField(
        label="Butir kompetensi", queryset=CompetencyItem.objects.none()
    )

    class Meta:
        model = EvidenceSourceCompetency
        fields = ["source", "competency"]

    def __init__(self, *args, program: StudyProgram, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        source = self.fields["source"]
        competency = self.fields["competency"]
        assert isinstance(source, forms.ModelChoiceField)
        assert isinstance(competency, forms.ModelChoiceField)
        source.queryset = EvidenceSource.objects.filter(program=program)
        competency.queryset = (
            CompetencyItem.objects.filter(version__framework__program=program)
            .select_related("version")
            .order_by("-version__number", "code")
        )


class EvidenceRequirementForm(forms.ModelForm):
    class Meta:
        model = EvidenceRequirementTemplate
        fields = ["code", "name", "competency", "capability", "minimum_count", "context"]

    def __init__(self, *args, version: AssessmentBlueprintVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.blueprint_version = version
        competency = self.fields["competency"]
        capability = self.fields["capability"]
        assert isinstance(competency, forms.ModelChoiceField)
        assert isinstance(capability, forms.ModelChoiceField)
        competency.queryset = version.framework_version.items.all()
        program_id = version.blueprint.program_id
        capability.queryset = EvidenceSourceCapability.objects.filter(
            source__program_id=program_id, evidence_type__program_id=program_id
        ).select_related("source", "evidence_type")

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if self.instance.blueprint_version.manual_evidence_requirements.filter(code=code).exists():
            raise forms.ValidationError("Kode persyaratan sudah digunakan pada draf ini.")
        return code
