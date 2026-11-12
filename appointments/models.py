from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import User
from doctors.models import Availability, DoctorProfile


class Appointment(models.Model):
    """A consultation booked by a patient on a generated slot."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        CONFIRMED = "confirmed", "Confirmé"
        COMPLETED = "completed", "Terminé"
        CANCELLED = "cancelled", "Annulé"

    patient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="appointments",
        limit_choices_to={"role": User.Role.PATIENT},
        verbose_name="patient",
    )
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="médecin",
    )
    slot = models.ForeignKey(
        Availability,
        on_delete=models.SET_NULL,
        related_name="appointments",
        null=True,
        blank=True,
        verbose_name="créneau",
        help_text="Nul pour les rendez-vous historiques dont le créneau a été purgé.",
    )
    date = models.DateField("date")
    start_time = models.TimeField("heure de début")
    end_time = models.TimeField("heure de fin")
    status = models.CharField(
        "statut", max_length=12, choices=Status.choices, default=Status.PENDING
    )
    reason = models.CharField("motif", max_length=300, blank=True)
    reminder_sent_at = models.DateTimeField("rappel envoyé le", null=True, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "rendez-vous"
        verbose_name_plural = "rendez-vous"
        ordering = ["date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=models.Q(slot__isnull=False) & ~models.Q(status="cancelled"),
                name="appointment_unique_open_slot",
            ),
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="appointment_start_before_end",
            ),
        ]
        indexes = [
            models.Index(fields=["patient", "date"]),
            models.Index(fields=["doctor", "date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.patient.full_name} — {self.doctor.display_name} {self.date:%d/%m/%Y %H:%M}"

    @property
    def is_open(self):
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    def clean(self):
        super().clean()
        if self.slot_id and (
            self.date != self.slot.date
            or self.start_time != self.slot.start_time
            or self.end_time != self.slot.end_time
        ):
            raise ValidationError("Les horaires du rendez-vous ne correspondent pas au créneau.")

    def save(self, *args, **kwargs):
        if self.slot_id:
            self.date = self.slot.date
            self.start_time = self.slot.start_time
            self.end_time = self.slot.end_time
        self.full_clean()
        return super().save(*args, **kwargs)
