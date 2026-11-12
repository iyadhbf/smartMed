from django.test import TestCase
from django.urls import reverse

from accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_defaults_to_patient_role(self):
        user = User.objects.create_user(
            email="patient@example.tn",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )

        self.assertEqual(user.email, "patient@example.tn")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(user.check_password("MotDePasse123!"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_requires_email(self):
        with self.assertRaisesMessage(ValueError, "adresse e-mail"):
            User.objects.create_user(
                email="",
                password="MotDePasse123!",
                first_name="Sami",
                last_name="Khelifi",
            )

    def test_create_superuser_gets_admin_role(self):
        admin = User.objects.create_superuser(
            email="admin@example.tn",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
        )

        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_full_name_and_initials(self):
        user = User(
            email="leila.trabelsi@example.tn",
            first_name="Leïla",
            last_name="Trabelsi",
        )

        self.assertEqual(user.full_name, "Leïla Trabelsi")
        self.assertEqual(user.initials, "LT")
        self.assertEqual(str(user), "Leïla Trabelsi")

    def test_role_properties(self):
        doctor = User(role=User.Role.DOCTOR)
        patient = User(role=User.Role.PATIENT)

        self.assertTrue(doctor.is_doctor)
        self.assertFalse(doctor.is_patient)
        self.assertTrue(patient.is_patient)
        self.assertFalse(patient.is_doctor)


class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="patient@example.tn",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )

    def test_login_page_uses_email_field(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="email"')
        self.assertContains(response, "Adresse e-mail")
        self.assertContains(response, "Mot de passe")

    def test_login_with_email_succeeds(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "patient@example.tn", "password": "MotDePasse123!"},
        )

        self.assertRedirects(response, reverse("patient_dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "patient@example.tn", "password": "MauvaisMotDePasse"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertTrue(response.context["form"].non_field_errors())

    def test_authenticated_user_is_redirected_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:login"))

        self.assertRedirects(response, reverse("patient_dashboard"))

    def test_logout_only_accepts_post(self):
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("accounts:logout"))
        post_response = self.client.post(reverse("accounts:logout"))

        self.assertEqual(get_response.status_code, 405)
        self.assertRedirects(post_response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)
