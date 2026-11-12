from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from accounts.permissions import (
    DoctorRequiredMixin,
    PatientRequiredMixin,
    patient_required,
)
from doctors.models import Availability, DoctorProfile, Specialty
from doctors.services import generate_availability

from .models import Appointment
from .services import (
    CANCELLATION_LEAD,
    OPEN_STATUSES,
    book_slot,
    cancel_appointment,
    reschedule_appointment,
    set_doctor_status,
)

BOOKING_HORIZON_DAYS = 14


def _bookable_specialties():
    return Specialty.objects.filter(is_active=True, is_bookable=True).order_by(
        "display_order", "name"
    )


def _free_slot_days(doctor, days=BOOKING_HORIZON_DAYS):
    """Group this doctor's still-free slots by day for the next `days` days."""

    generate_availability(doctor, days=days)
    today = timezone.localdate()
    limit = today + timedelta(days=days - 1)
    booked_ids = Appointment.objects.filter(
        doctor=doctor, status__in=OPEN_STATUSES, slot__date__range=(today, limit)
    ).values_list("slot_id", flat=True)

    grouped = []
    current_date = None
    slots = (
        doctor.slots.filter(date__range=(today, limit))
        .exclude(pk__in=booked_ids)
        .order_by("date", "start_time")
    )
    for slot in slots:
        if slot.date != current_date:
            current_date = slot.date
            grouped.append(
                {
                    "date": slot.date,
                    "label": date_format(slot.date, "l j F Y").capitalize(),
                    "short_label": date_format(slot.date, "D j M").capitalize(),
                    "slots": [],
                }
            )
        grouped[-1]["slots"].append(slot)
    return grouped


def _patient_can_change(appointment):
    return (
        appointment.is_open
        and appointment.slot_id is not None
        and appointment.starts_at - timezone.localtime() >= CANCELLATION_LEAD
    )


@patient_required
def book_entry(request):
    """Two-step booking: pick a doctor, then pick a slot and confirm."""

    if request.method == "POST":
        return _book_slot(request)

    raw_specialty = request.GET.get("specialty", "").strip()
    raw_doctor = request.GET.get("doctor", "").strip()
    raw_date = request.GET.get("date", "").strip()

    specialty = None
    if raw_specialty.isdigit():
        specialty = Specialty.objects.filter(
            pk=int(raw_specialty), is_active=True, is_bookable=True
        ).first()

    doctor = None
    if raw_doctor.isdigit():
        doctor = (
            DoctorProfile.objects.filter(
                pk=int(raw_doctor),
                is_active=True,
                user__is_active=True,
                specialty__is_active=True,
                specialty__is_bookable=True,
            )
            .select_related("user", "specialty")
            .first()
        )

    if doctor is not None:
        slot_days = _free_slot_days(doctor)
        wanted = None
        try:
            wanted = timezone.datetime.fromisoformat(raw_date).date() if raw_date else None
        except ValueError:
            wanted = None
        return render(
            request,
            "appointments/book.html",
            {
                "step": "slots",
                "doctor": doctor,
                "slot_days": slot_days,
                "slot_count": sum(len(day["slots"]) for day in slot_days),
                "wanted_date": wanted,
            },
        )

    return render(
        request,
        "appointments/book.html",
        {
            "step": "choose",
            "specialties": _bookable_specialties(),
            "selected_specialty": specialty.pk if specialty else "",
            "wanted_date": raw_date,
        },
    )


def _book_slot(request):
    raw_slot = request.POST.get("slot_id", "").strip()
    slot = (
        Availability.objects.select_related("doctor", "doctor__user")
        .filter(pk=int(raw_slot) if raw_slot.isdigit() else 0)
        .first()
    )
    try:
        book_slot(
            patient=request.user,
            slot=slot,
            reason=request.POST.get("reason", ""),
            actor=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
        doctor_id = request.POST.get("doctor", "") or (slot.doctor_id if slot else "")
        params = f"?doctor={doctor_id}" if str(doctor_id).isdigit() else ""
        return redirect(reverse("appointments:book_entry") + params)

    messages.success(
        request,
        "Votre demande de rendez-vous a été enregistrée. Le médecin va la confirmer.",
    )
    return redirect("appointments:appointment_list")


class AppointmentListView(PatientRequiredMixin, ListView):
    template_name = "appointments/appointment_list.html"
    context_object_name = "past_appointments"
    paginate_by = 8

    def get_queryset(self):
        today = timezone.localdate()
        return (
            Appointment.objects.filter(patient=self.request.user)
            .filter(Q(date__lt=today) | ~Q(status__in=OPEN_STATUSES))
            .select_related("doctor", "doctor__user", "doctor__specialty")
            .order_by("-date", "-start_time")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        upcoming = (
            Appointment.objects.filter(patient=self.request.user)
            .filter(status__in=OPEN_STATUSES, date__gte=today)
            .select_related("doctor", "doctor__user", "doctor__specialty")
            .order_by("date", "start_time")
        )
        context["upcoming_appointments"] = upcoming
        context["changeable_ids"] = {
            appointment.pk for appointment in upcoming if _patient_can_change(appointment)
        }
        return context


@patient_required
@require_POST
def appointment_cancel(request, pk):
    appointment = get_object_or_404(Appointment, pk=pk, patient=request.user)
    try:
        cancel_appointment(
            appointment=appointment,
            actor=request.user,
            cancelled_by="patient",
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Votre rendez-vous a été annulé.")
    return redirect("appointments:appointment_list")


@patient_required
def appointment_reschedule(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("doctor", "doctor__user", "doctor__specialty"),
        pk=pk,
        patient=request.user,
    )

    if request.method == "POST":
        raw_slot = request.POST.get("slot_id", "").strip()
        new_slot = (
            Availability.objects.select_related("doctor")
            .filter(pk=int(raw_slot) if raw_slot.isdigit() else 0)
            .first()
        )
        try:
            reschedule_appointment(
                patient=request.user,
                appointment=appointment,
                new_slot=new_slot,
                request=request,
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect("appointments:appointment_reschedule", pk=appointment.pk)
        messages.success(request, "Votre rendez-vous a été déplacé vers le nouveau créneau.")
        return redirect("appointments:appointment_list")

    return render(
        request,
        "appointments/reschedule.html",
        {
            "appointment": appointment,
            "can_change": _patient_can_change(appointment),
            "slot_days": _free_slot_days(appointment.doctor),
        },
    )


class DoctorAgendaView(DoctorRequiredMixin, ListView):
    template_name = "appointments/doctor_agenda.html"
    context_object_name = "past_appointments"
    paginate_by = 10

    def get_profile(self):
        return get_object_or_404(
            DoctorProfile.objects.select_related("user", "specialty"),
            user=self.request.user,
        )

    def get_queryset(self):
        profile = self.get_profile()
        today = timezone.localdate()
        return (
            Appointment.objects.filter(doctor=profile)
            .filter(Q(date__lt=today) | ~Q(status__in=OPEN_STATUSES))
            .select_related("patient")
            .order_by("-date", "-start_time")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.get_profile()
        today = timezone.localdate()
        upcoming = (
            Appointment.objects.filter(doctor=profile)
            .filter(status__in=OPEN_STATUSES, date__gte=today)
            .select_related("patient")
            .order_by("date", "start_time")
        )
        context["profile"] = profile
        context["today_appointments"] = [a for a in upcoming if a.date == today]
        context["upcoming_appointments"] = [a for a in upcoming if a.date > today]
        context["pending_count"] = sum(
            1 for a in upcoming if a.status == Appointment.Status.PENDING
        )
        return context


class DoctorAppointmentActionView(DoctorRequiredMixin, View):
    ALLOWED_ACTIONS = {
        "confirm": Appointment.Status.CONFIRMED,
        "complete": Appointment.Status.COMPLETED,
        "cancel": "cancel",
    }

    def post(self, request, pk, action):
        profile = get_object_or_404(DoctorProfile.objects.select_related("user"), user=request.user)
        appointment = get_object_or_404(
            Appointment.objects.select_related("patient"), pk=pk, doctor=profile
        )
        new_status = self.ALLOWED_ACTIONS.get(action)
        if new_status is None:
            raise PermissionDenied("Action inconnue.")

        try:
            if new_status == "cancel":
                cancel_appointment(
                    appointment=appointment,
                    actor=request.user,
                    cancelled_by="doctor",
                    request=request,
                )
                messages.success(request, "Le rendez-vous a été annulé.")
            else:
                set_doctor_status(
                    appointment=appointment,
                    doctor_profile=profile,
                    new_status=new_status,
                    actor=request.user,
                    request=request,
                )
                if new_status == Appointment.Status.CONFIRMED:
                    messages.success(request, "Le rendez-vous a été confirmé.")
                else:
                    messages.success(request, "Le rendez-vous a été marqué comme terminé.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect("doctor_agenda")
