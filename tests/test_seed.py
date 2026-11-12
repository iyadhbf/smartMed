from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from doctors.models import (
    AvailabilityException,
    DoctorProfile,
    Specialty,
    WeeklyAvailability,
)
from patients.models import PatientProfile


class SeedDemoCommandTests(TestCase):
    def seed(self):
        output = StringIO()
        call_command("seed_demo", stdout=output)
        return output.getvalue()

    def test_seed_creates_a_fictional_dataset(self):
        output = self.seed()

        self.assertIn("Seed terminé", output)
        self.assertEqual(Specialty.objects.count(), 6)
        self.assertEqual(DoctorProfile.objects.count(), 6)
        self.assertEqual(User.objects.filter(role=User.Role.DOCTOR).count(), 6)
        self.assertEqual(User.objects.filter(role=User.Role.PATIENT).count(), 2)
        self.assertEqual(User.objects.filter(role=User.Role.ADMIN).count(), 1)
        self.assertEqual(PatientProfile.objects.count(), 2)

        for profile in PatientProfile.objects.select_related("user"):
            self.assertIsNotNone(profile.birth_date)
            self.assertTrue(profile.phone)
            self.assertIsNotNone(profile.consent_given_at)

        for user in User.objects.all():
            self.assertTrue(user.email.endswith("@smartmed.test"))

        self.assertEqual(WeeklyAvailability.objects.count(), 53)
        self.assertEqual(AvailabilityException.objects.count(), 2)
        for profile in DoctorProfile.objects.all():
            self.assertTrue(profile.weekly_hours.exists())
            self.assertTrue(profile.slots.exists())

    def test_seed_marks_emergency_department_as_non_bookable(self):
        self.seed()

        emergency = Specialty.objects.get(name="Urgences")
        self.assertFalse(emergency.is_bookable)

    def test_seed_creates_a_usable_admin_account(self):
        self.seed()

        admin = User.objects.get(email="admin@smartmed.test")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin_role)
        self.assertTrue(admin.check_password("Demo1234!"))

    def test_seed_is_idempotent_and_preserves_passwords(self):
        self.seed()
        password_hash = User.objects.get(email="doctor1@smartmed.test").password
        counts = (
            User.objects.count(),
            Specialty.objects.count(),
            DoctorProfile.objects.count(),
            PatientProfile.objects.count(),
            WeeklyAvailability.objects.count(),
            AvailabilityException.objects.count(),
        )

        self.seed()

        self.assertEqual(
            counts,
            (
                User.objects.count(),
                Specialty.objects.count(),
                DoctorProfile.objects.count(),
                PatientProfile.objects.count(),
                WeeklyAvailability.objects.count(),
                AvailabilityException.objects.count(),
            ),
        )
        self.assertEqual(User.objects.get(email="doctor1@smartmed.test").password, password_hash)
