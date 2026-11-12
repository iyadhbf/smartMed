from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from doctors.models import DoctorProfile, Specialty
from patients.models import PatientProfile


class PatientProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.profile = PatientProfile.objects.create(
            user=cls.patient,
            birth_date="1988-03-14",
            phone="+216 20 000 001",
        )

    def setUp(self):
        self.client.force_login(self.patient)

    def test_profile_shows_patient_fields(self):
        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Date de naissance")
        self.assertContains(response, "Téléphone")
        self.assertContains(response, "patient@smartmed.test")

    def test_profile_form_is_prefilled_with_existing_values(self):
        response = self.client.get(reverse("accounts:profile"))

        form = response.context["form"]
        self.assertEqual(form.initial["first_name"], "Sami")
        self.assertEqual(form.initial["last_name"], "Khelifi")
        self.assertEqual(form.initial["birth_date"].isoformat(), "1988-03-14")
        self.assertEqual(form.initial["phone"], "+216 20 000 001")

    def test_patient_can_update_personal_information(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Samuel",
                "last_name": "Khelifi",
                "birth_date": "1990-06-20",
                "phone": "+216 20 999 888",
            },
        )

        self.assertRedirects(response, reverse("accounts:profile"))
        self.patient.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.patient.first_name, "Samuel")
        self.assertEqual(self.profile.birth_date.isoformat(), "1990-06-20")
        self.assertEqual(self.profile.phone, "+216 20 999 888")

    def test_patient_cannot_change_email_or_role_through_the_profile_form(self):
        self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Sami",
                "last_name": "Khelifi",
                "birth_date": "1988-03-14",
                "phone": "+216 20 000 001",
                "email": "attacker@smartmed.test",
                "role": User.Role.ADMIN,
            },
        )

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.email, "patient@smartmed.test")
        self.assertEqual(self.patient.role, User.Role.PATIENT)

    def test_future_birth_date_is_rejected(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Sami",
                "last_name": "Khelifi",
                "birth_date": "2099-01-01",
                "phone": "+216 20 000 001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La date de naissance ne peut pas être dans le futur.")


class DoctorProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.specialty = Specialty.objects.create(name="Cardiologie")
        cls.doctor = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.profile = DoctorProfile.objects.create(
            user=cls.doctor,
            specialty=cls.specialty,
            professional_number="TN-CARD-1042",
            bio="Présentation initiale.",
        )

    def test_doctor_profile_shows_professional_information(self):
        self.client.force_login(self.doctor)

        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, "Cardiologie")
        self.assertContains(response, "TN-CARD-1042")
        self.assertContains(response, "Présentation")

    def test_doctor_can_update_name_and_bio(self):
        self.client.force_login(self.doctor)

        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Amine",
                "last_name": "Ben Salah",
                "bio": "Nouvelle présentation professionnelle.",
            },
        )

        self.assertRedirects(response, reverse("accounts:profile"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Nouvelle présentation professionnelle.")


class AdminProfileTests(TestCase):
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

    def test_admin_can_update_their_name(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:profile"),
            {"first_name": "Amira", "last_name": "Zouari Ben Ali"},
        )

        self.assertRedirects(response, reverse("accounts:profile"))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.last_name, "Zouari Ben Ali")
