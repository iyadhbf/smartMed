from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from accounts.audit import log_event
from accounts.models import AuditLog
from accounts.permissions import (
    AdminRequiredMixin,
    DoctorRequiredMixin,
    admin_required,
)

from .forms import (
    AvailabilityExceptionForm,
    DoctorAdminForm,
    SpecialtyForm,
    WeeklyAvailabilityFormSet,
)
from .models import AvailabilityException, DoctorProfile, Specialty, WeeklyAvailability
from .services import generate_availability, rebuild_availability, upcoming_slots


@require_GET
def doctor_list(request):
    """Return active doctors for a bookable specialty: /api/doctors/?specialty=<id>."""

    raw_specialty = request.GET.get("specialty", "").strip()
    if not raw_specialty.isdigit():
        return JsonResponse({"doctors": []})

    doctors = (
        DoctorProfile.objects.filter(
            specialty_id=int(raw_specialty),
            specialty__is_active=True,
            specialty__is_bookable=True,
            is_active=True,
            user__is_active=True,
        )
        .select_related("user", "specialty")
        .order_by("display_order", "user__last_name", "user__first_name")
    )

    return JsonResponse(
        {
            "doctors": [
                {
                    "id": doctor.pk,
                    "name": doctor.display_name,
                    "specialty": doctor.specialty.name,
                    "photo": doctor.photo.url if doctor.photo else None,
                }
                for doctor in doctors
            ]
        }
    )


class DoctorDirectoryView(ListView):
    template_name = "doctors/directory.html"
    context_object_name = "doctors"
    paginate_by = 9

    def get_queryset(self):
        queryset = (
            DoctorProfile.objects.filter(
                is_active=True,
                user__is_active=True,
                specialty__is_active=True,
            )
            .select_related("user", "specialty")
            .order_by("display_order", "user__last_name", "user__first_name")
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
            )

        specialty = self.request.GET.get("specialty", "").strip()
        if specialty.isdigit():
            queryset = queryset.filter(specialty_id=int(specialty))
        elif specialty:
            queryset = queryset.filter(specialty__slug=specialty)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["specialties"] = Specialty.objects.filter(
            is_active=True, is_bookable=True
        ).order_by("display_order", "name")
        context["query"] = self.request.GET.get("q", "").strip()
        selected = self.request.GET.get("specialty", "").strip()
        context["selected_specialty"] = selected
        if selected.isdigit():
            context["selected_specialty_name"] = (
                Specialty.objects.filter(pk=int(selected)).values_list("name", flat=True).first()
            )
        elif selected:
            context["selected_specialty_name"] = (
                Specialty.objects.filter(slug=selected).values_list("name", flat=True).first()
            )
        context["result_count"] = context["paginator"].count if context["paginator"] else 0
        return context


class DoctorPublicDetailView(DetailView):
    template_name = "doctors/public_profile.html"
    context_object_name = "doctor"

    def get_queryset(self):
        return DoctorProfile.objects.filter(
            is_active=True,
            user__is_active=True,
            specialty__is_active=True,
        ).select_related("user", "specialty")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        days = upcoming_slots(self.object, days=14)
        for day in days:
            day["label"] = date_format(day["date"], "l j F Y").capitalize()
            day["short_label"] = date_format(day["date"], "D j M").capitalize()
        context["slot_days"] = days
        context["slot_count"] = sum(len(day["slots"]) for day in days)
        return context


class SpecialtyAdminListView(AdminRequiredMixin, ListView):
    template_name = "doctors/admin/specialty_list.html"
    context_object_name = "specialties"
    paginate_by = 12

    def get_queryset(self):
        queryset = Specialty.objects.annotate(doctor_count=Count("doctors")).order_by(
            "display_order", "name"
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(description__icontains=query))
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


class SpecialtyCreateView(AdminRequiredMixin, CreateView):
    model = Specialty
    form_class = SpecialtyForm
    template_name = "doctors/admin/specialty_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nouvelle spécialité"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_event(
            event=AuditLog.Event.SPECIALTY_CREATED,
            actor=self.request.user,
            request=self.request,
            description=self.object.name,
            metadata={"name": self.object.name, "icon": self.object.icon},
        )
        messages.success(self.request, f"La spécialité « {self.object.name} » a été créée.")
        return response

    def get_success_url(self):
        return reverse_lazy("specialty_admin_list")


class SpecialtyUpdateView(AdminRequiredMixin, UpdateView):
    model = Specialty
    form_class = SpecialtyForm
    template_name = "doctors/admin/specialty_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Modifier {self.object.name}"
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_event(
            event=AuditLog.Event.SPECIALTY_UPDATED,
            actor=self.request.user,
            request=self.request,
            description=self.object.name,
            metadata={
                "name": self.object.name,
                "is_bookable": self.object.is_bookable,
                "display_order": self.object.display_order,
            },
        )
        messages.success(self.request, f"La spécialité « {self.object.name} » a été mise à jour.")
        return response

    def get_success_url(self):
        return reverse_lazy("specialty_admin_list")


@admin_required
@require_POST
def specialty_toggle_status(request, pk):
    specialty = get_object_or_404(Specialty, pk=pk)
    specialty.is_active = not specialty.is_active
    specialty.save(update_fields=["is_active"])
    log_event(
        event=AuditLog.Event.SPECIALTY_STATUS_CHANGED,
        actor=request.user,
        request=request,
        description=specialty.name,
        metadata={"name": specialty.name, "is_active": specialty.is_active},
    )
    state = "réactivée" if specialty.is_active else "désactivée"
    messages.success(request, f"La spécialité « {specialty.name} » a été {state}.")
    return redirect("specialty_admin_list")


class DoctorAdminListView(AdminRequiredMixin, ListView):
    template_name = "doctors/admin/doctor_list.html"
    context_object_name = "doctors"
    paginate_by = 10

    def get_queryset(self):
        queryset = DoctorProfile.objects.select_related("user", "specialty").order_by(
            "user__last_name", "user__first_name"
        )
        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(professional_number__icontains=query)
            )
        specialty = self.request.GET.get("specialty", "").strip()
        if specialty.isdigit():
            queryset = queryset.filter(specialty_id=int(specialty))
        status = self.request.GET.get("status", "")
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "inactive":
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["specialties"] = Specialty.objects.order_by("display_order", "name")
        context["query"] = self.request.GET.get("q", "").strip()
        context["selected_specialty"] = self.request.GET.get("specialty", "").strip()
        context["status"] = self.request.GET.get("status", "")
        return context


class DoctorAdminUpdateView(AdminRequiredMixin, UpdateView):
    model = DoctorProfile
    form_class = DoctorAdminForm
    template_name = "doctors/admin/doctor_edit.html"

    def get_queryset(self):
        return DoctorProfile.objects.select_related("user", "specialty")

    def form_valid(self, form):
        previous_duration = (
            DoctorProfile.objects.only("consultation_duration")
            .get(pk=form.instance.pk)
            .consultation_duration
        )
        response = super().form_valid(form)
        if self.object.consultation_duration != previous_duration:
            rebuild_availability(self.object)
        log_event(
            event=AuditLog.Event.DOCTOR_UPDATED,
            actor=self.request.user,
            target=self.object.user,
            request=self.request,
            description=self.object.display_name,
            metadata={
                "professional_number": self.object.professional_number,
                "specialty": self.object.specialty.name,
                "consultation_duration": self.object.consultation_duration,
            },
        )
        messages.success(self.request, f"Le profil de {self.object.display_name} a été mis à jour.")
        return response

    def get_success_url(self):
        return reverse_lazy("doctor_admin_list")


@admin_required
@require_POST
def doctor_toggle_status(request, pk):
    doctor = get_object_or_404(DoctorProfile.objects.select_related("user"), pk=pk)
    doctor.is_active = not doctor.is_active
    doctor.user.is_active = doctor.is_active
    doctor.save(update_fields=["is_active"])
    doctor.user.save(update_fields=["is_active"])

    if doctor.is_active:
        generate_availability(doctor)
    else:
        doctor.slots.filter(date__gte=timezone.localdate()).delete()

    log_event(
        event=AuditLog.Event.DOCTOR_STATUS_CHANGED,
        actor=request.user,
        target=doctor.user,
        request=request,
        description=doctor.display_name,
        metadata={"is_active": doctor.is_active, "email": doctor.user.email},
    )
    state = "réactivé" if doctor.is_active else "désactivé"
    messages.success(request, f"Le compte de {doctor.display_name} a été {state}.")
    return redirect("doctor_admin_list")


class DoctorAvailabilityView(DoctorRequiredMixin, View):
    template_name = "doctors/availability.html"

    def get_profile(self):
        return get_object_or_404(
            DoctorProfile.objects.select_related("user", "specialty"),
            user=self.request.user,
        )

    def get_context(self, profile, formset=None, exception_form=None):
        today = timezone.localdate()
        return {
            "profile": profile,
            "formset": formset
            or WeeklyAvailabilityFormSet(
                queryset=WeeklyAvailability.objects.filter(doctor=profile).order_by(
                    "weekday", "start_time"
                ),
                doctor=profile,
            ),
            "exception_form": exception_form or AvailabilityExceptionForm(),
            "exceptions": AvailabilityException.objects.filter(
                doctor=profile, date__gte=today
            ).order_by("date", "start_time"),
            "slot_count": profile.slots.filter(date__gte=today).count(),
            "weekly_count": profile.weekly_hours.filter(is_active=True).count(),
        }

    def get(self, request, *args, **kwargs):
        profile = self.get_profile()
        return render(request, self.template_name, self.get_context(profile))

    def post(self, request, *args, **kwargs):
        profile = self.get_profile()
        action = request.POST.get("action", "hours")

        if action == "add_exception":
            exception_form = AvailabilityExceptionForm(request.POST)
            if exception_form.is_valid():
                exception = exception_form.save(commit=False)
                exception.doctor = profile
                exception.save()
                rebuild_availability(profile)
                log_event(
                    event=AuditLog.Event.AVAILABILITY_UPDATED,
                    actor=request.user,
                    target=request.user,
                    request=request,
                    description=f"Exception {exception.date:%d/%m/%Y}",
                    metadata={"action": "exception_added", "date": exception.date.isoformat()},
                )
                messages.success(request, "L'exception a été ajoutée et les créneaux mis à jour.")
                return redirect("doctor_availability")
            return render(
                request,
                self.template_name,
                self.get_context(profile, exception_form=exception_form),
            )

        if action == "delete_exception":
            exception = get_object_or_404(
                AvailabilityException, pk=request.POST.get("exception_id"), doctor=profile
            )
            description = f"Exception {exception.date:%d/%m/%Y}"
            exception.delete()
            rebuild_availability(profile)
            log_event(
                event=AuditLog.Event.AVAILABILITY_UPDATED,
                actor=request.user,
                target=request.user,
                request=request,
                description=description,
                metadata={"action": "exception_deleted"},
            )
            messages.success(request, "L'exception a été supprimée et les créneaux mis à jour.")
            return redirect("doctor_availability")

        formset = WeeklyAvailabilityFormSet(
            request.POST,
            queryset=WeeklyAvailability.objects.filter(doctor=profile).order_by(
                "weekday", "start_time"
            ),
            doctor=profile,
        )
        if formset.is_valid():
            for instance in formset.save(commit=False):
                instance.doctor = profile
                instance.save()
            for instance in formset.deleted_objects:
                instance.delete()
            rebuild_availability(profile)
            log_event(
                event=AuditLog.Event.AVAILABILITY_UPDATED,
                actor=request.user,
                target=request.user,
                request=request,
                description="Horaires hebdomadaires",
                metadata={"action": "weekly_hours_saved"},
            )
            messages.success(request, "Vos horaires ont été enregistrés et vos créneaux générés.")
            return redirect("doctor_availability")

        return render(
            request,
            self.template_name,
            self.get_context(profile, formset=formset),
        )
