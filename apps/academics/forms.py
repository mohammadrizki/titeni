from datetime import date

from django import forms

from apps.academics.models import AcademicPeriod, Institution, StudyProgram


class InstitutionForm(forms.ModelForm):
    class Meta:
        model = Institution
        fields = ["name"]


class StudyProgramForm(forms.ModelForm):
    class Meta:
        model = StudyProgram
        fields = ["code", "name", "education_stage"]


class AcademicPeriodForm(forms.ModelForm):
    class Meta:
        model = AcademicPeriod
        fields = ["code", "name", "starts_on", "ends_on"]
        widgets = {
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        start, end = cleaned.get("starts_on"), cleaned.get("ends_on")
        if isinstance(start, date) and isinstance(end, date) and end < start:
            self.add_error("ends_on", "Tanggal selesai harus sama atau setelah tanggal mulai.")
        return cleaned
