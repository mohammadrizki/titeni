from django import forms

from apps.academics.models import CurriculumStage
from apps.accounts.models import User
from apps.competencies.models import (
    CompetencyFrameworkVersion,
    CompetencyIndicator,
    CompetencyItem,
    CompetencyMilestone,
    CompetencyRelationship,
    PerformanceStandard,
    PerformanceStandardVersion,
)


class ItemForm(forms.ModelForm):
    class Meta:
        model = CompetencyItem
        fields = ["code", "name", "parent"]

    def __init__(self, *args, version: CompetencyFrameworkVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.version = version
        parent = self.fields["parent"]
        assert isinstance(parent, forms.ModelChoiceField)
        parent.queryset = version.items.all()

    def clean_code(self) -> str:
        code = self.cleaned_data["code"]
        if self.instance.version.items.filter(code=code).exists():
            raise forms.ValidationError("Kode butir sudah digunakan di versi ini.")
        return code


class StageChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: CurriculumStage) -> str:
        return f"{obj.version} · {obj.code} · {obj.name}"


class MilestoneForm(forms.ModelForm):
    stage = StageChoiceField(label="Tahap kurikulum", queryset=CurriculumStage.objects.none())

    class Meta:
        model = CompetencyMilestone
        fields = ["item", "stage", "expectation"]

    def __init__(self, *args, version: CompetencyFrameworkVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        stage = self.fields["stage"]
        assert isinstance(item, forms.ModelChoiceField)
        assert isinstance(stage, forms.ModelChoiceField)
        item.queryset = version.items.all()
        stage.queryset = CurriculumStage.objects.filter(
            version__curriculum__program_id=version.framework.program_id
        ).select_related("version__curriculum")


class IndicatorForm(forms.ModelForm):
    class Meta:
        model = CompetencyIndicator
        fields = ["item", "code", "description"]

    def __init__(self, *args, version: CompetencyFrameworkVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        assert isinstance(item, forms.ModelChoiceField)
        item.queryset = version.items.all()


class RelationshipForm(forms.ModelForm):
    class Meta:
        model = CompetencyRelationship
        fields = ["source", "target", "description"]

    def __init__(self, *args, version: CompetencyFrameworkVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for name in ("source", "target"):
            field = self.fields[name]
            assert isinstance(field, forms.ModelChoiceField)
            field.queryset = version.items.all()


class StandardForm(forms.Form):
    item = forms.ModelChoiceField(label="Butir", queryset=CompetencyItem.objects.none())
    code = forms.SlugField(label="Kode standar", max_length=40)
    description = forms.CharField(label="Deskripsi standar performa", max_length=400)

    def __init__(self, *args, version: CompetencyFrameworkVersion, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        item = self.fields["item"]
        assert isinstance(item, forms.ModelChoiceField)
        item.queryset = version.items.all()

    def create_version(self, actor: User) -> PerformanceStandardVersion:
        # The view holds the framework draft lock for the entire write.
        standard, _ = PerformanceStandard.objects.get_or_create(
            item=self.cleaned_data["item"], code=self.cleaned_data["code"]
        )
        latest = standard.versions.first()
        return standard.versions.create(
            number=latest.number + 1 if latest else 1,
            description=self.cleaned_data["description"],
            created_by=actor,
        )
