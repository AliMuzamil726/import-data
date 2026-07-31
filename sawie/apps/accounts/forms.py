"""Authentication and user-administration forms."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Role, User

INPUT_CLASS = (
    "w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 "
    "placeholder-slate-400 shadow-sm transition focus:border-brand-500 focus:outline-none "
    "focus:ring-2 focus:ring-brand-500/20"
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={"autofocus": True, "autocomplete": "username", "placeholder": "you@sawie.io"}
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"autocomplete": "current-password", "placeholder": "••••••••",
                   "x-bind:type": "show ? 'text' : 'password'"}
        )
    )
    remember_me = forms.BooleanField(required=False, initial=True)

    error_messages = {
        "invalid_login": "That username and password do not match an account.",
        "inactive": "This account has been deactivated. Contact your administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field_class = (
            "w-full rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-white "
            "placeholder-white/40 backdrop-blur transition focus:border-accent-400 "
            "focus:outline-none focus:ring-2 focus:ring-accent-400/30"
        )
        for name in ("username", "password"):
            self.fields[name].widget.attrs["class"] = field_class


class UserForm(forms.ModelForm):
    """Create or edit a platform user (Super Admin only)."""

    password1 = forms.CharField(
        label="Password", required=False, widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
        help_text="Leave blank when editing to keep the current password.",
    )
    password2 = forms.CharField(
        label="Confirm password", required=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
    )

    class Meta:
        model = User
        fields = (
            "username", "first_name", "last_name", "email", "phone",
            "role", "designation", "district", "avatar", "is_active",
        )
        widgets = {
            "username": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "+92 300 0000000"}),
            "role": forms.Select(attrs={"class": INPUT_CLASS}),
            "designation": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "district": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "avatar": forms.ClearableFileInput(attrs={"class": "text-sm text-slate-600"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 rounded border-slate-300 text-brand-600"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "The two password fields do not match.")
            elif len(p1) < 8:
                self.add_error("password1", "Use at least 8 characters.")
        elif self.instance.pk is None:
            self.add_error("password1", "Set a password for the new user.")
        return cleaned

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "designation", "district", "avatar")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "last_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "designation": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "district": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "avatar": forms.ClearableFileInput(attrs={"class": "text-sm text-slate-600"}),
        }


ROLE_CHOICES = Role.choices
