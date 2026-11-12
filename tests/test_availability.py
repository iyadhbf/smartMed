from datetime import time, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, User
from doctors.models import (
    AvailabilityException,
    DoctorProfile,
    Specialty,
    WeeklyAvailability,
)
from doctors.services import generate_availability, rebuild_availability


def next_weekday(weekday):
    today = timezone.localdate()
    offset = (weekday - today.weekday()) % 7
    return today + timedelta(days=offset or 7)


def create_doctor(email, number, duration=30, **profile_fields):
    user = User.objects.create_user(
        email=email,
        password="MotDePasse123!",
        first_name="Amine",
        last_name="Ben Salah",
        role=User.Role.DOCTOR,
    )
    return DoctorProfile.objects.create(
        user=user,
        specialty=Specialty.objects.create(name=f"Spécialité {number}"),
        professional_number=number,
        consultation_duration=duration,
        **profile_fields,
    )


class SlotGenerationTests(TestCase):
    def setUp(self):
        self.doctor = create_doctor("doctor@smartmed.test", "TN-GEN-0001", duration=30)
        self.monday = next_weekday(0)

    def test_slots_follow_the_weekly_hours_and_duration(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )

        created = generate_availability(self.doctor, days=1, start_date=self.monday)

        self.assertEqual(created, 2)
        slots = list(self.doctor.slots.order_by("start_time"))
        self.assertEqual(
            [(slot.start_time, slot.end_time) for slot in slots],
            [(time(9, 0), time(9, 30)), (time(9, 30), time(10, 0))],
        )

    def test_leftover_minutes_are_not_booked(self):
        self.doctor.consultation_duration = 45
        self.doctor.save(update_fields=["consultation_duration"])
        WeeklyAvailability.objects.create(
            doctor=self.doctor,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )

        generate_availability(self.doctor, days=1, start_date=self.monday)

        self.assertEqual(self.doctor.slots.count(), 1)
        slot = self.doctor.slots.get()
        self.assertEqual(slot.end_time, time(9, 45))

    def test_multiple_daily_intervals_are_generated(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(14, 0), end_time=time(15, 0)
        )

        generate_availability(self.doctor, days=1, start_date=self.monday)

        self.assertEqual(self.doctor.slots.count(), 4)

    def test_generation_is_idempotent(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )

        first = generate_availability(self.doctor, days=1, start_date=self.monday)
        second = generate_availability(self.doctor, days=1, start_date=self.monday)

        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(self.doctor.slots.count(), 2)

    def test_inactive_weekly_hours_are_ignored(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
            is_active=False,
        )

        self.assertEqual(generate_availability(self.doctor, days=1, start_date=self.monday), 0)

    def test_full_day_exception_removes_the_day(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=1, start_time=time(9, 0), end_time=time(10, 0)
        )
        AvailabilityException.objects.create(doctor=self.doctor, date=self.monday)

        rebuild_availability(self.doctor)

        self.assertFalse(self.doctor.slots.filter(date=self.monday).exists())
        self.assertTrue(self.doctor.slots.filter(date=self.monday + timedelta(days=1)).exists())

    def test_partial_exception_removes_only_the_overlap(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        AvailabilityException.objects.create(
            doctor=self.doctor,
            date=self.monday,
            start_time=time(9, 0),
            end_time=time(9, 30),
        )

        rebuild_availability(self.doctor)

        starts = list(
            self.doctor.slots.filter(date=self.monday).values_list("start_time", flat=True)
        )
        self.assertEqual(starts, [time(9, 30)])

    def test_weekly_hours_cannot_overlap(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(12, 0)
        )

        with self.assertRaises(ValidationError):
            WeeklyAvailability.objects.create(
                doctor=self.doctor, weekday=0, start_time=time(11, 0), end_time=time(13, 0)
            )

    def test_weekly_hours_end_must_follow_start(self):
        with self.assertRaises(ValidationError):
            WeeklyAvailability.objects.create(
                doctor=self.doctor, weekday=0, start_time=time(12, 0), end_time=time(9, 0)
            )

    def test_exception_requires_both_times_or_neither(self):
        exception = AvailabilityException(
            doctor=self.doctor, date=self.monday, start_time=time(9, 0)
        )

        with self.assertRaises(ValidationError):
            exception.full_clean()

    def test_no_overlapping_slots_are_created(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(10, 0), end_time=time(11, 0)
        )

        generate_availability(self.doctor, days=1, start_date=self.monday)

        slots = list(self.doctor.slots.order_by("start_time"))
        for current, following in zip(slots, slots[1:], strict=False):
            self.assertLessEqual(current.end_time, following.start_time)


class DoctorAvailabilityViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doctor = create_doctor("doctor@smartmed.test", "TN-GEN-0001")
        cls.other_doctor = create_doctor("other@smartmed.test", "TN-GEN-0002")
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
            role=User.Role.PATIENT,
        )

    def setUp(self):
        self.client.force_login(self.doctor.user)
        self.monday = next_weekday(0)

    def payload(self, rows):
        data = {
            "action": "hours",
            "form-TOTAL_FORMS": str(len(rows)),
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        }
        for index, (weekday, start, end) in enumerate(rows):
            data[f"form-{index}-weekday"] = str(weekday)
            data[f"form-{index}-start_time"] = start
            data[f"form-{index}-end_time"] = end
            data[f"form-{index}-is_active"] = "on"
            data[f"form-{index}-id"] = ""
        return data

    def test_patient_and_admin_cannot_manage_availability(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("doctor_availability")).status_code, 403)

        admin = User.objects.create_user(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
            role=User.Role.ADMIN,
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("doctor_availability")).status_code, 403)

    def test_doctor_saves_hours_and_slots_are_generated(self):
        response = self.client.post(
            reverse("doctor_availability"), self.payload([(0, "09:00", "10:00")])
        )

        self.assertRedirects(response, reverse("doctor_availability"))
        self.assertEqual(WeeklyAvailability.objects.filter(doctor=self.doctor).count(), 1)
        self.assertGreater(self.doctor.slots.count(), 0)
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.AVAILABILITY_UPDATED).exists())

    def test_overlapping_rows_are_rejected_together(self):
        response = self.client.post(
            reverse("doctor_availability"),
            self.payload([(0, "09:00", "10:00"), (0, "09:30", "10:30")]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chevauchent")
        self.assertEqual(WeeklyAvailability.objects.filter(doctor=self.doctor).count(), 0)

    def test_existing_overlap_is_rejected(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(12, 0)
        )

        response = self.client.post(
            reverse("doctor_availability"), self.payload([(0, "11:00", "13:00")])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chevauchent")
        self.assertEqual(WeeklyAvailability.objects.filter(doctor=self.doctor).count(), 1)

    def test_doctor_only_manages_their_own_schedule(self):
        WeeklyAvailability.objects.create(
            doctor=self.other_doctor, weekday=0, start_time=time(8, 15), end_time=time(9, 0)
        )

        listing = self.client.get(reverse("doctor_availability"))
        self.assertNotContains(listing, "08:15")

        self.client.post(reverse("doctor_availability"), self.payload([(2, "10:00", "11:00")]))

        self.assertEqual(WeeklyAvailability.objects.filter(doctor=self.doctor).count(), 1)
        self.assertEqual(WeeklyAvailability.objects.filter(doctor=self.other_doctor).count(), 1)
        self.assertFalse(
            WeeklyAvailability.objects.filter(doctor=self.other_doctor, weekday=2).exists()
        )

    def test_full_day_exception_removes_slots_and_is_audited(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        rebuild_availability(self.doctor)

        response = self.client.post(
            reverse("doctor_availability"),
            {
                "action": "add_exception",
                "date": self.monday.isoformat(),
                "start_time": "",
                "end_time": "",
                "reason": "Congé",
            },
        )

        self.assertRedirects(response, reverse("doctor_availability"))
        self.assertTrue(
            AvailabilityException.objects.filter(doctor=self.doctor, date=self.monday).exists()
        )
        self.assertFalse(self.doctor.slots.filter(date=self.monday).exists())
        self.assertTrue(AuditLog.objects.filter(event=AuditLog.Event.AVAILABILITY_UPDATED).exists())

    def test_past_exception_is_rejected(self):
        yesterday = timezone.localdate() - timedelta(days=1)

        response = self.client.post(
            reverse("doctor_availability"),
            {
                "action": "add_exception",
                "date": yesterday.isoformat(),
                "start_time": "",
                "end_time": "",
                "reason": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choisissez une date à venir.")
        self.assertFalse(AvailabilityException.objects.exists())

    def test_deleting_an_exception_restores_slots(self):
        WeeklyAvailability.objects.create(
            doctor=self.doctor, weekday=0, start_time=time(9, 0), end_time=time(10, 0)
        )
        exception = AvailabilityException.objects.create(
            doctor=self.doctor, date=self.monday, reason="Congé"
        )
        rebuild_availability(self.doctor)
        self.assertFalse(self.doctor.slots.filter(date=self.monday).exists())

        response = self.client.post(
            reverse("doctor_availability"),
            {"action": "delete_exception", "exception_id": exception.pk},
        )

        self.assertRedirects(response, reverse("doctor_availability"))
        self.assertTrue(self.doctor.slots.filter(date=self.monday).exists())
