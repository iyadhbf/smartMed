from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from accounts.permissions import patient_required


class PermissionMatrixTests(TestCase):
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

    def assert_status_for_each_role(self, url_name, expected):
        for user, expected_status in expected.items():
            with self.subTest(role=user.role, view=url_name):
                self.client.force_login(user)
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, expected_status)
                self.client.logout()

    def test_patient_dashboard_is_patient_only(self):
        self.assert_status_for_each_role(
            "patient_dashboard",
            {self.patient: 200, self.doctor: 403, self.admin: 403},
        )

    def test_doctor_dashboard_is_doctor_only(self):
        self.assert_status_for_each_role(
            "doctor_dashboard",
            {self.patient: 403, self.doctor: 200, self.admin: 403},
        )

    def test_admin_dashboard_is_admin_only(self):
        self.assert_status_for_each_role(
            "admin_dashboard",
            {self.patient: 403, self.doctor: 403, self.admin: 200},
        )

    def test_doctor_creation_is_admin_only(self):
        self.assert_status_for_each_role(
            "doctor_create",
            {self.patient: 403, self.doctor: 403, self.admin: 200},
        )

    def test_profile_and_password_change_are_open_to_every_role(self):
        for user in (self.patient, self.doctor, self.admin):
            with self.subTest(role=user.role):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
                self.assertEqual(
                    self.client.get(reverse("accounts:password_change")).status_code, 200
                )
                self.client.logout()

    def test_anonymous_users_are_redirected_to_login_with_next(self):
        protected_urls = [
            "patient_dashboard",
            "doctor_dashboard",
            "admin_dashboard",
            "doctor_create",
            "accounts:profile",
            "accounts:password_change",
        ]
        for url_name in protected_urls:
            with self.subTest(view=url_name):
                target = reverse(url_name)
                response = self.client.get(target)

                self.assertEqual(response.status_code, 302)
                parsed = urlparse(response.url)
                self.assertEqual(parsed.path, reverse("accounts:login"))
                self.assertEqual(parse_qs(parsed.query)["next"], [target])

    def test_role_required_decorator_guards_a_function_view(self):
        @patient_required
        def sample_view(request):
            return HttpResponse("ok")

        factory = RequestFactory()
        request = factory.get("/exemple/")
        request.user = self.patient
        self.assertEqual(sample_view(request).content, b"ok")

        request.user = self.doctor
        with self.assertRaises(PermissionDenied):
            sample_view(request)

        request.user = AnonymousUser()
        response = sample_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
