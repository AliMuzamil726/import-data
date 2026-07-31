from django import forms

from apps.accounts.forms import INPUT_CLASS

from .models import Crop


class CropForm(forms.ModelForm):
    class Meta:
        model = Crop
        fields = (
            "name", "variety", "category", "season", "field", "planting_date",
            "expected_harvest_date", "actual_harvest_date", "area_acres",
            "production_tonnes", "price_per_tonne", "status", "notes",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Cotton"}),
            "variety": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "FH-490"}),
            "category": forms.Select(attrs={"class": INPUT_CLASS}),
            "season": forms.Select(attrs={"class": INPUT_CLASS}),
            "field": forms.Select(attrs={"class": INPUT_CLASS}),
            "planting_date": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "expected_harvest_date": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "actual_harvest_date": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "area_acres": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "production_tonnes": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.001"}),
            "price_per_tonne": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("planting_date", "expected_harvest_date", "actual_harvest_date"):
            self.fields[name].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned = super().clean()
        planted = cleaned.get("planting_date")
        expected = cleaned.get("expected_harvest_date")
        actual = cleaned.get("actual_harvest_date")
        if planted and expected and expected < planted:
            self.add_error("expected_harvest_date", "Harvest cannot be before planting.")
        if planted and actual and actual < planted:
            self.add_error("actual_harvest_date", "Harvest cannot be before planting.")
        if cleaned.get("status") == "harvested" and not actual:
            self.add_error("actual_harvest_date", "Set the harvest date for a harvested crop.")
        field = cleaned.get("field")
        area = cleaned.get("area_acres")
        if field and area and area > field.area_acres:
            self.add_error(
                "area_acres",
                f"{field.name} is only {field.area_acres} acres.",
            )
        return cleaned
