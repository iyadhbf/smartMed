"""Reusable role guards for function and class-based views."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import User


def role_required(*roles):
    """Allow the view only to authenticated users whose role is listed."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied("Vous n'avez pas accès à cet espace.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role not in self.allowed_roles:
            raise PermissionDenied("Vous n'avez pas accès à cet espace.")
        return super().dispatch(request, *args, **kwargs)


class PatientRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.PATIENT,)


class DoctorRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.DOCTOR,)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = (User.Role.ADMIN,)


patient_required = role_required(User.Role.PATIENT)
doctor_required = role_required(User.Role.DOCTOR)
admin_required = role_required(User.Role.ADMIN)
