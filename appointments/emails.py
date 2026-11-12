"""E-mail notifications for the appointment lifecycle (console backend in development)."""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def _send(template, context, subject, recipient):
    body = render_to_string(f"appointments/emails/{template}.txt", context).strip()
    send_mail(
        subject=f"SmartMed AI — {subject}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=True,
    )


def _context(appointment):
    return {
        "appointment": appointment,
        "patient": appointment.patient,
        "doctor": appointment.doctor,
    }


def send_booking_emails(appointment):
    ctx = _context(appointment)
    _send(
        "booking_patient",
        ctx,
        "Votre demande de rendez-vous",
        appointment.patient.email,
    )
    _send(
        "booking_doctor",
        ctx,
        "Nouvelle demande de rendez-vous",
        appointment.doctor.user.email,
    )


def send_cancellation_emails(appointment, cancelled_by_role):
    ctx = {**_context(appointment), "cancelled_by_role": cancelled_by_role}
    if cancelled_by_role != "patient":
        _send("cancellation_patient", ctx, "Rendez-vous annulé", appointment.patient.email)
    if cancelled_by_role != "doctor":
        _send("cancellation_doctor", ctx, "Rendez-vous annulé", appointment.doctor.user.email)


def send_status_emails(appointment):
    ctx = _context(appointment)
    if appointment.status == appointment.Status.CONFIRMED:
        _send(
            "status_confirmed_patient",
            ctx,
            "Rendez-vous confirmé",
            appointment.patient.email,
        )
    elif appointment.status == appointment.Status.COMPLETED:
        _send(
            "status_completed_patient",
            ctx,
            "Compte rendu de votre consultation",
            appointment.patient.email,
        )


def send_reminder_email(appointment):
    _send(
        "reminder_patient",
        _context(appointment),
        "Rappel : rendez-vous demain",
        appointment.patient.email,
    )
