"""Business rules for booking, cancelling, rescheduling, and confirming appointments."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.audit import log_event
from accounts.models import AuditLog, User

from .emails import (
    send_booking_emails,
    send_cancellation_emails,
    send_status_emails,
)
from .models import Appointment

CANCELLATION_LEAD = timedelta(hours=2)

OPEN_STATUSES = (Appointment.Status.PENDING, Appointment.Status.CONFIRMED)


class SlotConflictError(ValidationError):
    """Raised when another open appointment already claims the slot."""


def _check_slot_is_bookable(slot):
    if slot is None:
        raise ValidationError("Ce créneau n'existe plus.")
    if not slot.doctor.is_active or not slot.doctor.user.is_active:
        raise ValidationError("Ce médecin ne prend plus de rendez-vous en ligne.")
    now = timezone.localtime()
    if slot.date < now.date() or (slot.date == now.date() and slot.start_time <= now.time()):
        raise ValidationError("Ce créneau est déjà passé.")


@transaction.atomic
def book_slot(*, patient, slot, reason="", actor=None, request=None):
    """Atomically claim a slot for a patient; the database unique constraint is the backstop."""

    if patient.role != User.Role.PATIENT:
        raise PermissionDenied("Seuls les patients peuvent prendre rendez-vous.")

    _check_slot_is_bookable(slot)
    locked_slot = (
        type(slot)
        .objects.select_related("doctor", "doctor__user")
        .select_for_update()
        .get(pk=slot.pk)
    )
    _check_slot_is_bookable(locked_slot)
    if Appointment.objects.filter(slot=locked_slot, status__in=OPEN_STATUSES).exists():
        raise SlotConflictError("Ce créneau vient d'être réservé. Choisissez un autre horaire.")

    appointment = Appointment(
        patient=patient,
        doctor=locked_slot.doctor,
        slot=locked_slot,
        reason=reason.strip()[:300],
    )
    try:
        appointment.save()
    except IntegrityError as exc:
        raise SlotConflictError(
            "Ce créneau vient d'être réservé. Choisissez un autre horaire."
        ) from exc

    log_event(
        event=AuditLog.Event.APPOINTMENT_BOOKED,
        actor=actor or patient,
        target=locked_slot.doctor.user,
        request=request,
        description=f"{patient.full_name} — {locked_slot.date:%d/%m/%Y %H:%M}",
        metadata={
            "appointment_id": appointment.pk,
            "doctor_id": locked_slot.doctor.pk,
            "date": locked_slot.date.isoformat(),
            "start_time": locked_slot.start_time.isoformat(),
        },
    )
    send_booking_emails(appointment)
    return appointment


def _ensure_patient_can_cancel(patient, appointment):
    if appointment.patient_id != patient.pk:
        raise PermissionDenied("Ce rendez-vous ne vous appartient pas.")
    if appointment.status not in OPEN_STATUSES:
        raise ValidationError("Ce rendez-vous est déjà clôturé.")
    if appointment.starts_at - timezone.localtime() < CANCELLATION_LEAD:
        raise ValidationError(
            "Ce rendez-vous a lieu dans moins de 2 heures et ne peut plus être annulé "
            "en ligne. Contactez le centre."
        )


@transaction.atomic
def cancel_appointment(*, appointment, actor, cancelled_by, request=None):
    """Cancel an open appointment. `cancelled_by` is 'patient', 'doctor', or 'admin'."""

    if cancelled_by == "patient":
        _ensure_patient_can_cancel(actor, appointment)
    elif cancelled_by == "doctor":
        if actor.doctor_profile.pk != appointment.doctor_id:
            raise PermissionDenied("Ce rendez-vous ne fait pas partie de votre agenda.")
    elif cancelled_by != "admin":
        raise ValueError(f"Unknown cancelled_by value: {cancelled_by}")

    if appointment.status not in OPEN_STATUSES:
        raise ValidationError("Ce rendez-vous est déjà clôturé.")

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])

    log_event(
        event=AuditLog.Event.APPOINTMENT_CANCELLED,
        actor=actor if actor.is_authenticated else None,
        target=appointment.patient,
        request=request,
        description=f"{appointment.patient.full_name} — {appointment.date:%d/%m/%Y %H:%M}",
        metadata={
            "appointment_id": appointment.pk,
            "doctor_id": appointment.doctor_id,
            "cancelled_by": cancelled_by,
        },
    )
    send_cancellation_emails(appointment, cancelled_by)
    return appointment


@transaction.atomic
def reschedule_appointment(*, patient, appointment, new_slot, reason="", request=None):
    """Cancel the old appointment (same policy as cancel) and book the new slot."""

    _ensure_patient_can_cancel(patient, appointment)
    try:
        new_appointment = book_slot(
            patient=patient, slot=new_slot, reason=reason or appointment.reason, request=request
        )
    except ValidationError:
        raise
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])
    log_event(
        event=AuditLog.Event.APPOINTMENT_RESCHEDULED,
        actor=patient,
        target=appointment.doctor.user,
        request=request,
        description=f"{patient.full_name} — {appointment.date:%d/%m/%Y %H:%M}",
        metadata={
            "old_appointment_id": appointment.pk,
            "new_appointment_id": new_appointment.pk,
            "old_slot": f"{appointment.date.isoformat()} {appointment.start_time:%H:%M}",
            "new_slot": f"{new_appointment.date.isoformat()} {new_appointment.start_time:%H:%M}",
        },
    )
    return new_appointment


@transaction.atomic
def set_doctor_status(*, appointment, doctor_profile, new_status, actor, request=None):
    """Allow a doctor to confirm (pending → confirmed) or complete (confirmed → completed)."""

    if doctor_profile.pk != appointment.doctor_id:
        raise PermissionDenied("Ce rendez-vous ne fait pas partie de votre agenda.")

    allowed = {
        Appointment.Status.CONFIRMED: (Appointment.Status.PENDING,),
        Appointment.Status.COMPLETED: (Appointment.Status.CONFIRMED,),
    }
    if appointment.status not in allowed.get(new_status, ()):
        raise ValidationError("Cette transition de statut n'est pas autorisée.")

    appointment.status = new_status
    appointment.save(update_fields=["status", "updated_at"])

    event = (
        AuditLog.Event.APPOINTMENT_CONFIRMED
        if new_status == Appointment.Status.CONFIRMED
        else AuditLog.Event.APPOINTMENT_COMPLETED
    )
    log_event(
        event=event,
        actor=actor,
        target=appointment.patient,
        request=request,
        description=f"{appointment.patient.full_name} — {appointment.date:%d/%m/%Y %H:%M}",
        metadata={"appointment_id": appointment.pk, "status": new_status},
    )
    send_status_emails(appointment)
    return appointment
