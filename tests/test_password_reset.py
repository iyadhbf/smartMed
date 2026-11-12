import re

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import AuditLog, User


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )

    def request_reset(self, email="patient@smartmed.test"):
        return self.client.post(reverse("accounts:password_reset"), {"email": email})

    def test_reset_request_sends_an_email_and_is_audited(self):
        response = self.request_reset()

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("mot de passe", mail.outbox[0].subject.lower())
        self.assertIn("patient@smartmed.test", mail.outbox[0].to)
        self.assertIn("/compte/reinitialiser/", mail.outbox[0].body)

        entry = AuditLog.objects.get(event=AuditLog.Event.PASSWORD_RESET_REQUESTED)
        self.assertEqual(entry.target_user, self.user)
        self.assertEqual(entry.description, "patient@smartmed.test")

    def test_unknown_email_does_not_reveal_account_existence(self):
        response = self.request_reset("inconnu@smartmed.test")

        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
        entry = AuditLog.objects.get(event=AuditLog.Event.PASSWORD_RESET_REQUESTED)
        self.assertIsNone(entry.target_user)

    def test_full_reset_flow_updates_the_password_and_is_audited(self):
        self.request_reset()
        body = mail.outbox[0].body
        match = re.search(r"http://testserver(/compte/reinitialiser/\S+)", body)
        self.assertIsNotNone(match)
        reset_path = match.group(1)

        response = self.client.get(reset_path, follow=True)
        self.assertEqual(response.status_code, 200)
        set_password_path = response.request["PATH_INFO"]
        self.assertTrue(set_password_path.endswith("/set-password/"))

        response = self.client.post(
            set_password_path,
            {"new_password1": "NouveauMotDePasse456!", "new_password2": "NouveauMotDePasse456!"},
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauMotDePasse456!"))
        self.assertTrue(
            AuditLog.objects.filter(event=AuditLog.Event.PASSWORD_RESET_COMPLETED).exists()
        )

    def test_invalid_token_shows_a_french_message(self):
        response = self.client.get(
            reverse(
                "accounts:password_reset_confirm",
                kwargs={"uidb64": "abc", "token": "def"},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalide ou a déjà été utilisé")

    def test_password_change_requires_the_current_password(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "MauvaisMotDePasse",
                "new_password1": "NouveauMotDePasse456!",
                "new_password2": "NouveauMotDePasse456!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Votre ancien mot de passe est incorrect")
        self.assertFalse(self.user.check_password("NouveauMotDePasse456!"))

    def test_password_change_updates_the_password_and_is_audited(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "MotDePasse123!",
                "new_password1": "NouveauMotDePasse456!",
                "new_password2": "NouveauMotDePasse456!",
            },
        )

        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NouveauMotDePasse456!"))
        entry = AuditLog.objects.get(event=AuditLog.Event.PASSWORD_CHANGED)
        self.assertEqual(entry.actor, self.user)
