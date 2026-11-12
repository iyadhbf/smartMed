from datetime import time

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from doctors.models import DoctorProfile, Specialty, WeeklyAvailability
from doctors.services import generate_availability
from tests.test_availability import next_weekday


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


class DoctorDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiology = Specialty.objects.create(name="Cardiologie", display_order=1)
        cls.pediatrics = Specialty.objects.create(name="Pédiatrie", display_order=2)
        cls.hidden_specialty = Specialty.objects.create(name="Urgences", is_active=False)
        cls.amine = create_doctor(
            "amine@smartmed.test", "Amine", "Ben Salah", cls.cardiology, "TN-CARD-0001"
        )
        cls.leila = create_doctor(
            "leila@smartmed.test", "Leïla", "Trabelsi", cls.pediatrics, "TN-PED-0002"
        )
        cls.inactive = create_doctor(
            "inactive@smartmed.test",
            "Karim",
            "Haddad",
            cls.cardiology,
            "TN-CARD-0003",
            is_active=False,
        )
        cls.inactive.user.is_active = False
        cls.inactive.user.save(update_fields=["is_active"])
        cls.hidden = create_doctor(
            "hidden@smartmed.test", "Sonia", "Mansour", cls.hidden_specialty, "TN-URG-0004"
        )

    def test_directory_lists_only_public_doctors(self):
        response = self.client.get(reverse("doctor_directory"))

        self.assertContains(response, "Amine Ben Salah")
        self.assertContains(response, "Leïla Trabelsi")
        self.assertNotContains(response, "Karim Haddad")
        self.assertNotContains(response, "Sonia Mansour")

    def test_search_by_full_or_partial_name_is_case_insensitive(self):
        response = self.client.get(reverse("doctor_directory"), {"q": "ben"})

        self.assertContains(response, "Amine Ben Salah")
        self.assertNotContains(response, "Leïla Trabelsi")

    def test_filter_by_specialty_slug_and_id(self):
        by_slug = self.client.get(reverse("doctor_directory"), {"specialty": "pediatrie"})
        self.assertContains(by_slug, "Leïla Trabelsi")
        self.assertNotContains(by_slug, "Amine Ben Salah")

        by_id = self.client.get(reverse("doctor_directory"), {"specialty": self.cardiology.pk})
        self.assertContains(by_id, "Amine Ben Salah")
        self.assertNotContains(by_id, "Leïla Trabelsi")

    def test_empty_result_shows_a_helpful_state(self):
        response = self.client.get(reverse("doctor_directory"), {"q": "introuvable"})

        self.assertContains(response, "Aucun médecin ne correspond")

    def test_directory_is_paginated(self):
        for index in range(9):
            create_doctor(
                f"extra{index}@smartmed.test",
                "Prénom",
                f"Supplémentaire {index:02d}",
                self.cardiology,
                f"TN-EXT-{index:04d}",
            )

        first_page = self.client.get(reverse("doctor_directory"))
        second_page = self.client.get(reverse("doctor_directory"), {"page": 2})

        self.assertEqual(len(first_page.context["doctors"]), 9)
        self.assertEqual(len(second_page.context["doctors"]), 2)

    def test_home_page_links_to_the_directory(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("doctor_directory"))


class DoctorPublicProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.doctor = create_doctor(
            "amine@smartmed.test",
            "Amine",
            "Ben Salah",
            cls.specialty,
            "TN-CARD-0001",
            bio="Cardiologue depuis douze ans.",
            consultation_duration=30,
        )

    def test_public_profile_shows_professional_information_and_slots(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        generate_availability(self.doctor, start_date=next_weekday(0), days=1)

        response = self.client.get(reverse("doctor_public", args=[self.doctor.pk]))

        self.assertContains(response, "Amine Ben Salah")
        self.assertContains(response, "Cardiologie")
        self.assertContains(response, "TN-CARD-0001")
        self.assertContains(response, "30 minutes")
        self.assertContains(response, "Cardiologue depuis douze ans.")
        self.assertContains(response, "09:00")
        self.assertContains(response, "09:30")

    def test_profile_without_schedule_shows_empty_state(self):
        response = self.client.get(reverse("doctor_public", args=[self.doctor.pk]))

        self.assertContains(response, "Aucun créneau n'est publié")

    def test_inactive_doctor_profile_returns_404(self):
        self.doctor.is_active = False
        self.doctor.save(update_fields=["is_active"])

        response = self.client.get(reverse("doctor_public", args=[self.doctor.pk]))

        self.assertEqual(response.status_code, 404)

    def test_profile_is_available_to_visitors(self):
        response = self.client.get(reverse("doctor_public", args=[self.doctor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["doctor"], self.doctor)
