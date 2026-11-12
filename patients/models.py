from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r"^\+?[0-9 .()\-]{8,20}$",
    message="Saisissez un numéro de téléphone valide (8 à 20 chiffres).",
)


class PatientProfile(models.Model):
    """Personal information attached to a user with the patient role."""

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="patient_profile",
        limit_choices_to={"role": "patient"},
        verbose_name="utilisateur",
    )
    birth_date = models.DateField("date de naissance", null=True, blank=True)
    phone = models.CharField("téléphone", max_length=30, blank=True, validators=[phone_validator])
    consent_given_at = models.DateTimeField("consentement recueilli le", null=True, blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "profil patient"
        verbose_name_plural = "profils patients"

    def __str__(self):
        return f"Profil de {self.user.full_name}"

    @property
    def age(self):
        if not self.birth_date:
            return None
        today = timezone.localdate()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )
