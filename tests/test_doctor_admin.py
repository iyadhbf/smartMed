from datetime import time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, User
from doctors.models import DoctorProfile, Specialty, WeeklyAvailability
from doctors.services import generate_availability


def create_doctor(email, first_name, last_name, specialty, number, **profile_fields):
    user = User.objects.create_user(
        email=email,
        password="MotDePasse123!",
        first_name=first_name,
        last_name=last_name,
        role=User.Role.DOCTOR,
    )
    return DoctorProfile.objects.create(
        user=user,
        specialty=specialty,
        professional_number=number,
        **profile_fields,
    )


class DoctorAdminTests(TestCase):
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
            role=User.Role.PATIENT,
        )
        cls.cardiology = Specialty.objects.create(name="Cardiologie")
        cls.pediatrics = Specialty.objects.create(name="Pédiatrie")
        cls.doctor = create_doctor(
            "amine.bensalah@smartmed.test",
            "Amine",
            "Ben Salah",
            cls.cardiology,
            "TN-CARD-1042",
            bio="Cardiologue.",
            consultation_duration=30,
        )
        cls.inactive_doctor = create_doctor(
            "leila.trabelsi@smartmed.test",
            "Leïla",
            "Trabelsi",
            cls.pediatrics,
            "TN-PED-2087",
            is_active=False,
        )
        cls.inactive_doctor.user.is_active = False
        cls.inactive_doctor.user.save(update_fields=["is_active"])

    def setUp(self):
        self.client.force_login(self.admin)

    def test_patient_cannot_manage_doctors(self):
        self.client.force_login(self.patient)

        for url in (
            reverse("doctor_admin_list"),
            reverse("doctor_edit", args=[self.doctor.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)

        toggle = self.client.post(reverse("doctor_toggle_status", args=[self.doctor.pk]))
        self.assertEqual(toggle.status_code, 403)
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.is_active)

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("doctor_admin_list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('doctor_admin_list')}",
        )

    def test_list_searches_by_name_email_and_professional_number(self):
        for query, expected, hidden in (
            ("amine", "Amine Ben Salah", "Leïla Trabelsi"),
            ("leila.trabelsi", "Leïla Trabelsi", "Amine Ben Salah"),
            ("TN-CARD", "Amine Ben Salah", "Leïla Trabelsi"),
        ):
            response = self.client.get(reverse("doctor_admin_list"), {"q": query})
            self.assertContains(response, expected)
            self.assertNotContains(response, hidden)

    def test_list_filters_by_specialty_and_status(self):
        by_specialty = self.client.get(
            reverse("doctor_admin_list"), {"specialty": self.pediatrics.pk}
        )
        self.assertContains(by_specialty, "Leïla Trabelsi")
        self.assertNotContains(by_specialty, "Amine Ben Salah")

        inactive = self.client.get(reverse("doctor_admin_list"), {"status": "inactive"})
        self.assertContains(inactive, "Leïla Trabelsi")
        self.assertNotContains(inactive, "Amine Ben Salah")

        active = self.client.get(reverse("doctor_admin_list"), {"status": "active"})
        self.assertContains(active, "Amine Ben Salah")
        self.assertNotContains(active, "Leïla Trabelsi")

    def test_admin_updates_doctor_information_and_audits_it(self):
        response = self.client.post(
            reverse("doctor_edit", args=[self.doctor.pk]),
            {
                "first_name": "Amine",
                "last_name": "Ben Salah",
                "email": "amine.bensalah@smartmed.test",
                "specialty": self.cardiology.pk,
                "professional_number": "TN-CARD-1042",
                "bio": "Cardiologue interventionnelle.",
                "consultation_duration": 45,
            },
        )

        self.assertRedirects(response, reverse("doctor_admin_list"))
        self.doctor.refresh_from_db()
        self.doctor.user.refresh_from_db()
        self.assertEqual(self.doctor.consultation_duration, 45)
        self.assertEqual(self.doctor.bio, "Cardiologue interventionnelle.")
        self.assertEqual(self.doctor.user.full_name, "Amine Ben Salah")

        entry = AuditLog.objects.get(event=AuditLog.Event.DOCTOR_UPDATED)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.target_user, self.doctor.user)
        self.assertEqual(entry.metadata["consultation_duration"], 45)

    def test_changing_duration_rebuilds_future_slots(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        WeeklyAvailability.objects.create(
            doctor=self.doctor,
            weekday=tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        generate_availability(self.doctor, days=2, start_date=tomorrow)
        self.assertEqual(self.doctor.slots.filter(date=tomorrow).count(), 4)

        self.client.post(
            reverse("doctor_edit", args=[self.doctor.pk]),
            {
                "first_name": "Amine",
                "last_name": "Ben Salah",
                "email": "amine.bensalah@smartmed.test",
                "specialty": self.cardiology.pk,
                "professional_number": "TN-CARD-1042",
                "bio": "Cardiologue.",
                "consultation_duration": 45,
            },
        )

        slots = list(
            self.doctor.slots.filter(date=tomorrow)
            .order_by("start_time")
            .values_list("start_time", "end_time")
        )
        self.assertEqual(
            slots,
            [(time(9, 0), time(9, 45)), (time(9, 45), time(10, 30))],
        )

    def test_duplicate_email_and_professional_number_are_rejected(self):
        response = self.client.post(
            reverse("doctor_edit", args=[self.doctor.pk]),
            {
                "first_name": "Amine",
                "last_name": "Ben Salah",
                "email": "leila.trabelsi@smartmed.test",
                "specialty": self.cardiology.pk,
                "professional_number": "TN-PED-2087",
                "bio": "",
                "consultation_duration": 30,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un compte existe déjà avec cette adresse e-mail.")
        self.assertContains(response, "Ce numéro professionnel est déjà utilisé.")

    def test_deactivation_hides_the_doctor_and_preserves_history(self):
        response = self.client.post(reverse("doctor_toggle_status", args=[self.doctor.pk]))

        self.assertRedirects(response, reverse("doctor_admin_list"))
        self.doctor.refresh_from_db()
        self.doctor.user.refresh_from_db()
        self.assertFalse(self.doctor.is_active)
        self.assertFalse(self.doctor.user.is_active)

        self.assertEqual(
            DoctorProfile.objects.get(pk=self.doctor.pk).professional_number,
            "TN-CARD-1042",
        )
        self.assertEqual(
            self.client.get(reverse("doctor_public", args=[self.doctor.pk])).status_code, 404
        )
        self.assertNotContains(self.client.get(reverse("doctor_directory")), "Amine Ben Salah")

        entry = AuditLog.objects.filter(event=AuditLog.Event.DOCTOR_STATUS_CHANGED).first()
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.metadata["is_active"], False)

    def test_reactivation_restores_access_and_visibility(self):
        self.doctor.is_active = False
        self.doctor.user.is_active = False
        self.doctor.user.save(update_fields=["is_active"])
        self.doctor.save(update_fields=["is_active"])

        self.client.post(reverse("doctor_toggle_status", args=[self.doctor.pk]))

        self.doctor.refresh_from_db()
        self.doctor.user.refresh_from_db()
        self.assertTrue(self.doctor.is_active)
        self.assertTrue(self.doctor.user.is_active)
        self.assertContains(self.client.get(reverse("doctor_directory")), "Amine Ben Salah")

    def test_list_is_paginated(self):
        for index in range(11):
            create_doctor(
                f"doctor{index}@smartmed.test",
                "Prénom",
                f"Médecin {index:02d}",
                self.cardiology,
                f"TN-TEST-{index:04d}",
            )

        first_page = self.client.get(reverse("doctor_admin_list"))
        second_page = self.client.get(reverse("doctor_admin_list"), {"page": 2})

        self.assertEqual(len(first_page.context["doctors"]), 10)
        self.assertEqual(len(second_page.context["doctors"]), 3)
