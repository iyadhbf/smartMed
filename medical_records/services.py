"""Access rules for medical records.

Authorisation model: a patient always sees their own record; a doctor sees a
patient's record only when a non-cancelled appointment links them. Every
sensitive read (record view, document download) and every write is audited.
"""

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone

from accounts.audit import log_event
from accounts.models import AuditLog, User
from appointments.models import Appointment
from doctors.models import DoctorProfile
from patients.models import PatientProfile

from .models import Consultation, Document, MedicalRecord, Prescription


def get_or_create_record(patient_profile):
    record, _ = MedicalRecord.objects.get_or_create(patient=patient_profile)
    return record


ACCESS_STATUSES = (
    Appointment.Status.PENDING,
    Appointment.Status.CONFIRMED,
    Appointment.Status.COMPLETED,
)


def doctor_has_access(doctor_profile, patient_profile):
    """A doctor is authorised when a non-cancelled appointment links them."""
    return Appointment.objects.filter(
        doctor=doctor_profile,
        patient=patient_profile.user,
        status__in=ACCESS_STATUSES,
    ).exists()


def get_patient_record_for_doctor(*, doctor_profile, patient_pk):
    """Return the patient's record for an authorised doctor, else 404."""
    patient = get_object_or_404(PatientProfile, pk=patient_pk)
    if not doctor_has_access(doctor_profile, patient):
        raise PermissionDenied("Vous n'avez pas de relation de soins avec ce patient.")
    return get_or_create_record(patient)


def audit_record_view(*, actor, record, request=None):
    log_event(
        event=AuditLog.Event.RECORD_VIEWED,
        actor=actor,
        target=record.patient.user,
        request=request,
        description=f"Dossier de {record.patient.user.full_name}",
        metadata={"record_id": record.pk},
    )


def update_record_summary(
    *, doctor_profile, record, history, allergies, treatments, actor=None, request=None
):
    if not doctor_has_access(doctor_profile, record.patient):
        raise PermissionDenied("Vous n'avez pas de relation de soins avec ce patient.")
    record.history = history.strip()
    record.allergies = allergies.strip()
    record.treatments = treatments.strip()
    record.save()
    log_event(
        event=AuditLog.Event.RECORD_UPDATED,
        actor=actor or doctor_profile.user,
        target=record.patient.user,
        request=request,
        description=f"Dossier de {record.patient.user.full_name}",
        metadata={"record_id": record.pk},
    )
    return record


def create_consultation(
    *,
    doctor_profile,
    record,
    report,
    occurred_at=None,
    appointment=None,
    prescription_content="",
    actor=None,
    request=None,
):
    """Write a consultation report; optionally issue a prescription in the same flow."""
    if not doctor_has_access(doctor_profile, record.patient):
        raise PermissionDenied("Vous n'avez pas de relation de soins avec ce patient.")
    if appointment is not None:
        if (
            appointment.patient_id != record.patient.user_id
            or appointment.doctor_id != doctor_profile.pk
        ):
            raise PermissionDenied("Ce rendez-vous ne concerne pas ce patient.")
    consultation = Consultation.objects.create(
        record=record,
        doctor=doctor_profile,
        appointment=appointment,
        occurred_at=occurred_at or timezone.now(),
        report=report.strip(),
    )
    log_event(
        event=AuditLog.Event.CONSULTATION_CREATED,
        actor=actor or doctor_profile.user,
        target=record.patient.user,
        request=request,
        description=f"Consultation du {consultation.occurred_at:%d/%m/%Y}",
        metadata={"consultation_id": consultation.pk},
    )
    if prescription_content.strip():
        issue_prescription(
            doctor_profile=doctor_profile,
            consultation=consultation,
            content=prescription_content,
            actor=actor,
            request=request,
        )
    return consultation


def issue_prescription(
    *, doctor_profile, consultation, content, issued_on=None, actor=None, request=None
):
    """Issue a prescription; only the doctor who wrote the consultation may sign it."""
    if consultation.doctor_id != doctor_profile.pk:
        raise PermissionDenied(
            "Seul le médecin auteur de la consultation peut délivrer cette ordonnance."
        )
    prescription = Prescription.objects.create(
        consultation=consultation,
        content=content.strip(),
        issued_on=issued_on or timezone.localdate(),
    )
    log_event(
        event=AuditLog.Event.PRESCRIPTION_ISSUED,
        actor=actor or doctor_profile.user,
        target=consultation.record.patient.user,
        request=request,
        description=f"Ordonnance du {prescription.issued_on:%d/%m/%Y}",
        metadata={
            "prescription_id": prescription.pk,
            "consultation_id": consultation.pk,
        },
    )
    return prescription


def upload_document(
    *,
    user,
    doctor_profile,
    patient_profile,
    file,
    document_type,
    title="",
    consultation=None,
    request=None,
):
    if doctor_profile is None or not doctor_has_access(doctor_profile, patient_profile):
        raise PermissionDenied("Vous n'avez pas de relation de soins avec ce patient.")
    if consultation is not None and consultation.record.patient_id != patient_profile.pk:
        raise PermissionDenied("Cette consultation ne concerne pas ce patient.")
    document = Document(
        patient=patient_profile,
        consultation=consultation,
        document_type=document_type,
        title=title.strip(),
        file=file,
        uploaded_by=user,
    )
    document.save()  # model validation: extension whitelist + 5 MB cap
    log_event(
        event=AuditLog.Event.DOCUMENT_UPLOADED,
        actor=user,
        target=patient_profile.user,
        request=request,
        description=f"{document.get_document_type_display()} — {document.display_name}",
        metadata={"document_id": document.pk},
    )
    return document


def get_document_for_user(*, user, pk, request=None):
    """Fetch a document the user may read (owner patient or authorised doctor), audit it."""
    document = get_object_or_404(
        Document.objects.select_related("patient", "patient__user", "uploaded_by"),
        pk=pk,
    )
    allowed = False
    if user.role == User.Role.PATIENT:
        allowed = document.patient.user_id == user.pk
    elif user.role == User.Role.DOCTOR:
        profile = get_object_or_404(DoctorProfile, user=user)
        allowed = doctor_has_access(profile, document.patient)
    if not allowed:
        raise PermissionDenied("Vous n'avez pas accès à ce document.")
    log_event(
        event=AuditLog.Event.DOCUMENT_DOWNLOADED,
        actor=user,
        target=document.patient.user,
        request=request,
        description=document.display_name,
        metadata={"document_id": document.pk},
    )
    return document
