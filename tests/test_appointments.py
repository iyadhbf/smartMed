from datetime import time, timedelta

from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, User
from appointments.models import Appointment
from appointments.services import (
    book_slot,
    cancel_appointment,
    reschedule_appointment,
    set_doctor_status,
)
from doctors.models import Availability, DoctorProfile, Specialty, WeeklyAvailability
from doctors.services import generate_availability


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AppointmentServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.other_patient = User.objects.create_user(
            email="patient2@smartmed.test",
            password="MotDePasse123!",
            first_name="Nour",
            last_name="Jaziri",
        )
        cls.doctor_user = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.doctor = DoctorProfile.objects.create(
            user=cls.doctor_user,
            specialty=cls.specialty,
            professional_number="TN-CARD-1042",
        )

        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        WeeklyAvailability.objects.create(
            doctor=cls.doctor,
            weekday=cls.tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        generate_availability(cls.doctor, days=2, start_date=cls.tomorrow)
        cls.slots = list(cls.doctor.slots.filter(date=cls.tomorrow).order_by("start_time"))

    def test_booking_claims_the_slot_and_denormalizes_times(self):
        appointment = book_slot(
            patient=self.patient, slot=self.slots[0], reason="Douleur thoracique"
        )

        self.assertEqual(appointment.status, Appointment.Status.PENDING)
        self.assertEqual(appointment.date, self.tomorrow)
        self.assertEqual(appointment.start_time, time(9, 0))
        self.assertEqual(appointment.end_time, time(9, 30))
        self.assertEqual(appointment.reason, "Douleur thoracique")

    def test_booking_sends_confirmation_to_patient_and_notification_to_doctor(self):
        book_slot(patient=self.patient, slot=self.slots[0])

        self.assertEqual(len(mail.outbox), 2)
        recipients = {message.to[0] for message in mail.outbox}
        self.assertEqual(recipients, {self.patient.email, self.doctor_user.email})

    def test_booking_writes_an_audit_entry(self):
        book_slot(patient=self.patient, slot=self.slots[0], request=None)

        entry = AuditLog.objects.get(event=AuditLog.Event.APPOINTMENT_BOOKED)
        self.assertEqual(entry.actor, self.patient)
        self.assertEqual(entry.target_user, self.doctor_user)

    def test_a_second_open_booking_on_the_same_slot_is_rejected(self):
        book_slot(patient=self.patient, slot=self.slots[0])

        with self.assertRaises(ValidationError):
            book_slot(patient=self.other_patient, slot=self.slots[0])

    def test_the_unique_constraint_blocks_a_racing_second_booking(self):
        book_slot(patient=self.patient, slot=self.slots[0])

        sneaky = Appointment(patient=self.other_patient, doctor=self.doctor, slot=self.slots[0])
        with self.assertRaises(ValidationError):
            sneaky.save()

    def test_a_cancelled_slot_can_be_rebooked(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])
        cancel_appointment(appointment=appointment, actor=self.patient, cancelled_by="patient")

        rebooked = book_slot(patient=self.other_patient, slot=self.slots[0])
        self.assertEqual(rebooked.patient, self.other_patient)

    def test_past_slots_are_not_bookable(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        past_slot = Availability.objects.create(
            doctor=self.doctor,
            date=yesterday,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )

        with self.assertRaises(ValidationError):
            book_slot(patient=self.patient, slot=past_slot)

    def test_inactive_doctors_are_not_bookable(self):
        self.doctor.is_active = False
        self.doctor.save(update_fields=["is_active"])

        with self.assertRaises(ValidationError):
            book_slot(patient=self.patient, slot=self.slots[0])

    def test_non_patients_cannot_book(self):
        with self.assertRaises(PermissionDenied):
            book_slot(patient=self.doctor_user, slot=self.slots[0])

    def test_cancel_within_two_hours_is_rejected(self):
        soon = timezone.localtime() + timedelta(hours=1)
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            slot=None,
            date=soon.date(),
            start_time=soon.time().replace(second=0, microsecond=0),
            end_time=(soon + timedelta(minutes=30)).time().replace(second=0, microsecond=0),
        )

        with self.assertRaises(ValidationError):
            cancel_appointment(appointment=appointment, actor=self.patient, cancelled_by="patient")

    def test_cancel_someone_elses_appointment_is_denied(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])

        with self.assertRaises(PermissionDenied):
            cancel_appointment(
                appointment=appointment, actor=self.other_patient, cancelled_by="patient"
            )

    def test_doctor_cannot_cancel_another_doctors_appointment(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])
        other_user = User.objects.create_user(
            email="doctor2@smartmed.test",
            password="MotDePasse123!",
            first_name="Leila",
            last_name="Trabelsi",
            role=User.Role.DOCTOR,
        )
        other_profile = DoctorProfile.objects.create(
            user=other_user,
            specialty=self.specialty,
            professional_number="TN-PED-2087",
        )

        with self.assertRaises(PermissionDenied):
            cancel_appointment(
                appointment=appointment,
                actor=other_user,
                cancelled_by="doctor",
            )
        self.assertEqual(other_profile.appointments.count(), 0)

    def test_reschedule_cancels_the_old_slot_and_books_the_new_one(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])

        new_appointment = reschedule_appointment(
            patient=self.patient, appointment=appointment, new_slot=self.slots[1]
        )

        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertEqual(new_appointment.status, Appointment.Status.PENDING)
        self.assertEqual(new_appointment.slot, self.slots[1])
        self.assertTrue(
            AuditLog.objects.filter(event=AuditLog.Event.APPOINTMENT_RESCHEDULED).exists()
        )

    def test_doctor_confirm_and_complete_flow(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])

        set_doctor_status(
            appointment=appointment,
            doctor_profile=self.doctor,
            new_status=Appointment.Status.CONFIRMED,
            actor=self.doctor_user,
        )
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)
        self.assertTrue(
            AuditLog.objects.filter(event=AuditLog.Event.APPOINTMENT_CONFIRMED).exists()
        )

        set_doctor_status(
            appointment=appointment,
            doctor_profile=self.doctor,
            new_status=Appointment.Status.COMPLETED,
            actor=self.doctor_user,
        )
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)

    def test_completing_a_pending_appointment_is_rejected(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])

        with self.assertRaises(ValidationError):
            set_doctor_status(
                appointment=appointment,
                doctor_profile=self.doctor,
                new_status=Appointment.Status.COMPLETED,
                actor=self.doctor_user,
            )

    def test_history_survives_slot_deletion(self):
        appointment = book_slot(patient=self.patient, slot=self.slots[0])
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status"])
        self.slots[0].delete()

        appointment.refresh_from_db()
        self.assertIsNone(appointment.slot_id)
        self.assertEqual(appointment.date, self.tomorrow)
        self.assertEqual(appointment.start_time, time(9, 0))


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AppointmentViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.other_patient = User.objects.create_user(
            email="patient2@smartmed.test",
            password="MotDePasse123!",
            first_name="Nour",
            last_name="Jaziri",
        )
        cls.admin = User.objects.create_user(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
            role=User.Role.ADMIN,
        )
        cls.doctor_user = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.doctor = DoctorProfile.objects.create(
            user=cls.doctor_user,
            specialty=cls.specialty,
            professional_number="TN-CARD-1042",
        )

        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        WeeklyAvailability.objects.create(
            doctor=cls.doctor,
            weekday=cls.tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        generate_availability(cls.doctor, days=2, start_date=cls.tomorrow)
        cls.slots = list(cls.doctor.slots.filter(date=cls.tomorrow).order_by("start_time"))

    def _book(self, slot, patient=None):
        return book_slot(patient=patient or self.patient, slot=slot)

    def test_patient_can_book_through_the_view(self):
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse("appointments:book_entry"),
            {"slot_id": self.slots[0].pk, "doctor": self.doctor.pk, "reason": "Contrôle"},
        )

        self.assertRedirects(response, reverse("appointments:appointment_list"))
        appointment = Appointment.objects.get(slot=self.slots[0])
        self.assertEqual(appointment.patient, self.patient)
        self.assertEqual(appointment.reason, "Contrôle")

    def test_booking_an_already_taken_slot_shows_an_error(self):
        self._book(self.slots[0])
        self.client.force_login(self.other_patient)

        response = self.client.post(
            reverse("appointments:book_entry"),
            {"slot_id": self.slots[0].pk, "doctor": self.doctor.pk},
            follow=True,
        )

        self.assertContains(response, "être réservé")
        self.assertEqual(Appointment.objects.filter(slot=self.slots[0]).count(), 1)

    def test_booking_an_unknown_slot_shows_an_error(self):
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse("appointments:book_entry"),
            {"slot_id": "999999", "doctor": self.doctor.pk},
            follow=True,
        )

        self.assertContains(response, "Ce créneau n&#x27;existe plus.")
        self.assertEqual(Appointment.objects.count(), 0)

    def test_doctor_role_cannot_book(self):
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("appointments:book_entry"))

        self.assertEqual(response.status_code, 403)

    def test_appointment_list_splits_upcoming_and_past(self):
        upcoming = self._book(self.slots[0])
        cancelled = self._book(self.slots[1])
        cancel_appointment(appointment=cancelled, actor=self.patient, cancelled_by="patient")
        self.client.force_login(self.patient)

        response = self.client.get(reverse("appointments:appointment_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dr Amine Ben Salah")
        upcoming_ids = [a.pk for a in response.context["upcoming_appointments"]]
        self.assertIn(upcoming.pk, upcoming_ids)
        self.assertNotIn(cancelled.pk, upcoming_ids)
        past_ids = [a.pk for a in response.context["past_appointments"]]
        self.assertIn(cancelled.pk, past_ids)

    def test_patient_cancels_through_the_view(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse("appointments:appointment_cancel", args=[appointment.pk])
        )

        self.assertRedirects(response, reverse("appointments:appointment_list"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertEqual(len(mail.outbox), 3)  # booking (2) + doctor cancellation notice

    def test_patient_cannot_cancel_someone_elses_appointment(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.other_patient)

        response = self.client.post(
            reverse("appointments:appointment_cancel", args=[appointment.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_patient_reschedules_through_the_view(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.patient)

        response = self.client.post(
            reverse("appointments:appointment_reschedule", args=[appointment.pk]),
            {"slot_id": self.slots[1].pk},
        )

        self.assertRedirects(response, reverse("appointments:appointment_list"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertTrue(Appointment.objects.filter(slot=self.slots[1]).exists())

    def test_reschedule_page_renders_free_slots(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.patient)

        response = self.client.get(
            reverse("appointments:appointment_reschedule", args=[appointment.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Déplacer mon rendez-vous")
        self.assertNotContains(response, f'value="{self.slots[0].pk}"')
        self.assertContains(response, f'value="{self.slots[1].pk}"')

    def test_doctor_agenda_shows_only_own_appointments(self):
        own = self._book(self.slots[0])
        other = self._book(self.slots[1], patient=self.other_patient)
        self.client.force_login(self.doctor_user)

        response = self.client.get(reverse("doctor_agenda"))

        self.assertEqual(response.status_code, 200)
        shown = [a.pk for a in response.context["upcoming_appointments"]]
        self.assertCountEqual(shown, [own.pk, other.pk])
        self.assertEqual(response.context["pending_count"], 2)

    def test_patient_cannot_open_the_doctor_agenda(self):
        self.client.force_login(self.patient)

        response = self.client.get(reverse("doctor_agenda"))

        self.assertEqual(response.status_code, 403)

    def test_doctor_confirms_and_completes_through_the_view(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("doctor_appointment_action", args=[appointment.pk, "confirm"])
        )
        self.assertRedirects(response, reverse("doctor_agenda"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CONFIRMED)

        response = self.client.post(
            reverse("doctor_appointment_action", args=[appointment.pk, "complete"])
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)

    def test_doctor_cannot_act_on_another_doctors_appointment(self):
        appointment = self._book(self.slots[0])
        other_user = User.objects.create_user(
            email="doctor2@smartmed.test",
            password="MotDePasse123!",
            first_name="Leila",
            last_name="Trabelsi",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=other_user,
            specialty=self.specialty,
            professional_number="TN-PED-2087",
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("doctor_appointment_action", args=[appointment.pk, "confirm"])
        )

        self.assertEqual(response.status_code, 404)

    def test_unknown_action_is_rejected(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.doctor_user)

        response = self.client.post(
            reverse("doctor_appointment_action", args=[appointment.pk, "delete"])
        )

        self.assertEqual(response.status_code, 403)

    def test_cancelling_as_doctor_frees_the_slot(self):
        appointment = self._book(self.slots[0])
        self.client.force_login(self.doctor_user)
        self.client.post(reverse("doctor_appointment_action", args=[appointment.pk, "cancel"]))

        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        rebooked = book_slot(patient=self.other_patient, slot=self.slots[0])
        self.assertEqual(rebooked.patient, self.other_patient)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ReminderCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.doctor_user = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.doctor = DoctorProfile.objects.create(
            user=cls.doctor_user,
            specialty=cls.specialty,
            professional_number="TN-CARD-1042",
        )
        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        WeeklyAvailability.objects.create(
            doctor=cls.doctor,
            weekday=cls.tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        generate_availability(cls.doctor, days=3, start_date=cls.tomorrow)

    def test_reminders_are_sent_once_for_confirmed_appointments(self):
        slot = self.doctor.slots.filter(date=self.tomorrow).first()
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            slot=slot,
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=Appointment.Status.CONFIRMED,
        )

        from django.core.management import call_command

        call_command("send_reminders")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.patient.email])
        self.assertIn("Rappel", mail.outbox[0].subject)

        appointment.refresh_from_db()
        self.assertIsNotNone(appointment.reminder_sent_at)

        call_command("send_reminders")
        self.assertEqual(len(mail.outbox), 1)

    def test_pending_appointments_get_no_reminder(self):
        slot = self.doctor.slots.filter(date=self.tomorrow).first()
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            slot=slot,
            date=slot.date,
            start_time=slot.start_time,
            end_time=slot.end_time,
            status=Appointment.Status.PENDING,
        )

        from django.core.management import call_command

        call_command("send_reminders")
        self.assertEqual(len(mail.outbox), 0)


class PatientAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.doctor_user = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )

    def test_admin_sees_the_patient_list(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("patient_admin_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sami Khelifi")
        self.assertContains(response, "patient@smartmed.test")

    def test_search_filters_the_patient_list(self):
        User.objects.create_user(
            email="autre@smartmed.test",
            password="MotDePasse123!",
            first_name="Nour",
            last_name="Jaziri",
            role=User.Role.PATIENT,
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("patient_admin_list"), {"q": "khelifi"})

        self.assertContains(response, "Sami Khelifi")
        self.assertNotContains(response, "Nour Jaziri")

    def test_non_admin_roles_are_denied(self):
        for user in (self.patient, self.doctor_user):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                response = self.client.get(reverse("patient_admin_list"))
                self.assertEqual(response.status_code, 403)
                self.client.logout()

    def test_toggle_deactivates_and_blocks_login(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("patient_toggle_status", args=[self.patient.pk]))

        self.assertRedirects(response, reverse("patient_admin_list"))
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                event=AuditLog.Event.PATIENT_STATUS_CHANGED, target_user=self.patient
            ).exists()
        )

        self.client.logout()
        login = self.client.post(
            reverse("accounts:login"),
            {"username": "patient@smartmed.test", "password": "MotDePasse123!"},
        )
        self.assertEqual(login.status_code, 200)  # form re-rendered, not logged in

    def test_toggle_reactivates(self):
        self.patient.is_active = False
        self.patient.save(update_fields=["is_active"])
        self.client.force_login(self.admin)

        self.client.post(reverse("patient_toggle_status", args=[self.patient.pk]))

        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

    def test_toggle_requires_post(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("patient_toggle_status", args=[self.patient.pk]))

        self.assertEqual(response.status_code, 405)

    def test_toggle_refuses_doctor_accounts(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("patient_toggle_status", args=[self.doctor_user.pk]))

        self.assertEqual(response.status_code, 404)
