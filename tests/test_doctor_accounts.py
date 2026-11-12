from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditLog, User
from doctors.models import DoctorProfile, Specialty


class DoctorAccountCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiology = Specialty.objects.create(name="Cardiologie")
        cls.inactive_specialty = Specialty.objects.create(name="Urgences", is_active=False)
        cls.admin = User.objects.create_user(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        cls.payload = {
            "first_name": "Rania",
            "last_name": "Nejjar",
            "email": "rania.nejjar@smartmed.test",
            "specialty": cls.cardiology.pk,
            "professional_number": "TN-CARD-7788",
            "bio": "Cardiologue interventionnelle.",
            "consultation_duration": 30,
            "password1": "MotDePasse123!",
            "password2": "MotDePasse123!",
        }

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_creates_a_doctor_account_and_profile(self):
        response = self.client.post(reverse("doctor_create"), self.payload)

        self.assertRedirects(response, reverse("admin_dashboard"))
        doctor = User.objects.get(email="rania.nejjar@smartmed.test")
        self.assertEqual(doctor.role, User.Role.DOCTOR)
        self.assertFalse(doctor.is_staff)
        self.assertFalse(doctor.is_superuser)

        profile = DoctorProfile.objects.get(user=doctor)
        self.assertEqual(profile.specialty, self.cardiology)
        self.assertEqual(profile.professional_number, "TN-CARD-7788")

        entry = AuditLog.objects.get(event=AuditLog.Event.DOCTOR_ACCOUNT_CREATED)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.target_user, doctor)
        self.assertEqual(entry.metadata["professional_number"], "TN-CARD-7788")

    def test_new_doctor_can_log_in_and_reaches_the_doctor_dashboard(self):
        self.client.post(reverse("doctor_create"), self.payload)
        self.client.logout()

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "rania.nejjar@smartmed.test", "password": "MotDePasse123!"},
        )

        self.assertRedirects(response, reverse("doctor_dashboard"))

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            email="rania.nejjar@smartmed.test",
            password="MotDePasse123!",
            first_name="Autre",
            last_name="Personne",
        )

        response = self.client.post(reverse("doctor_create"), self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un compte existe déjà avec cette adresse e-mail.")

    def test_duplicate_professional_number_is_rejected(self):
        DoctorProfile.objects.create(
            user=User.objects.create_user(
                email="existing.doctor@smartmed.test",
                password="MotDePasse123!",
                first_name="Existant",
                last_name="Médecin",
                role=User.Role.DOCTOR,
            ),
            specialty=self.cardiology,
            professional_number="TN-CARD-7788",
        )

        response = self.client.post(reverse("doctor_create"), self.payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ce numéro professionnel est déjà utilisé.")

    def test_inactive_specialties_are_not_proposed(self):
        response = self.client.get(reverse("doctor_create"))

        self.assertNotContains(response, "Urgences")

        invalid_payload = {**self.payload, "specialty": self.inactive_specialty.pk}
        response = self.client.post(reverse("doctor_create"), invalid_payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["specialty"])

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("doctor_create"),
            {**self.payload, "password1": "12345678", "password2": "12345678"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["password1"])
        self.assertFalse(User.objects.filter(email=self.payload["email"]).exists())

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(
            reverse("doctor_create"),
            {**self.payload, "password2": "AutreMotDePasse456!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les deux mots de passe ne correspondent pas.")
