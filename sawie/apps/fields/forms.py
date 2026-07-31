import json

from django import forms

from apps.accounts.forms import INPUT_CLASS

from .models import FarmActivity, Field


class FieldForm(forms.ModelForm):
    boundary_geojson = forms.CharField(
        required=False, widget=forms.HiddenInput(attrs={"x-ref": "boundary"}),
        help_text="Filled in by the map when you draw a polygon.",
    )

    class Meta:
        model = Field
        fields = (
            "name", "code", "farmer", "latitude", "longitude", "area_acres",
            "soil_type", "irrigation_type", "status", "officer", "notes",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "North block"}),
            "code": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "FSD-001-A"}),
            "farmer": forms.Select(attrs={"class": INPUT_CLASS}),
            "latitude": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "step": "0.000001", "x-ref": "lat"}
            ),
            "longitude": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "step": "0.000001", "x-ref": "lng"}
            ),
            "area_acres": forms.NumberInput(
                attrs={"class": INPUT_CLASS, "step": "0.01", "x-ref": "area"}
            ),
            "soil_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "irrigation_type": forms.Select(attrs={"class": INPUT_CLASS}),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
            "officer": forms.Select(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["officer"].required = False
        if self.instance.pk and self.instance.boundary:
            self.fields["boundary_geojson"].initial = json.dumps(self.instance.boundary)

    def clean_boundary_geojson(self):
        raw = (self.cleaned_data.get("boundary_geojson") or "").strip()
        if not raw:
            return None
        try:
            geometry = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("The drawn boundary could not be read.") from exc
        if geometry.get("type") != "Polygon":
            raise forms.ValidationError("Draw a closed polygon around the plot.")
        return geometry

    def save(self, commit: bool = True):
        field = super().save(commit=False)
        field.boundary = self.cleaned_data.get("boundary_geojson")
        if commit:
            field.save()
        return field


class ActivityForm(forms.ModelForm):
    class Meta:
        model = FarmActivity
        fields = ("kind", "performed_on", "crop", "detail", "quantity", "unit", "cost")
        widgets = {
            "kind": forms.Select(attrs={"class": INPUT_CLASS}),
            "performed_on": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "crop": forms.Select(attrs={"class": INPUT_CLASS}),
            "detail": forms.TextInput(
                attrs={"class": INPUT_CLASS, "placeholder": "Urea top dressing"}
            ),
            "quantity": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "unit": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "kg"}),
            "cost": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
        }

    def __init__(self, *args, field=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["performed_on"].input_formats = ["%Y-%m-%d"]
        self.fields["crop"].required = False
        if field is not None:
            self.fields["crop"].queryset = field.crops.all()
