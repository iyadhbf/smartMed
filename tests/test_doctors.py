from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from doctors.models import DoctorProfile, Specialty


def make_doctor(email, specialty, *, order=0, is_active=True, user_is_active=True):
    user = User.objects.create_user(
        email=email,
        password="MotDePasse123!",
        first_name="Prénom",
        last_name="Nom",
        role=User.Role.DOCTOR,
        is_active=user_is_active,
    )
    return DoctorProfile.objects.create(
        user=user,
        specialty=specialty,
        professional_number=f"TN-{DoctorProfile.objects.count() + 1:04d}",
        display_order=order,
        is_active=is_active,
    )


class SpecialtyModelTests(TestCase):
    def test_slug_is_generated_from_name(self):
        specialty = Specialty.objects.create(name="Médecine générale")

        self.assertEqual(specialty.slug, "medecine-generale")

    def test_existing_slug_is_preserved(self):
        specialty = Specialty.objects.create(name="Pédiatrie", slug="pediatrie-enfant")

        self.assertEqual(specialty.slug, "pediatrie-enfant")


class DoctorListApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiology = Specialty.objects.create(name="Cardiologie", display_order=1)
        cls.pediatrics = Specialty.objects.create(name="Pédiatrie", display_order=2)
        cls.emergency = Specialty.objects.create(
            name="Urgences", is_bookable=False, display_order=3
        )
        cls.inactive_specialty = Specialty.objects.create(
            name="Ancienne spécialité", is_active=False, display_order=4
        )

        cls.second = make_doctor("second@smartmed.test", cls.cardiology, order=2)
        cls.first = make_doctor("first@smartmed.test", cls.cardiology, order=1)
        cls.inactive_doctor = make_doctor(
            "inactive@smartmed.test", cls.cardiology, order=0, is_active=False
        )
        cls.inactive_user = make_doctor(
            "closed@smartmed.test", cls.cardiology, order=0, user_is_active=False
        )
        cls.pediatrician = make_doctor("pediatre@smartmed.test", cls.pediatrics)
        cls.emergency_doctor = make_doctor("urgences@smartmed.test", cls.emergency)
        cls.legacy_doctor = make_doctor("legacy@smartmed.test", cls.inactive_specialty)

    def test_returns_active_doctors_of_a_bookable_specialty(self):
        response = self.client.get(reverse("doctors:api_list"), {"specialty": self.cardiology.pk})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([row["id"] for row in payload["doctors"]], [self.first.pk, self.second.pk])
        self.assertEqual(payload["doctors"][0]["name"], "Dr Prénom Nom")
        self.assertEqual(payload["doctors"][0]["specialty"], "Cardiologie")
        self.assertIsNone(payload["doctors"][0]["photo"])

    def test_excludes_inactive_doctors_and_users(self):
        response = self.client.get(reverse("doctors:api_list"), {"specialty": self.cardiology.pk})

        ids = {row["id"] for row in response.json()["doctors"]}
        self.assertNotIn(self.inactive_doctor.pk, ids)
        self.assertNotIn(self.inactive_user.pk, ids)

    def test_excludes_non_bookable_and_inactive_specialties(self):
        for specialty in (self.emergency, self.inactive_specialty):
            response = self.client.get(reverse("doctors:api_list"), {"specialty": specialty.pk})
            self.assertEqual(response.json(), {"doctors": []})

    def test_missing_or_invalid_specialty_returns_empty_list(self):
        for params in ({}, {"specialty": "abc"}, {"specialty": ""}):
            response = self.client.get(reverse("doctors:api_list"), params)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"doctors": []})

    def test_post_is_not_allowed(self):
        response = self.client.post(reverse("doctors:api_list"), {"specialty": self.cardiology.pk})

        self.assertEqual(response.status_code, 405)
