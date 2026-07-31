from django import forms

from apps.accounts.forms import INPUT_CLASS

from .models import NDVIRecord

FILE_CLASS = (
    "block w-full text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 "
    "file:bg-brand-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-brand-700 "
    "hover:file:bg-brand-100"
)


class NDVIUploadForm(forms.ModelForm):
    class Meta:
        model = NDVIRecord
        fields = ("field", "captured_on", "source", "red_band", "nir_band", "rgb_image")
        widgets = {
            "field": forms.Select(attrs={"class": INPUT_CLASS}),
            "captured_on": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "source": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Sentinel-2 L2A"}),
            "red_band": forms.ClearableFileInput(attrs={"class": FILE_CLASS}),
            "nir_band": forms.ClearableFileInput(attrs={"class": FILE_CLASS}),
            "rgb_image": forms.ClearableFileInput(attrs={"class": FILE_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["captured_on"].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned = super().clean()
        red, nir, rgb = cleaned.get("red_band"), cleaned.get("nir_band"), cleaned.get("rgb_image")
        if not rgb and not (red and nir):
            raise forms.ValidationError(
                "Upload a red band together with a NIR band for true NDVI, "
                "or a single RGB image for a visible-band estimate."
            )
        if bool(red) != bool(nir) and not rgb:
            raise forms.ValidationError("NDVI needs both the red and the NIR band.")
        return cleaned
