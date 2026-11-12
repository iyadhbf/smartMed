from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from config import views as config_views
from doctors.models import DoctorProfile, Specialty


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cardiology = Specialty.objects.create(
            name="Cardiologie", display_order=1, description="Le cœur."
        )
        cls.pediatrics = Specialty.objects.create(
            name="Pédiatrie", display_order=2, description="Les enfants."
        )
        cls.emergency = Specialty.objects.create(
            name="Urgences", display_order=3, is_bookable=False
        )
        cls.inactive = Specialty.objects.create(
            name="Ancienne spécialité", display_order=4, is_active=False
        )

        cls.doctors = []
        for index in range(4):
            user = User.objects.create_user(
                email=f"doctor{index}@smartmed.test",
                password="MotDePasse123!",
                first_name=f"Prénom{index}",
                last_name="Nom",
                role=User.Role.DOCTOR,
            )
            cls.doctors.append(
                DoctorProfile.objects.create(
                    user=user,
                    specialty=cls.cardiology if index < 3 else cls.pediatrics,
                    professional_number=f"TN-{index:04d}",
                    display_order=index,
                )
            )

    def test_home_page_renders(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, "Votre santé")
        self.assertContains(response, "Nos départements")
        self.assertContains(response, "Nos médecins")
        self.assertContains(response, "Comment ça marche")

    def test_departments_include_active_non_bookable_specialties(self):
        response = self.client.get(reverse("home"))

        specialties = list(response.context["specialties"])
        self.assertIn(self.emergency, specialties)
        self.assertNotIn(self.inactive, specialties)

    def test_booking_select_excludes_non_bookable_and_empty_specialties(self):
        response = self.client.get(reverse("home"))

        booking_specialties = set(response.context["booking_specialties"])
        self.assertEqual(booking_specialties, {self.cardiology, self.pediatrics})

    def test_booking_select_excludes_specialty_without_active_doctor(self):
        self.pediatrics.doctors.update(is_active=False)

        response = self.client.get(reverse("home"))

        self.assertNotIn(self.pediatrics, response.context["booking_specialties"])

    def test_doctors_preview_is_limited_to_three(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(len(response.context["doctors"]), 3)

    def test_booking_form_targets_booking_entry(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, reverse("appointments:book_entry"))
        self.assertContains(response, reverse("doctors:api_list"))

    def test_today_is_exposed_for_the_date_input(self):
        response = self.client.get(reverse("home"))

        self.assertRegex(response.context["today"], r"^\d{4}-\d{2}-\d{2}$")


class StaticPageTests(TestCase):
    def test_privacy_page_renders(self):
        response = self.client.get(reverse("privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Politique de confidentialité")
        self.assertContains(response, "INPDP")

    def test_legal_page_renders(self):
        response = self.client.get(reverse("legal"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mentions légales")


class ErrorPageTests(TestCase):
    @override_settings(DEBUG=False)
    def test_unknown_url_uses_custom_404(self):
        response = self.client.get("/page-introuvable/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page introuvable", status_code=404)
        self.assertContains(response, "Retour à l'accueil", status_code=404)

    def test_403_handler(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        response = config_views.handler403(request)

        self.assertEqual(response.status_code, 403)

    def test_500_handler(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        response = config_views.handler500(request)

        self.assertEqual(response.status_code, 500)
        self.assertIn("Une erreur est survenue", response.content.decode())
