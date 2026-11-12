from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from patients.models import PatientProfile


class RegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse("accounts:register")
        cls.payload = {
            "first_name": "Inès",
            "last_name": "Ben Amor",
            "email": "ines.benamor@smartmed.test",
            "birth_date": "1999-04-12",
            "phone": "+216 20 111 222",
            "password1": "MotDePasse123!",
            "password2": "MotDePasse123!",
            "consent": "on",
        }

    def test_registration_creates_a_patient_account_and_profile(self):
        response = self.client.post(self.url, self.payload)

        self.assertRedirects(response, reverse("patient_dashboard"))
        user = User.objects.get(email="ines.benamor@smartmed.test")
        self.assertEqual(user.role, User.Role.PATIENT)
        self.assertTrue(user.check_password("MotDePasse123!"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

        profile = PatientProfile.objects.get(user=user)
        self.assertEqual(profile.birth_date.isoformat(), "1999-04-12")
        self.assertEqual(profile.phone, "+216 20 111 222")
        self.assertIsNotNone(profile.consent_given_at)

    def test_visitor_cannot_choose_the_doctor_role(self):
        payload = {**self.payload, "role": User.Role.DOCTOR}

        self.client.post(self.url, payload)

        user = User.objects.get(email="ines.benamor@smartmed.test")
        self.assertEqual(user.role, User.Role.PATIENT)

    def test_duplicate_email_is_rejected_in_french(self):
        User.objects.create_user(
            email="ines.benamor@smartmed.test",
            password="MotDePasse123!",
            first_name="Déjà",
            last_name="Inscrit",
        )
        payload = {**self.payload, "email": "Ines.BenAmor@SmartMed.test"}

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Un compte existe déjà avec cette adresse e-mail.")
        self.assertEqual(User.objects.filter(email__iexact=self.payload["email"]).count(), 1)

    def test_consent_is_required(self):
        payload = {**self.payload}
        payload.pop("consent")

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Vous devez accepter la politique de confidentialité pour créer un compte.",
        )
        self.assertFalse(User.objects.filter(email=self.payload["email"]).exists())

    def test_future_birth_date_is_rejected(self):
        response = self.client.post(self.url, {**self.payload, "birth_date": "2099-01-01"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La date de naissance ne peut pas être dans le futur.")

    def test_numeric_password_is_rejected(self):
        response = self.client.post(
            self.url,
            {**self.payload, "password1": "12345678", "password2": "12345678"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["password2"])
        self.assertFalse(User.objects.filter(email=self.payload["email"]).exists())

    def test_passwords_must_match(self):
        response = self.client.post(
            self.url,
            {**self.payload, "password2": "AutreMotDePasse123!"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Les deux mots de passe ne correspondent pas.")

    def test_safe_next_is_preserved_after_registration(self):
        booking_url = reverse("appointments:book_entry") + "?specialty=1"

        response = self.client.post(self.url, {**self.payload, "next": booking_url})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, booking_url)

    def test_external_next_is_ignored(self):
        response = self.client.post(
            self.url, {**self.payload, "next": "https://example.org/phishing"}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("patient_dashboard"))

    def test_authenticated_user_is_redirected_to_their_dashboard(self):
        user = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse("patient_dashboard"))

    def test_login_page_links_to_registration(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, reverse("accounts:register"))
        self.assertContains(response, "Créer un compte patient")
        self.assertContains(response, reverse("accounts:password_reset"))
