from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import FormView, ListView, TemplateView

from appointments.models import Appointment
from appointments.services import OPEN_STATUSES
from doctors.models import DoctorProfile, Specialty
from patients.models import PatientProfile

from .audit import log_event
from .forms import (
    BaseProfileForm,
    DoctorCreateForm,
    DoctorProfileForm,
    EmailAuthenticationForm,
    PatientProfileForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
)
from .models import AuditLog, User
from .permissions import (
    AdminRequiredMixin,
    DoctorRequiredMixin,
    PatientRequiredMixin,
    admin_required,
)


def dashboard_url_name(user):
    if user.is_admin_role:
        return "admin_dashboard"
    if user.is_doctor:
        return "doctor_dashboard"
    return "patient_dashboard"


class EmailLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        redirect_to = self.get_redirect_url()
        if redirect_to:
            return redirect_to
        return reverse(dashboard_url_name(self.request.user))


class UserLogoutView(LogoutView):
    next_page = "home"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Vous avez été déconnecté.")
        return response


class RegisterView(FormView):
    template_name = "accounts/register.html"
    form_class = RegistrationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(dashboard_url_name(request.user))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def get_success_url(self):
        candidate = self.request.POST.get("next") or self.request.GET.get("next")
        if candidate and url_has_allowed_host_and_scheme(
            candidate,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return candidate
        return reverse("patient_dashboard")

    def form_valid(self, form):
        user = form.save()
        auth_login(
            self.request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        messages.success(
            self.request,
            "Votre compte patient a été créé. Bienvenue sur SmartMed AI !",
        )
        return redirect(self.get_success_url())


class AuditedPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/emails/password_reset_email.txt"
    subject_template_name = "accounts/emails/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")

    def form_valid(self, form):
        email = form.cleaned_data["email"].strip().lower()
        target = User.objects.filter(email__iexact=email).first()
        response = super().form_valid(form)
        log_event(
            event=AuditLog.Event.PASSWORD_RESET_REQUESTED,
            target=target,
            request=self.request,
            description=email,
            metadata={"email": email},
        )
        return response


class AuditedPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.user
        log_event(
            event=AuditLog.Event.PASSWORD_RESET_COMPLETED,
            actor=user,
            target=user,
            request=self.request,
        )
        return response


class PasswordResetSentView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetFinishedView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class AuditedPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        response = super().form_valid(form)
        log_event(
            event=AuditLog.Event.PASSWORD_CHANGED,
            actor=self.request.user,
            target=self.request.user,
            request=self.request,
        )
        messages.success(self.request, "Votre mot de passe a été modifié.")
        return response


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get_form(self, data=None):
        user = self.request.user
        if user.is_patient:
            profile, _ = PatientProfile.objects.get_or_create(user=user)
            return PatientProfileForm(data, user=user, profile=profile), profile
        if user.is_doctor:
            profile = getattr(user, "doctor_profile", None)
            return DoctorProfileForm(data, user=user, profile=profile), profile
        return BaseProfileForm(data, user=user), None

    def get(self, request, *args, **kwargs):
        form, profile = self.get_form()
        return render(
            request,
            self.template_name,
            {"form": form, "profile": profile},
        )

    def post(self, request, *args, **kwargs):
        form, profile = self.get_form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour.")
            return redirect("accounts:profile")
        return render(
            request,
            self.template_name,
            {"form": form, "profile": profile},
        )


class PatientDashboardView(PatientRequiredMixin, TemplateView):
    template_name = "accounts/patient_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        context["profile"] = profile
        context["upcoming_appointments"] = (
            Appointment.objects.filter(
                patient=self.request.user,
                status__in=OPEN_STATUSES,
                date__gte=timezone.localdate(),
            )
            .select_related("doctor", "doctor__user", "doctor__specialty")
            .order_by("date", "start_time")[:3]
        )
        return context


class DoctorDashboardView(DoctorRequiredMixin, TemplateView):
    template_name = "accounts/doctor_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "doctor_profile", None)
        context["profile"] = profile
        if profile is not None:
            context["weekly_hours"] = profile.weekly_hours.filter(is_active=True).order_by(
                "weekday", "start_time"
            )
            context["slot_count"] = profile.slots.filter(date__gte=timezone.localdate()).count()
            today = timezone.localdate()
            todays = Appointment.objects.filter(
                doctor=profile, status__in=OPEN_STATUSES, date=today
            )
            context["today_count"] = todays.count()
            context["pending_count"] = todays.filter(status=Appointment.Status.PENDING).count()
        else:
            context["weekly_hours"] = []
            context["slot_count"] = 0
            context["today_count"] = 0
            context["pending_count"] = 0
        return context


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    template_name = "accounts/admin_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["patient_count"] = User.objects.filter(role=User.Role.PATIENT).count()
        context["doctor_count"] = DoctorProfile.objects.filter(
            is_active=True, user__is_active=True
        ).count()
        context["specialty_count"] = Specialty.objects.filter(is_active=True).count()
        context["audit_events"] = AuditLog.objects.select_related("actor")[:8]
        context["audit_count"] = AuditLog.objects.count()
        return context


class DoctorCreateView(AdminRequiredMixin, FormView):
    template_name = "accounts/doctor_form.html"
    form_class = DoctorCreateForm
    success_url = reverse_lazy("admin_dashboard")

    def form_valid(self, form):
        doctor = form.save()
        log_event(
            event=AuditLog.Event.DOCTOR_ACCOUNT_CREATED,
            actor=self.request.user,
            target=doctor,
            request=self.request,
            metadata={
                "email": doctor.email,
                "professional_number": doctor.doctor_profile.professional_number,
                "specialty": doctor.doctor_profile.specialty.name,
            },
        )
        messages.success(
            self.request,
            f"Le compte du Dr {doctor.full_name} a été créé avec succès.",
        )
        return redirect(self.get_success_url())


def lockout_view(request, original_response=None, credentials=None):
    submitted = request.POST.get("username") or (credentials or {}).get("username") or ""
    attempted_email = submitted[:254]
    target = User.objects.filter(email__iexact=attempted_email).first() if attempted_email else None
    log_event(
        event=AuditLog.Event.LOGIN_LOCKED_OUT,
        target=target,
        request=request,
        description=attempted_email,
        metadata={"email": attempted_email},
    )
    response = render(request, "accounts/lockout.html", status=429)
    response["Retry-After"] = "900"
    return response


class PatientAdminListView(AdminRequiredMixin, ListView):
    """Admin list of patient accounts — contact details only, never medical data."""

    template_name = "accounts/admin/patient_list.html"
    context_object_name = "patients"
    paginate_by = 12

    def get_queryset(self):
        queryset = User.objects.filter(role=User.Role.PATIENT).order_by("last_name", "first_name")
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
            )
        status = self.request.GET.get("status", "")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.request.GET.get("q", "").strip()
        context["status"] = self.request.GET.get("status", "")
        return context


@admin_required
@require_POST
def patient_toggle_status(request, pk):
    patient = get_object_or_404(User, pk=pk, role=User.Role.PATIENT)
    patient.is_active = not patient.is_active
    patient.save(update_fields=["is_active"])
    log_event(
        event=AuditLog.Event.PATIENT_STATUS_CHANGED,
        actor=request.user,
        target=patient,
        request=request,
        description=patient.full_name,
        metadata={"email": patient.email, "is_active": patient.is_active},
    )
    state = "réactivé" if patient.is_active else "désactivé"
    messages.success(request, f"Le compte de {patient.full_name} a été {state}.")
    return redirect("patient_admin_list")
