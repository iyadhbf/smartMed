from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Manager using e-mail as the unique identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superutilisateur doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrateur"
        DOCTOR = "doctor", "Médecin"
        PATIENT = "patient", "Patient"

    username = None
    email = models.EmailField("adresse e-mail", unique=True)
    first_name = models.CharField("prénom", max_length=150)
    last_name = models.CharField("nom", max_length=150)
    role = models.CharField("rôle", max_length=20, choices=Role.choices, default=Role.PATIENT)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def full_name(self):
        return self.get_full_name() or self.email

    @property
    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_patient(self):
        return self.role == self.Role.PATIENT


class AuditLog(models.Model):
    """Append-only journal of sensitive account and security events."""

    class Event(models.TextChoices):
        LOGIN_SUCCESS = "login_success", "Connexion réussie"
        LOGIN_FAILED = "login_failed", "Échec de connexion"
        LOGIN_LOCKED_OUT = "login_locked_out", "Connexion bloquée"
        LOGOUT = "logout", "Déconnexion"
        PASSWORD_RESET_REQUESTED = "password_reset_requested", "Réinitialisation demandée"
        PASSWORD_RESET_COMPLETED = "password_reset_completed", "Réinitialisation effectuée"
        PASSWORD_CHANGED = "password_changed", "Mot de passe modifié"
        ROLE_CHANGED = "role_changed", "Rôle modifié"
        DOCTOR_ACCOUNT_CREATED = "doctor_account_created", "Compte médecin créé"
        DOCTOR_UPDATED = "doctor_updated", "Profil médecin modifié"
        DOCTOR_STATUS_CHANGED = "doctor_status_changed", "Statut médecin modifié"
        SPECIALTY_CREATED = "specialty_created", "Spécialité créée"
        SPECIALTY_UPDATED = "specialty_updated", "Spécialité modifiée"
        SPECIALTY_STATUS_CHANGED = "specialty_status_changed", "Statut spécialité modifié"
        AVAILABILITY_UPDATED = "availability_updated", "Disponibilités modifiées"
        APPOINTMENT_BOOKED = "appointment_booked", "Rendez-vous réservé"
        APPOINTMENT_CONFIRMED = "appointment_confirmed", "Rendez-vous confirmé"
        APPOINTMENT_COMPLETED = "appointment_completed", "Rendez-vous terminé"
        APPOINTMENT_CANCELLED = "appointment_cancelled", "Rendez-vous annulé"
        APPOINTMENT_RESCHEDULED = "appointment_rescheduled", "Rendez-vous déplacé"
        PATIENT_STATUS_CHANGED = "patient_status_changed", "Statut patient modifié"
        RECORD_VIEWED = "record_viewed", "Dossier médical consulté"
        RECORD_UPDATED = "record_updated", "Dossier médical modifié"
        CONSULTATION_CREATED = "consultation_created", "Consultation enregistrée"
        PRESCRIPTION_ISSUED = "prescription_issued", "Prescription délivrée"
        DOCUMENT_UPLOADED = "document_uploaded", "Document médical ajouté"
        DOCUMENT_DOWNLOADED = "document_downloaded", "Document médical téléchargé"

    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
        verbose_name="auteur",
    )
    target_user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events_received",
        verbose_name="utilisateur concerné",
    )
    event = models.CharField("événement", max_length=40, choices=Event.choices, db_index=True)
    description = models.CharField("description", max_length=255, blank=True)
    ip_address = models.GenericIPAddressField("adresse IP", null=True, blank=True)
    user_agent = models.CharField("navigateur", max_length=300, blank=True)
    metadata = models.JSONField("métadonnées", default=dict, blank=True)
    created_at = models.DateTimeField("horodatage", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée d'audit"
        verbose_name_plural = "journal d'audit"
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["event", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_event_display()} — {self.description or self.actor_label}"

    @property
    def actor_label(self):
        if self.actor_id:
            return self.actor.full_name
        return self.description or "Anonyme"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Les entrées d'audit sont immuables.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Les entrées d'audit ne peuvent pas être supprimées.")
