from django import forms

from apps.accounts.forms import INPUT_CLASS

from .models import Farmer


class FarmerForm(forms.ModelForm):
    class Meta:
        model = Farmer
        fields = (
            "full_name", "father_name", "cnic", "phone", "email", "address", "village",
            "city", "district", "province", "profile_image", "total_land_acres",
            "registration_date", "status", "portal_user", "notes",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Muhammad Aslam"}),
            "father_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "cnic": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "35202-1234567-1"}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+92 300 1234567"}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "address": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "village": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Chak 45 GB"}),
            "city": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Faisalabad"}),
            "district": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "province": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "profile_image": forms.ClearableFileInput(attrs={"class": "text-sm text-slate-600"}),
            "total_land_acres": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "registration_date": forms.DateInput(
                attrs={"class": INPUT_CLASS, "type": "date"}, format="%Y-%m-%d"
            ),
            "status": forms.Select(attrs={"class": INPUT_CLASS}),
            "portal_user": forms.Select(attrs={"class": INPUT_CLASS}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["registration_date"].input_formats = ["%Y-%m-%d"]
        self.fields["portal_user"].required = False
        self.fields["portal_user"].queryset = self.fields["portal_user"].queryset.filter(
            role="farmer", is_active=True
        )
