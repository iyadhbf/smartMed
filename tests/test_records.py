"""Sprint 4 — medical records: access rules, validation, views, and audit."""

from datetime import time, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, User
from appointments.models import Appointment
from doctors.models import DoctorProfile, Specialty
from medical_records import services
from medical_records.models import Consultation, Document, MedicalRecord
from patients.models import PatientProfile

PDF_BYTES = b"%PDF-1.4 fake demo document"


def _make_user(email, role, first, last):
    return User.objects.create_user(
        email=email,
        password="MotDePasse123!",
        first_name=first,
        last_name=last,
        role=role,
    )


class RecordAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.patient = _make_user("patient@smartmed.test", User.Role.PATIENT, "Sami", "Khelifi")
        cls.other_patient = _make_user(
            "patient2@smartmed.test", User.Role.PATIENT, "Nour", "Jaziri"
        )
        cls.doctor_user = _make_user("doctor@smartmed.test", User.Role.DOCTOR, "Amine", "Ben Salah")
        cls.other_doctor_user = _make_user(
            "doctor2@smartmed.test", User.Role.DOCTOR, "Leïla", "Trabelsi"
        )
        cls.patient_profile = PatientProfile.objects.create(user=cls.patient)
        cls.other_patient_profile = PatientProfile.objects.create(user=cls.other_patient)
        cls.doctor = DoctorProfile.objects.create(
            user=cls.doctor_user,
            specialty=cls.specialty,
            professional_number="TN-MD-0001",
        )
        cls.other_doctor = DoctorProfile.objects.create(
            user=cls.other_doctor_user,
            specialty=cls.specialty,
            professional_number="TN-MD-0002",
        )
        cls.record = MedicalRecord.objects.create(
            patient=cls.patient_profile,
            history="Hypertension artérielle (fictive)",
            allergies="Pénicilline (fictif)",
        )
        cls.relationship = Appointment.objects.create(
            patient=cls.patient,
            doctor=cls.doctor,
            date=timezone.localdate() - timedelta(days=1),
            start_time=time(9, 0),
            end_time=time(9, 30),
            status=Appointment.Status.COMPLETED,
        )

    def test_get_or_create_record_is_idempotent(self):
        first = services.get_or_create_record(self.patient_profile)
        second = services.get_or_create_record(self.patient_profile)
        self.assertEqual(first.pk, self.record.pk)
        self.assertEqual(second.pk, self.record.pk)

    def test_doctor_has_access_with_non_cancelled_appointment(self):
        self.assertTrue(services.doctor_has_access(self.doctor, self.patient_profile))

    def test_doctor_without_relationship_has_no_access(self):
        self.assertFalse(services.doctor_has_access(self.other_doctor, self.patient_profile))
        self.assertFalse(services.doctor_has_access(self.doctor, self.other_patient_profile))

    def test_cancelled_appointment_removes_access(self):
        self.relationship.status = Appointment.Status.CANCELLED
        self.relationship.save()
        self.assertFalse(services.doctor_has_access(self.doctor, self.patient_profile))

    def test_doctor_record_lookup_denies_unrelated_doctor(self):
        with self.assertRaises(PermissionDenied):
            services.get_patient_record_for_doctor(
                doctor_profile=self.other_doctor,
                patient_pk=self.patient_profile.pk,
            )

    def test_doctor_record_lookup_denies_patient_without_relationship(self):
        with self.assertRaises(PermissionDenied):
            services.get_patient_record_for_doctor(
                doctor_profile=self.doctor,
                patient_pk=self.other_patient_profile.pk,
            )

    def test_doctor_record_lookup_creates_missing_record(self):
        third_user = _make_user("patient3@smartmed.test", User.Role.PATIENT, "Rim", "Bouzid")
        third_profile = PatientProfile.objects.create(user=third_user)
        Appointment.objects.create(
            patient=third_user,
            doctor=self.doctor,
            date=timezone.localdate(),
            start_time=time(11, 0),
            end_time=time(11, 30),
            status=Appointment.Status.PENDING,
        )

        record = services.get_patient_record_for_doctor(
            doctor_profile=self.doctor,
            patient_pk=third_profile.pk,
        )

        self.assertEqual(record.patient, third_profile)

    def test_update_record_summary_requires_access(self):
        with self.assertRaises(PermissionDenied):
            services.update_record_summary(
                doctor_profile=self.other_doctor,
                record=self.record,
                history="X",
                allergies="Y",
                treatments="Z",
            )

    def test_update_record_summary_saves_and_audits(self):
        services.update_record_summary(
            doctor_profile=self.doctor,
            record=self.record,
            history="Migraine (fictive)",
            allergies="Aucune",
            treatments="Repos",
            actor=self.doctor_user,
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.history, "Migraine (fictive)")
        self.assertTrue(
            AuditLog.objects.filter(
                event=AuditLog.Event.RECORD_UPDATED,
                actor=self.doctor_user,
            ).exists()
        )


class ConsultationAndPrescriptionTests(RecordAccessTests):
    def test_create_consultation_with_prescription(self):
        consultation = services.create_consultation(
            doctor_profile=self.doctor,
            record=self.record,
            report="Tension normale (fictif).",
            prescription_content="Paracétamol 500 mg, 3 fois par jour (fictif).",
            actor=self.doctor_user,
        )
        self.assertEqual(consultation.record, self.record)
        self.assertEqual(consultation.doctor, self.doctor)
        self.assertEqual(consultation.prescriptions.count(), 1)
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.CONSULTATION_CREATED).exists())
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.PRESCRIPTION_ISSUED).exists())

    def test_create_consultation_without_prescription(self):
        consultation = services.create_consultation(
            doctor_profile=self.doctor,
            record=self.record,
            report="Simple contrôle.",
        )
        self.assertEqual(consultation.prescriptions.count(), 0)

    def test_create_consultation_validates_appointment_ownership(self):
        foreign = Appointment.objects.create(
            patient=self.other_patient,
            doctor=self.doctor,
            date=timezone.localdate(),
            start_time=time(10, 0),
            end_time=time(10, 30),
            status=Appointment.Status.COMPLETED,
        )
        with self.assertRaises(PermissionDenied):
            services.create_consultation(
                doctor_profile=self.doctor,
                record=self.record,
                report="Intrusion.",
                appointment=foreign,
            )

    def test_create_consultation_requires_access(self):
        other_record = MedicalRecord.objects.create(patient=self.other_patient_profile)
        with self.assertRaises(PermissionDenied):
            services.create_consultation(
                doctor_profile=self.doctor,
                record=other_record,
                report="Intrusion.",
            )

    def test_only_the_author_doctor_can_sign_the_prescription(self):
        consultation = services.create_consultation(
            doctor_profile=self.doctor,
            record=self.record,
            report="Contrôle.",
        )
        with self.assertRaises(PermissionDenied):
            services.issue_prescription(
                doctor_profile=self.other_doctor,
                consultation=consultation,
                content="Médicament fictif.",
            )


class DocumentTests(RecordAccessTests):
    def _file(self, name="analyse.pdf", content=PDF_BYTES):
        return SimpleUploadedFile(name, content, content_type="application/pdf")

    def test_document_rejects_disallowed_extension(self):
        document = Document(
            patient=self.patient_profile,
            file=SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream"),
            uploaded_by=self.doctor_user,
        )
        with self.assertRaises(ValidationError):
            document.save()

    def test_document_rejects_oversized_file(self):
        big = self._file(content=b"x" * (5 * 1024 * 1024 + 1))
        document = Document(
            patient=self.patient_profile,
            file=big,
            uploaded_by=self.doctor_user,
        )
        with self.assertRaises(ValidationError):
            document.save()

    def test_document_accepts_pdf(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=self._file(),
            document_type=Document.Type.ANALYSIS,
            title="Bilan sanguin (fictif)",
        )
        self.assertTrue(document.file.name.endswith(".pdf"))
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.DOCUMENT_UPLOADED).exists())

    def test_upload_requires_doctor_access(self):
        with self.assertRaises(PermissionDenied):
            services.upload_document(
                user=self.other_doctor_user,
                doctor_profile=self.other_doctor,
                patient_profile=self.patient_profile,
                file=self._file(),
                document_type=Document.Type.OTHER,
            )

    def test_owner_patient_can_download(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=self._file(),
            document_type=Document.Type.OTHER,
        )
        found = services.get_document_for_user(user=self.patient, pk=document.pk)
        self.assertEqual(found.pk, document.pk)
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.DOCUMENT_DOWNLOADED).exists())

    def test_other_patient_cannot_download(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=self._file(),
            document_type=Document.Type.OTHER,
        )
        with self.assertRaises(PermissionDenied):
            services.get_document_for_user(user=self.other_patient, pk=document.pk)

    def test_unrelated_doctor_cannot_download(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=self._file(),
            document_type=Document.Type.OTHER,
        )
        with self.assertRaises(PermissionDenied):
            services.get_document_for_user(user=self.other_doctor_user, pk=document.pk)


class RecordViewTests(RecordAccessTests):
    def test_patient_sees_own_record(self):
        services.create_consultation(
            doctor_profile=self.doctor,
            record=self.record,
            report="Compte rendu fictif de démonstration.",
            prescription_content="Ordonnance fictive de démonstration.",
        )
        self.client.force_login(self.patient)

        response = self.client.get(reverse("records:patient_record"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hypertension artérielle")
        self.assertContains(response, "Compte rendu fictif")
        self.assertContains(response, "Ordonnance fictive")
        self.assertTrue(
            AuditLog.objects.filter(event=AuditLog.Event.RECORD_VIEWED, actor=self.patient).exists()
        )

    def test_record_is_created_on_first_view(self):
        self.client.force_login(self.other_patient)

        response = self.client.get(reverse("records:patient_record"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(MedicalRecord.objects.filter(patient=self.other_patient_profile).exists())

    def test_patient_cannot_open_doctor_patient_list(self):
        self.client.force_login(self.patient)

        response = self.client.get(reverse("records:doctor_patients"))

        self.assertEqual(response.status_code, 403)

    def test_doctor_cannot_open_patient_record_page(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("records:patient_record"))

        self.assertEqual(response.status_code, 403)

    def test_doctor_patient_list_shows_only_authorised_patients(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("records:doctor_patients"))

        self.assertEqual(response.status_code, 200)
        shown = [p.pk for p in response.context["patients"]]
        self.assertIn(self.patient_profile.pk, shown)
        self.assertNotIn(self.other_patient_profile.pk, shown)

    def test_doctor_patient_list_search(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("records:doctor_patients"), {"q": "khelifi"})

        shown = [p.pk for p in response.context["patients"]]
        self.assertEqual(shown, [self.patient_profile.pk])

    def test_doctor_record_page_denied_for_unrelated_patient(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(
            reverse("records:doctor_patient_record", args=[self.other_patient_profile.pk])
        )

        self.assertEqual(response.status_code, 403)

    def test_doctor_updates_summary_through_the_view(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("records:doctor_patient_record", args=[self.patient_profile.pk]),
            {
                "form_kind": "summary",
                "history": "Asthme (fictif)",
                "allergies": "Aucune",
                "treatments": "Ventoline si besoin",
            },
        )

        self.assertRedirects(
            response, reverse("records:doctor_patient_record", args=[self.patient_profile.pk])
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.history, "Asthme (fictif)")

    def test_doctor_creates_consultation_with_prescription_through_the_view(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("records:doctor_patient_record", args=[self.patient_profile.pk]),
            {
                "form_kind": "consultation",
                "occurred_at": "2026-10-26T09:00",
                "appointment": "",
                "report": "Compte rendu de démonstration.",
                "prescription_content": "Paracétamol fictif 500 mg.",
            },
        )

        self.assertEqual(response.status_code, 302)
        consultation = Consultation.objects.get(record=self.record)
        self.assertEqual(consultation.report, "Compte rendu de démonstration.")
        self.assertEqual(consultation.prescriptions.count(), 1)

    def test_doctor_uploads_document_through_the_view(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("records:doctor_patient_record", args=[self.patient_profile.pk]),
            {
                "form_kind": "document",
                "document_type": Document.Type.ANALYSIS,
                "title": "Bilan (fictif)",
                "consultation": "",
                "file": SimpleUploadedFile("bilan.pdf", PDF_BYTES, content_type="application/pdf"),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Document.objects.filter(patient=self.patient_profile).exists())

    def test_view_rejects_disallowed_document_extension(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("records:doctor_patient_record", args=[self.patient_profile.pk]),
            {
                "form_kind": "document",
                "document_type": Document.Type.OTHER,
                "title": "",
                "consultation": "",
                "file": SimpleUploadedFile(
                    "notes.exe", b"MZ", content_type="application/octet-stream"
                ),
            },
            follow=True,
        )

        self.assertEqual(Document.objects.count(), 0)
        self.assertContains(response, "Format non autorisé")

    def test_document_download_permissions(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=SimpleUploadedFile("bilan.pdf", PDF_BYTES, content_type="application/pdf"),
            document_type=Document.Type.ANALYSIS,
        )
        url = reverse("records:document_download", args=[document.pk])

        self.client.force_login(self.patient)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"].find("attachment"), 0)

        self.client.force_login(self.other_patient)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.doctor_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.other_doctor_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_download_redirects_to_login(self):
        document = services.upload_document(
            user=self.doctor_user,
            doctor_profile=self.doctor,
            patient_profile=self.patient_profile,
            file=SimpleUploadedFile("bilan.pdf", PDF_BYTES, content_type="application/pdf"),
            document_type=Document.Type.ANALYSIS,
        )

        response = self.client.get(reverse("records:document_download", args=[document.pk]))

        self.assertRedirects(
            response, f"/compte/connexion/?next=/documents/{document.pk}/telecharger/"
        )

    def test_unknown_form_kind_shows_an_error(self):
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("records:doctor_patient_record", args=[self.patient_profile.pk]),
            {"form_kind": "hacker"},
            follow=True,
        )

        self.assertContains(response, "Formulaire inconnu")
