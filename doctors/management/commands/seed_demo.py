"""Seed the demo database with 100% fictional data.

Usage:
    python manage.py seed_demo

Idempotent: running it twice does not create duplicates and does not reset
passwords of existing accounts.
"""

from datetime import time, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from doctors.models import (
    AvailabilityException,
    DoctorProfile,
    Specialty,
    WeeklyAvailability,
)
from doctors.services import rebuild_availability
from patients.models import PatientProfile

DEMO_PASSWORD = "Demo1234!"

SPECIALTIES = [
    {
        "name": "Urgences",
        "icon": Specialty.Icon.EMERGENCY,
        "is_bookable": False,
        "display_order": 1,
        "description": "Une prise en charge immédiate, 24 h/24 et 7 j/7.",
    },
    {
        "name": "Pédiatrie",
        "icon": Specialty.Icon.PEDIATRICS,
        "is_bookable": True,
        "display_order": 2,
        "description": "Le suivi des nourrissons, enfants et adolescents.",
    },
    {
        "name": "Cardiologie",
        "icon": Specialty.Icon.CARDIOLOGY,
        "is_bookable": True,
        "display_order": 3,
        "description": "Prévention, diagnostic et suivi des maladies du cœur.",
    },
    {
        "name": "Dermatologie",
        "icon": Specialty.Icon.DERMATOLOGY,
        "is_bookable": True,
        "display_order": 4,
        "description": "Soins de la peau, des cheveux et des ongles.",
    },
    {
        "name": "Médecine générale",
        "icon": Specialty.Icon.GENERAL,
        "is_bookable": True,
        "display_order": 5,
        "description": "Un interlocuteur de confiance pour toute la famille.",
    },
    {
        "name": "Gynécologie",
        "icon": Specialty.Icon.GYNECOLOGY,
        "is_bookable": True,
        "display_order": 6,
        "description": "Le suivi de la santé des femmes à chaque étape de la vie.",
    },
]

DOCTORS = [
    {
        "email": "doctor1@smartmed.test",
        "first_name": "Amine",
        "last_name": "Ben Salah",
        "specialty": "Cardiologie",
        "professional_number": "TN-CARD-1042",
        "display_order": 1,
        "bio": (
            "Cardiologue depuis douze ans, je prends le temps d'expliquer chaque étape "
            "du diagnostic et du suivi, pour des décisions partagées."
        ),
    },
    {
        "email": "doctor2@smartmed.test",
        "first_name": "Leïla",
        "last_name": "Trabelsi",
        "specialty": "Pédiatrie",
        "professional_number": "TN-PED-2087",
        "display_order": 2,
        "bio": (
            "Pédiatre attentive, j'accompagne les enfants et leurs familles avec "
            "douceur, de la naissance à l'adolescence."
        ),
    },
    {
        "email": "doctor3@smartmed.test",
        "first_name": "Yasmine",
        "last_name": "Gharbi",
        "specialty": "Dermatologie",
        "professional_number": "TN-DER-3311",
        "display_order": 3,
        "bio": (
            "Dermatologue, je traite aussi bien les problèmes de peau courants que le "
            "suivi des maladies chroniques, avec des conseils simples et concrets."
        ),
    },
    {
        "email": "doctor4@smartmed.test",
        "first_name": "Karim",
        "last_name": "Haddad",
        "specialty": "Médecine générale",
        "professional_number": "TN-GEN-4056",
        "display_order": 4,
        "bio": (
            "Médecin généraliste, je coordonne les soins de toute la famille et vous "
            "oriente vers la bonne spécialité lorsque c'est nécessaire."
        ),
    },
    {
        "email": "doctor5@smartmed.test",
        "first_name": "Sonia",
        "last_name": "Mansour",
        "specialty": "Gynécologie",
        "professional_number": "TN-GYN-5120",
        "display_order": 5,
        "bio": (
            "Gynécologue-obstétricienne, j'accompagne les femmes dans leur suivi "
            "gynécologique et leur grossesse, dans un cadre respectueux et confidentiel."
        ),
    },
    {
        "email": "doctor6@smartmed.test",
        "first_name": "Mehdi",
        "last_name": "Bouazizi",
        "specialty": "Cardiologie",
        "professional_number": "TN-CARD-6114",
        "display_order": 6,
        "bio": (
            "Cardiologue, je suis particulièrement impliqué dans la prévention et le "
            "suivi de l'hypertension artérielle."
        ),
    },
]

CONSULTATION_DURATIONS = {
    "doctor1@smartmed.test": 30,
    "doctor2@smartmed.test": 45,
    "doctor3@smartmed.test": 30,
    "doctor4@smartmed.test": 20,
    "doctor5@smartmed.test": 40,
    "doctor6@smartmed.test": 30,
}

WEEKLY_SCHEDULES = {
    "doctor1@smartmed.test": [
        (0, "08:30", "12:30"),
        (0, "14:00", "17:30"),
        (2, "08:30", "12:30"),
        (2, "14:00", "17:30"),
        (4, "08:30", "12:30"),
        (4, "14:00", "17:30"),
        (1, "09:00", "12:00"),
        (3, "09:00", "12:00"),
    ],
    "doctor2@smartmed.test": [
        (0, "09:00", "12:00"),
        (0, "14:00", "16:30"),
        (1, "09:00", "12:00"),
        (1, "14:00", "16:30"),
        (2, "09:00", "12:00"),
        (2, "14:00", "16:30"),
        (3, "09:00", "12:00"),
        (3, "14:00", "16:30"),
        (4, "09:00", "12:00"),
        (4, "14:00", "16:30"),
        (5, "09:00", "12:00"),
    ],
    "doctor3@smartmed.test": [
        (1, "10:00", "13:00"),
        (1, "15:00", "18:00"),
        (2, "10:00", "13:00"),
        (2, "15:00", "18:00"),
        (3, "10:00", "13:00"),
        (3, "15:00", "18:00"),
        (4, "10:00", "13:00"),
        (4, "15:00", "18:00"),
        (5, "10:00", "13:00"),
    ],
    "doctor4@smartmed.test": [
        (0, "08:00", "12:00"),
        (0, "13:30", "17:00"),
        (1, "08:00", "12:00"),
        (1, "13:30", "17:00"),
        (2, "08:00", "12:00"),
        (2, "13:30", "17:00"),
        (3, "08:00", "12:00"),
        (3, "13:30", "17:00"),
        (4, "08:00", "12:00"),
    ],
    "doctor5@smartmed.test": [
        (0, "09:00", "13:00"),
        (0, "14:00", "18:00"),
        (2, "09:00", "13:00"),
        (2, "14:00", "18:00"),
        (3, "09:00", "13:00"),
        (3, "14:00", "18:00"),
    ],
    "doctor6@smartmed.test": [
        (0, "09:00", "12:00"),
        (0, "14:00", "17:00"),
        (1, "09:00", "12:00"),
        (1, "14:00", "17:00"),
        (2, "09:00", "12:00"),
        (2, "14:00", "17:00"),
        (3, "09:00", "12:00"),
        (3, "14:00", "17:00"),
        (4, "09:00", "12:00"),
        (4, "14:00", "17:00"),
    ],
}

EXCEPTIONS = [
    ("doctor1@smartmed.test", 7, None, None, "Congé"),
    ("doctor4@smartmed.test", 10, "14:00", "17:00", "Formation"),
]

PATIENTS = [
    {
        "email": "patient1@smartmed.test",
        "first_name": "Sami",
        "last_name": "Khelifi",
        "birth_date": "1988-03-14",
        "phone": "+216 20 000 001",
    },
    {
        "email": "patient2@smartmed.test",
        "first_name": "Nour",
        "last_name": "Jaziri",
        "birth_date": "1995-11-02",
        "phone": "+216 20 000 002",
    },
]


class Command(BaseCommand):
    help = "Create fictional specialties, doctors, an admin and patients for the demo."

    @transaction.atomic
    def handle(self, *args, **options):
        specialties = {}
        for data in SPECIALTIES:
            specialty, _ = Specialty.objects.update_or_create(
                name=data["name"],
                defaults={
                    "icon": data["icon"],
                    "is_bookable": data["is_bookable"],
                    "display_order": data["display_order"],
                    "description": data["description"],
                    "is_active": True,
                },
            )
            specialties[specialty.name] = specialty

        admin, admin_created = User.objects.get_or_create(
            email="admin@smartmed.test",
            defaults={
                "first_name": "Amira",
                "last_name": "Zouari",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if admin_created:
            admin.set_password(DEMO_PASSWORD)
            admin.save(update_fields=["password"])
        else:
            admin.role = User.Role.ADMIN
            admin.is_staff = True
            admin.is_superuser = True
            admin.save(update_fields=["role", "is_staff", "is_superuser"])

        for data in PATIENTS:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "role": User.Role.PATIENT,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])

            profile, profile_created = PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "birth_date": data["birth_date"],
                    "phone": data["phone"],
                    "consent_given_at": timezone.now(),
                },
            )
            if not profile_created:
                profile.birth_date = data["birth_date"]
                profile.phone = data["phone"]
                if profile.consent_given_at is None:
                    profile.consent_given_at = timezone.now()
                profile.save()

        for data in DOCTORS:
            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "role": User.Role.DOCTOR,
                },
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save(update_fields=["password"])
            elif not user.is_active:
                user.is_active = True
                user.save(update_fields=["is_active"])

            profile, _ = DoctorProfile.objects.update_or_create(
                user=user,
                defaults={
                    "specialty": specialties[data["specialty"]],
                    "professional_number": data["professional_number"],
                    "bio": data["bio"],
                    "consultation_duration": CONSULTATION_DURATIONS[user.email],
                    "is_active": True,
                    "display_order": data["display_order"],
                },
            )

            for weekday, start, end in WEEKLY_SCHEDULES[user.email]:
                WeeklyAvailability.objects.update_or_create(
                    doctor=profile,
                    weekday=weekday,
                    start_time=time.fromisoformat(start),
                    defaults={"end_time": time.fromisoformat(end), "is_active": True},
                )

            for email, offset, start, end, reason in EXCEPTIONS:
                if email != user.email:
                    continue
                exception_date = timezone.localdate() + timedelta(days=offset)
                AvailabilityException.objects.get_or_create(
                    doctor=profile,
                    date=exception_date,
                    reason=reason,
                    defaults={
                        "start_time": time.fromisoformat(start) if start else None,
                        "end_time": time.fromisoformat(end) if end else None,
                    },
                )

            rebuild_availability(profile)

        self._seed_appointments()
        self._seed_medical_records()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed terminé : {len(SPECIALTIES)} spécialités, {len(DOCTORS)} médecins, "
                f"{len(PATIENTS)} patients. Mot de passe démo : {DEMO_PASSWORD}"
            )
        )

    def _seed_appointments(self):
        """Create fictional demo appointments (idempotent per doctor/date/start_time)."""

        from appointments.models import Appointment

        today = timezone.localdate()
        patients = {user.email: user for user in User.objects.filter(role=User.Role.PATIENT)}
        doctors = {
            profile.user.email: profile
            for profile in DoctorProfile.objects.select_related("user", "specialty")
        }

        def claim(email, patient_email, status):
            profile = doctors.get(email)
            patient = patients.get(patient_email)
            if profile is None or patient is None:
                return
            slot = (
                profile.slots.filter(date__gt=today)
                .exclude(
                    pk__in=Appointment.objects.filter(
                        doctor=profile, status__in=("pending", "confirmed")
                    ).values("slot_id")
                )
                .order_by("date", "start_time")
                .first()
            )
            if slot is None:
                return
            appointment, created = Appointment.objects.get_or_create(
                doctor=profile,
                patient=patient,
                date=slot.date,
                start_time=slot.start_time,
                defaults={"slot": slot, "end_time": slot.end_time, "status": status},
            )
            if not created and appointment.slot_id != slot.pk:
                appointment.slot = slot
                appointment.save(update_fields=["slot"])

        claim("doctor1@smartmed.test", "patient1@smartmed.test", Appointment.Status.PENDING)
        claim("doctor1@smartmed.test", "patient2@smartmed.test", Appointment.Status.CONFIRMED)
        claim("doctor2@smartmed.test", "patient1@smartmed.test", Appointment.Status.CONFIRMED)

        # Historical appointments whose slots have been purged (slot=NULL).
        past = [
            (
                "doctor1@smartmed.test",
                "patient1@smartmed.test",
                today - timedelta(days=3),
                time(10, 0),
                time(10, 30),
                Appointment.Status.COMPLETED,
                "Contrôle de tension",
            ),
            (
                "doctor2@smartmed.test",
                "patient2@smartmed.test",
                today - timedelta(days=6),
                time(9, 0),
                time(9, 30),
                Appointment.Status.CANCELLED,
                "",
            ),
        ]
        for email, patient_email, day, start, end, status, reason in past:
            profile = doctors.get(email)
            patient = patients.get(patient_email)
            if profile is None or patient is None:
                continue
            Appointment.objects.get_or_create(
                doctor=profile,
                patient=patient,
                date=day,
                start_time=start,
                defaults={
                    "slot": None,
                    "end_time": end,
                    "status": status,
                    "reason": reason,
                },
            )

    def _seed_medical_records(self):
        """Create fictional records, consultations, prescriptions, and one document."""

        from medical_records.models import (
            Consultation,
            Document,
            MedicalRecord,
            Prescription,
        )

        demo_pdf = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 120]>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n"
        )

        def scenario(
            doctor_email,
            patient_email,
            history,
            allergies,
            treatments,
            occurred_days_ago,
            report,
            prescription,
        ):
            doctor = DoctorProfile.objects.filter(user__email=doctor_email).first()
            patient = User.objects.filter(email=patient_email, role=User.Role.PATIENT).first()
            if doctor is None or patient is None:
                return None
            profile, _ = PatientProfile.objects.get_or_create(user=patient)
            record, _ = MedicalRecord.objects.get_or_create(
                patient=profile,
                defaults={
                    "history": history,
                    "allergies": allergies,
                    "treatments": treatments,
                },
            )
            if not record.history:
                record.history = history
                record.allergies = allergies
                record.treatments = treatments
                record.save(update_fields=["history", "allergies", "treatments"])
            occurred = timezone.now().replace(
                hour=10, minute=0, second=0, microsecond=0
            ) - timedelta(days=occurred_days_ago)
            consultation, _ = Consultation.objects.get_or_create(
                record=record,
                doctor=doctor,
                occurred_at=occurred,
                defaults={"report": report},
            )
            if prescription and not consultation.prescriptions.exists():
                Prescription.objects.create(
                    consultation=consultation,
                    content=prescription,
                    issued_on=occurred.date(),
                )
            return record, consultation

        first = scenario(
            "doctor1@smartmed.test",
            "patient1@smartmed.test",
            "Hypertension artérielle (fictive), suivie depuis 2024.",
            "Pénicilline (fictif).",
            "Amlodipine 5 mg, 1 comprimé le matin (fictif).",
            3,
            "Contrôle de tension : 12/8 (fictif). Évolution favorable. "
            "Poursuite du traitement actuel, prochain contrôle dans trois mois.",
            "Amlodipine 5 mg — 1 cp le matin pendant 3 mois (fictif).\n"
            "Paracétamol 500 mg — si douleur, 3 fois par jour maximum (fictif).",
        )
        scenario(
            "doctor2@smartmed.test",
            "patient1@smartmed.test",
            "Hypertension artérielle (fictive), suivie depuis 2024.",
            "Pénicilline (fictif).",
            "Amlodipine 5 mg, 1 comprimé le matin (fictif).",
            10,
            "Consultation pédiatrique de routine (fictive) : aucune anomalie, "
            "croissance normale. Vaccination à jour.",
            None,
        )

        if first is not None:
            record, consultation = first
            if not Document.objects.filter(
                patient=record.patient, title="Compte rendu cardiaque (fictif)"
            ).exists():
                Document.objects.create(
                    patient=record.patient,
                    consultation=consultation,
                    document_type=Document.Type.REPORT,
                    title="Compte rendu cardiaque (fictif)",
                    uploaded_by=consultation.doctor.user,
                    file=ContentFile(demo_pdf, name="compte-rendu-cardiaque.pdf"),
                )
