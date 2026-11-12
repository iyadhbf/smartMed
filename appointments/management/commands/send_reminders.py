"""Send a reminder e-mail for each confirmed appointment starting tomorrow.

Usage:
    python manage.py send_reminders
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from appointments.emails import send_reminder_email
from appointments.models import Appointment


class Command(BaseCommand):
    help = "Envoie un rappel pour chaque rendez-vous confirmé du lendemain (une seule fois)."

    @transaction.atomic
    def handle(self, *args, **options):
        tomorrow = timezone.localdate() + timedelta(days=1)
        due = Appointment.objects.filter(
            status=Appointment.Status.CONFIRMED,
            date=tomorrow,
            reminder_sent_at__isnull=True,
        ).select_related("patient", "doctor", "doctor__user", "doctor__specialty")

        sent = 0
        for appointment in due:
            send_reminder_email(appointment)
            appointment.reminder_sent_at = timezone.now()
            appointment.save(update_fields=["reminder_sent_at"])
            sent += 1

        self.stdout.write(
            self.style.SUCCESS(f"{sent} rappel(s) envoyé(s) pour le {tomorrow:%d/%m/%Y}.")
        )
