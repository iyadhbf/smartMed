from urllib.parse import parse_qs, urlparse

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from doctors.models import DoctorProfile, Specialty, WeeklyAvailability
from doctors.services import generate_availability


class BookingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.other_specialty = Specialty.objects.create(name="Pédiatrie")
        cls.non_bookable = Specialty.objects.create(name="Urgences", is_bookable=False)

        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        doctor_user = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.doctor = DoctorProfile.objects.create(
            user=doctor_user,
            specialty=cls.specialty,
            professional_number="TN-CARD-1042",
        )
        cls.other_doctor = DoctorProfile.objects.create(
            user=User.objects.create_user(
                email="doctor2@smartmed.test",
                password="MotDePasse123!",
                first_name="Leila",
                last_name="Trabelsi",
                role=User.Role.DOCTOR,
            ),
            specialty=cls.other_specialty,
            professional_number="TN-PED-2087",
        )
        cls.emergency_doctor = DoctorProfile.objects.create(
            user=User.objects.create_user(
                email="doctor3@smartmed.test",
                password="MotDePasse123!",
                first_name="Karim",
                last_name="Haddad",
                role=User.Role.DOCTOR,
            ),
            specialty=cls.non_bookable,
            professional_number="TN-URG-0001",
        )

        inactive_user = User.objects.create_user(
            email="inactive@smartmed.test",
            password="MotDePasse123!",
            first_name="Nadia",
            last_name="Gharbi",
            role=User.Role.DOCTOR,
        )
        cls.inactive_doctor = DoctorProfile.objects.create(
            user=inactive_user,
            specialty=cls.specialty,
            professional_number="TN-CARD-9999",
            is_active=False,
        )

        from datetime import time, timedelta

        from django.utils import timezone

        cls.tomorrow = timezone.localdate() + timedelta(days=1)
        WeeklyAvailability.objects.create(
            doctor=cls.doctor,
            weekday=cls.tomorrow.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
        )
        generate_availability(cls.doctor, days=2, start_date=cls.tomorrow)

    def setUp(self):
        self.url = reverse("appointments:book_entry")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            self.url,
            {"specialty": self.specialty.pk, "doctor": self.doctor.pk, "date": "2026-11-05"},
        )

        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        self.assertEqual(parsed.path, reverse("accounts:login"))
        self.assertEqual(parse_qs(parsed.query)["next"], [response.wsgi_request.get_full_path()])

    def test_chooser_step_lists_bookable_specialties(self):
        self.client.force_login(self.patient)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cardiologie")
        self.assertContains(response, "Pédiatrie")
        self.assertNotContains(response, "Urgences")
        self.assertContains(response, "Choisir une spécialité d'abord")

    def test_specialty_is_preselected_in_the_chooser(self):
        self.client.force_login(self.patient)

        response = self.client.get(self.url, {"specialty": self.specialty.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.specialty.pk}" selected')

    def test_slot_step_is_rendered_for_a_valid_doctor(self):
        self.client.force_login(self.patient)

        response = self.client.get(self.url, {"doctor": self.doctor.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dr Amine Ben Salah")
        self.assertContains(response, "8 créneaux libres sur 14 jours")
        self.assertContains(response, 'name="slot_id"')
        self.assertContains(response, "Confirmer ma demande")

    def test_inactive_doctor_falls_back_to_the_chooser(self):
        self.client.force_login(self.patient)

        response = self.client.get(self.url, {"doctor": self.inactive_doctor.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir une spécialité d'abord")
        self.assertNotContains(response, "Dr Nadia Gharbi")

    def test_doctor_from_a_non_bookable_specialty_falls_back_to_the_chooser(self):
        self.client.force_login(self.patient)

        response = self.client.get(self.url, {"doctor": self.emergency_doctor.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir une spécialité d'abord")

    def test_invalid_identifiers_fall_back_to_the_chooser(self):
        self.client.force_login(self.patient)

        response = self.client.get(
            self.url, {"specialty": "abc", "doctor": "999999", "date": "pas-une-date"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisir une spécialité d'abord")

    def test_wanted_date_is_marked_on_the_matching_day(self):
        self.client.force_login(self.patient)

        response = self.client.get(
            self.url, {"doctor": self.doctor.pk, "date": self.tomorrow.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Date souhaitée")
