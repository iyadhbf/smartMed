from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditLog, User


class LoginRedirectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        cls.doctor = User.objects.create_user(
            email="doctor@smartmed.test",
            password="MotDePasse123!",
            first_name="Amine",
            last_name="Ben Salah",
            role=User.Role.DOCTOR,
        )
        cls.admin = User.objects.create_user(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
            role=User.Role.ADMIN,
            is_staff=True,
        )

    def test_each_role_is_redirected_to_its_own_dashboard(self):
        cases = [
            (self.patient, "patient_dashboard"),
            (self.doctor, "doctor_dashboard"),
            (self.admin, "admin_dashboard"),
        ]
        for user, dashboard in cases:
            with self.subTest(role=user.role):
                self.client.logout()
                response = self.client.post(
                    reverse("accounts:login"),
                    {"username": user.email, "password": "MotDePasse123!"},
                )
                self.assertRedirects(response, reverse(dashboard))

    def test_safe_next_is_respected_after_login(self):
        booking_url = reverse("appointments:book_entry") + "?specialty=1&date=2026-11-05"

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "patient@smartmed.test",
                "password": "MotDePasse123!",
                "next": booking_url,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, booking_url)

    def test_external_next_is_ignored(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "patient@smartmed.test",
                "password": "MotDePasse123!",
                "next": "https://example.org/phishing",
            },
        )

        self.assertRedirects(response, reverse("patient_dashboard"))

    def test_inactive_account_cannot_log_in(self):
        self.patient.is_active = False
        self.patient.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("accounts:login"),
            {"username": "patient@smartmed.test", "password": "MotDePasse123!"},
        )

        # The same generic message is shown for unknown and inactive accounts, so the
        # form cannot be used to enumerate existing profiles.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adresse e-mail ou mot de passe incorrect.")
        self.assertNotIn("_auth_user_id", self.client.session)


class AuditTrailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )

    def test_successful_login_is_logged(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "patient@smartmed.test", "password": "MotDePasse123!"},
            HTTP_USER_AGENT="Mozilla/5.0 (SmartMedTests)",
        )

        entry = AuditLog.objects.get(event=AuditLog.Event.LOGIN_SUCCESS)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.target_user, self.user)
        self.assertEqual(entry.ip_address, "127.0.0.1")
        self.assertIn("SmartMedTests", entry.user_agent)

    def test_failed_login_is_logged_without_the_password(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "patient@smartmed.test", "password": "MauvaisMotDePasse"},
        )

        entry = AuditLog.objects.get(event=AuditLog.Event.LOGIN_FAILED)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.description, "patient@smartmed.test")
        self.assertNotIn("password", entry.metadata)
        self.assertNotIn("MauvaisMotDePasse", str(entry.metadata))

    def test_unknown_email_failure_is_logged_anonymously(self):
        self.client.post(
            reverse("accounts:login"),
            {"username": "inconnu@smartmed.test", "password": "MauvaisMotDePasse"},
        )

        entry = AuditLog.objects.get(event=AuditLog.Event.LOGIN_FAILED)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.description, "inconnu@smartmed.test")

    def test_logout_is_logged(self):
        self.client.force_login(self.user)

        self.client.post(reverse("accounts:logout"))

        entry = AuditLog.objects.get(event=AuditLog.Event.LOGOUT)
        self.assertEqual(entry.actor, self.user)

    def test_five_failures_lock_the_account_for_fifteen_minutes(self):
        url = reverse("accounts:login")
        credentials = {"username": "patient@smartmed.test", "password": "MauvaisMotDePasse"}

        for _ in range(4):
            response = self.client.post(url, credentials)
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, credentials)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")
        self.assertContains(response, "Connexion temporairement bloquée", status_code=429)
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.LOGIN_LOCKED_OUT).exists())

        blocked = self.client.post(
            url, {"username": "patient@smartmed.test", "password": "MotDePasse123!"}
        )
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)
