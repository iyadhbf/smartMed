from django.test import TestCase
from django.urls import reverse

from accounts.models import AuditLog, User
from doctors.models import Specialty


class SpecialtyAdminTests(TestCase):
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
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
            role=User.Role.PATIENT,
        )
        cls.cardiology = Specialty.objects.create(
            name="Cardiologie", description="Cœur et vaisseaux.", display_order=1
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_patient_cannot_manage_specialties(self):
        self.client.force_login(self.patient)

        for url in (
            reverse("specialty_admin_list"),
            reverse("specialty_create"),
            reverse("specialty_edit", args=[self.cardiology.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)

        toggle = self.client.post(reverse("specialty_toggle_status", args=[self.cardiology.pk]))
        self.assertEqual(toggle.status_code, 403)
        self.cardiology.refresh_from_db()
        self.assertTrue(self.cardiology.is_active)

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.client.get(reverse("specialty_admin_list"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('specialty_admin_list')}",
        )

    def test_admin_creates_a_specialty_and_audits_it(self):
        response = self.client.post(
            reverse("specialty_create"),
            {
                "name": "Dermatologie",
                "description": "Soins de la peau.",
                "icon": Specialty.Icon.DERMATOLOGY,
                "is_bookable": "on",
                "display_order": 4,
            },
        )

        self.assertRedirects(response, reverse("specialty_admin_list"))
        specialty = Specialty.objects.get(name="Dermatologie")
        self.assertEqual(specialty.slug, "dermatologie")
        self.assertTrue(specialty.is_bookable)

        entry = AuditLog.objects.get(event=AuditLog.Event.SPECIALTY_CREATED)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.metadata["name"], "Dermatologie")

        home = self.client.get(reverse("home"))
        self.assertContains(home, "Dermatologie")

    def test_duplicate_name_is_rejected_in_french(self):
        response = self.client.post(
            reverse("specialty_create"),
            {
                "name": "cardiologie",
                "description": "",
                "icon": Specialty.Icon.CARDIOLOGY,
                "display_order": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Une spécialité porte déjà ce nom.")
        self.assertEqual(Specialty.objects.count(), 1)

    def test_invalid_icon_is_rejected(self):
        response = self.client.post(
            reverse("specialty_create"),
            {
                "name": "ORL",
                "description": "",
                "icon": "not-an-icon",
                "display_order": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Specialty.objects.filter(name="ORL").exists())

    def test_admin_updates_a_specialty_and_audits_it(self):
        response = self.client.post(
            reverse("specialty_edit", args=[self.cardiology.pk]),
            {
                "name": "Cardiologie interventionnelle",
                "description": "Prévention et intervention.",
                "icon": Specialty.Icon.CARDIOLOGY,
                "is_bookable": "on",
                "display_order": 5,
            },
        )

        self.assertRedirects(response, reverse("specialty_admin_list"))
        self.cardiology.refresh_from_db()
        self.assertEqual(self.cardiology.name, "Cardiologie interventionnelle")
        self.assertEqual(self.cardiology.display_order, 5)
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.SPECIALTY_UPDATED).exists())

    def test_deactivation_hides_the_specialty_from_the_home_page(self):
        response = self.client.post(reverse("specialty_toggle_status", args=[self.cardiology.pk]))

        self.assertRedirects(response, reverse("specialty_admin_list"))
        self.cardiology.refresh_from_db()
        self.assertFalse(self.cardiology.is_active)
        home = self.client.get(reverse("home"))
        self.assertNotContains(home, "Cardiologie")
        self.assertTrue(
            AuditLog.objects.filter(event=AuditLog.Event.SPECIALTY_STATUS_CHANGED).exists()
        )

    def test_reactivation_restores_the_specialty(self):
        self.cardiology.is_active = False
        self.cardiology.save(update_fields=["is_active"])

        self.client.post(reverse("specialty_toggle_status", args=[self.cardiology.pk]))

        self.cardiology.refresh_from_db()
        self.assertTrue(self.cardiology.is_active)
        self.assertContains(self.client.get(reverse("home")), "Cardiologie")

    def test_list_searches_and_filters_by_status(self):
        Specialty.objects.create(name="Pédiatrie", is_active=False)

        search = self.client.get(reverse("specialty_admin_list"), {"q": "cardio"})
        self.assertContains(search, "Cardiologie")
        self.assertNotContains(search, "Pédiatrie")

        inactive = self.client.get(reverse("specialty_admin_list"), {"status": "inactive"})
        self.assertContains(inactive, "Pédiatrie")
        self.assertNotContains(inactive, "Cardiologie")

    def test_list_is_paginated(self):
        for index in range(12):
            Specialty.objects.create(name=f"Spécialité {index:02d}", display_order=10 + index)

        first_page = self.client.get(reverse("specialty_admin_list"))
        second_page = self.client.get(reverse("specialty_admin_list"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["specialties"]), 12)
        self.assertEqual(len(second_page.context["specialties"]), 1)
