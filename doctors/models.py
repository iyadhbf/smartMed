from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Lundi"
    TUESDAY = 1, "Mardi"
    WEDNESDAY = 2, "Mercredi"
    THURSDAY = 3, "Jeudi"
    FRIDAY = 4, "Vendredi"
    SATURDAY = 5, "Samedi"
    SUNDAY = 6, "Dimanche"


class Specialty(models.Model):
    """Medical department / specialty shown on the public site."""

    class Icon(models.TextChoices):
        EMERGENCY = "truck", "Urgences"
        PEDIATRICS = "emoji-smile", "Pédiatrie"
        CARDIOLOGY = "heart-pulse", "Cardiologie"
        DERMATOLOGY = "bandaid", "Dermatologie"
        GENERAL = "clipboard2-pulse", "Médecine générale"
        GYNECOLOGY = "gender-female", "Gynécologie"

    name = models.CharField("nom", max_length=120, unique=True)
    slug = models.SlugField("slug", max_length=140, unique=True, blank=True)
    description = models.TextField("description", blank=True)
    icon = models.CharField("icône", max_length=40, choices=Icon.choices, default=Icon.GENERAL)
    is_bookable = models.BooleanField(
        "réservable en ligne",
        default=True,
        help_text="Désactivé pour les services comme les urgences, affichés sans réservation en ligne.",
    )
    is_active = models.BooleanField("active", default=True)
    display_order = models.PositiveSmallIntegerField("ordre d'affichage", default=0)

    class Meta:
        verbose_name = "spécialité"
        verbose_name_plural = "spécialités"
        ordering = ["display_order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class DoctorProfile(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="doctor_profile",
        limit_choices_to={"role": "doctor"},
        verbose_name="utilisateur",
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.PROTECT,
        related_name="doctors",
        verbose_name="spécialité",
    )
    professional_number = models.CharField("numéro professionnel", max_length=60, unique=True)
    bio = models.TextField("biographie", blank=True)
    photo = models.ImageField("photo", upload_to="doctors/", blank=True)
    consultation_duration = models.PositiveSmallIntegerField(
        "durée de consultation (minutes)",
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(120)],
        help_text="Durée d'un créneau, en minutes.",
    )
    is_active = models.BooleanField("actif", default=True)
    display_order = models.PositiveSmallIntegerField("ordre d'affichage", default=0)
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        verbose_name = "profil médecin"
        verbose_name_plural = "profils médecins"
        ordering = ["display_order", "user__last_name", "user__first_name"]
        indexes = [
            models.Index(fields=["specialty", "is_active"]),
        ]

    def __str__(self):
        return f"Dr {self.user.full_name} — {self.specialty.name}"

    @property
    def display_name(self):
        return f"Dr {self.user.full_name}"


class WeeklyAvailability(models.Model):
    """Recurring weekly working hours used to generate bookable slots."""

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="weekly_hours",
        verbose_name="médecin",
    )
    weekday = models.PositiveSmallIntegerField("jour", choices=Weekday.choices)
    start_time = models.TimeField("heure de début")
    end_time = models.TimeField("heure de fin")
    is_active = models.BooleanField("actif", default=True)

    class Meta:
        verbose_name = "disponibilité hebdomadaire"
        verbose_name_plural = "disponibilités hebdomadaires"
        ordering = ["doctor", "weekday", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="weekly_availability_start_before_end",
            ),
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time", "end_time"],
                name="weekly_availability_unique_interval",
            ),
        ]

    def __str__(self):
        return (
            f"{self.doctor.display_name} — {self.get_weekday_display()} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": "L'heure de fin doit être postérieure à l'heure de début."}
            )
        if not (self.doctor_id and self.start_time and self.end_time) or not self.is_active:
            return
        overlaps = (
            type(self)
            .objects.filter(
                doctor_id=self.doctor_id,
                weekday=self.weekday,
                is_active=True,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            )
            .exclude(pk=self.pk)
        )
        if overlaps.exists():
            raise ValidationError(
                {"end_time": "Ces horaires chevauchent une plage déjà définie pour ce jour."}
            )

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)


class AvailabilityException(models.Model):
    """A day off or a closed time range for a doctor."""

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="exceptions",
        verbose_name="médecin",
    )
    date = models.DateField("date")
    start_time = models.TimeField("heure de début", null=True, blank=True)
    end_time = models.TimeField("heure de fin", null=True, blank=True)
    reason = models.CharField("motif", max_length=200, blank=True)

    class Meta:
        verbose_name = "exception de disponibilité"
        verbose_name_plural = "exceptions de disponibilité"
        ordering = ["date", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(start_time__isnull=True, end_time__isnull=True)
                    | models.Q(
                        start_time__isnull=False,
                        end_time__isnull=False,
                        start_time__lt=models.F("end_time"),
                    )
                ),
                name="availability_exception_valid_range",
            ),
        ]

    def __str__(self):
        if self.is_full_day:
            return f"{self.doctor.display_name} — {self.date:%d/%m/%Y} (journée)"
        return (
            f"{self.doctor.display_name} — {self.date:%d/%m/%Y} "
            f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"
        )

    @property
    def is_full_day(self):
        return self.start_time is None and self.end_time is None

    def clean(self):
        super().clean()
        has_start = self.start_time is not None
        has_end = self.end_time is not None
        if has_start != has_end:
            raise ValidationError(
                {"start_time": "Renseignez l'heure de début et l'heure de fin, ou aucune des deux."}
            )
        if has_start and has_end and self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": "L'heure de fin doit être postérieure à l'heure de début."}
            )

    def blocks(self, start_time, end_time):
        if self.is_full_day:
            return True
        return self.start_time < end_time and self.end_time > start_time


class Availability(models.Model):
    """A concrete bookable slot generated from weekly hours and exceptions."""

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="slots",
        verbose_name="médecin",
    )
    date = models.DateField("date", db_index=True)
    start_time = models.TimeField("heure de début")
    end_time = models.TimeField("heure de fin")

    class Meta:
        verbose_name = "créneau"
        verbose_name_plural = "créneaux"
        ordering = ["date", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="availability_start_before_end",
            ),
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                name="availability_unique_start",
            ),
        ]
        indexes = [
            models.Index(fields=["doctor", "date", "start_time"]),
        ]

    def __str__(self):
        return f"{self.doctor.display_name} — {self.date:%d/%m/%Y} {self.start_time:%H:%M}"
