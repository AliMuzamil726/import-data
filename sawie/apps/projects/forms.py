from django import forms

from apps.accounts.forms import INPUT_CLASS

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            "name", "code", "status", "location", "lead",
            "start_date", "end_date", "budget", "description",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Regenerative cotton cluster"}),
            "code": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "RCC-2026"}),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
            "location": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Faisalabad district"}),
            "lead": forms.Select(attrs={"class": INPUT_CLASS}),
            "start_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"),
            "budget": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "description": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("start_date", "end_date"):
            self.fields[name].input_formats = ["%Y-%m-%d"]
        self.fields["lead"].required = False

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        return cleaned
