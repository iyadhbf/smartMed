"""Medical records: record, consultations, prescriptions, and documents.

Every access rule lives in ``services.py``; models only enforce shape and
file-validation invariants so bad data cannot be saved even from a shell.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_DOCUMENT_EXTENSIONS = ("pdf", "jpg", "jpeg", "png")


def patient_document_path(instance, filename):
    return f"documents/patient_{instance.patient_id}/{filename}"


class MedicalRecord(models.Model):
    """A patient's single medical record (antecedents, allergies, treatments)."""

    patient = models.OneToOneField(
        "patients.PatientProfile",
        on_delete=models.CASCADE,
        related_name="medical_record",
        verbose_name="patient",
    )
    history = models.TextField("antécédents", blank=True)
    allergies = models.TextField("allergies", blank=True)
    treatments = models.TextField("traitements en cours", blank=True)
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "dossier médical"
        verbose_name_plural = "dossiers médicaux"

    def __str__(self):
        return f"Dossier de {self.patient.user.full_name}"


class Consultation(models.Model):
    """A consultation report written by a doctor inside a patient's record."""

    record = models.ForeignKey(
        MedicalRecord,
        on_delete=models.CASCADE,
        related_name="consultations",
        verbose_name="dossier",
    )
    doctor = models.ForeignKey(
        "doctors.DoctorProfile",
        on_delete=models.PROTECT,
        related_name="consultations",
        verbose_name="médecin",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consultations",
        verbose_name="rendez-vous",
    )
    occurred_at = models.DateTimeField("date de consultation", default=timezone.now)
    report = models.TextField("compte rendu")
    created_at = models.DateTimeField("créé le", auto_now_add=True)
    updated_at = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = "consultation"
        verbose_name_plural = "consultations"
        indexes = [
            models.Index(fields=["record", "occurred_at"]),
        ]

    def __str__(self):
        return f"Consultation du {self.occurred_at:%d/%m/%Y} — {self.doctor}"


class Prescription(models.Model):
    """A prescription issued by a doctor, always linked to a consultation."""

    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name="prescriptions",
        verbose_name="consultation",
    )
    content = models.TextField("contenu")
    issued_on = models.DateField("date d'émission", default=timezone.localdate)
    created_at = models.DateTimeField("créé le", auto_now_add=True)

    class Meta:
        ordering = ["-issued_on", "-pk"]
        verbose_name = "prescription"
        verbose_name_plural = "prescriptions"

    def __str__(self):
        return f"Ordonnance du {self.issued_on:%d/%m/%Y}"


class Document(models.Model):
    """A medical document stored for one patient, optionally tied to a consultation."""

    class Type(models.TextChoices):
        PRESCRIPTION = "prescription", "Ordonnance"
        REPORT = "report", "Compte rendu"
        ANALYSIS = "analysis", "Analyse"
        IMAGING = "imaging", "Imagerie"
        OTHER = "other", "Autre"

    patient = models.ForeignKey(
        "patients.PatientProfile",
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="patient",
    )
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
        verbose_name="consultation",
    )
    document_type = models.CharField(
        "type", max_length=20, choices=Type.choices, default=Type.OTHER
    )
    title = models.CharField("titre", max_length=120, blank=True)
    file = models.FileField("fichier", upload_to=patient_document_path)
    uploaded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_documents",
        verbose_name="ajouté par",
    )
    created_at = models.DateTimeField("ajouté le", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "document"
        verbose_name_plural = "documents"

    def clean(self):
        super().clean()
        file = getattr(self, "file", None)
        if not file:
            return
        name = getattr(file, "name", "") or ""
        extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise ValidationError({"file": ("Format non autorisé. Utilisez PDF, JPG ou PNG.")})
        if file.size > MAX_DOCUMENT_SIZE:
            raise ValidationError({"file": "Le fichier dépasse la taille maximale de 5 Mo."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.title or (self.file.name.rsplit("/", 1)[-1] if self.file else "Document")

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.patient.user.full_name}"
