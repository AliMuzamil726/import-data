"""Authentication and user-administration views."""
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import LoginForm, ProfileForm, UserForm
from .models import Role, User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)
        self.request.user.touch()
        return response


class LogoutView(auth_views.LogoutView):
    http_method_names = ["post", "options"]


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"

    def get_success_url(self):
        return reverse("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"

    def get_success_url(self):
        return reverse("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


def _require_user_admin(request) -> None:
    if not request.user.can_access("users"):
        raise PermissionDenied("Only a Super Admin can manage platform users.")


@login_required
def user_list(request):
    _require_user_admin(request)
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    users = User.objects.all()
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role:
        users = users.filter(role=role)

    page = Paginator(users, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/user_list.html",
        {"page_obj": page, "query": query, "role": role, "roles": Role.choices,
         "active_module": "users"},
    )


@login_required
def user_create(request):
    _require_user_admin(request)
    form = UserForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Created the account for {user.display_name}.")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html",
        {"form": form, "title": "Add user", "active_module": "users"},
    )


@login_required
def user_update(request, pk: int):
    _require_user_admin(request)
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, request.FILES or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated {user.display_name}.")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_form.html",
        {"form": form, "title": f"Edit {user.display_name}", "object": user,
         "active_module": "users"},
    )


@login_required
def user_delete(request, pk: int):
    _require_user_admin(request)
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("accounts:user_list")
    if request.method == "POST":
        user.is_active = False
        user.save(update_fields=["is_active"])
        messages.success(request, f"Deactivated {user.display_name}.")
        return redirect("accounts:user_list")
    return render(
        request, "accounts/user_confirm_delete.html",
        {"object": user, "active_module": "users"},
    )


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "active_module": ""})
