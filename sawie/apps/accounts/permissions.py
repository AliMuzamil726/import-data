"""Reusable access-control helpers."""
from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class ModuleRequiredMixin(LoginRequiredMixin):
    """Class-based view guard. Set `required_module` on the view."""

    required_module: str = ""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.required_module:
            if not request.user.can_access(self.required_module):
                raise PermissionDenied("Your role does not have access to this module.")
        return super().dispatch(request, *args, **kwargs)


class WriteAccessMixin(ModuleRequiredMixin):
    """Guard for create/update views."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.can_edit_records:
            raise PermissionDenied("Your role is read-only for this record type.")
        return super().dispatch(request, *args, **kwargs)


class DeleteAccessMixin(ModuleRequiredMixin):
    """Guard for delete views."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.can_delete_records:
            raise PermissionDenied("Your role cannot delete records.")
        return super().dispatch(request, *args, **kwargs)


def module_required(module: str):
    """Function-view decorator equivalent of ModuleRequiredMixin."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if not request.user.can_access(module):
                raise PermissionDenied("Your role does not have access to this module.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
