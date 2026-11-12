from django.contrib import admin as django_admin
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.admin import AuditLogAdmin, UserAdmin
from accounts.models import AuditLog, User


class AuditLogModelTests(TestCase):
    def test_audit_entries_cannot_be_modified_or_deleted(self):
        entry = AuditLog.objects.create(event=AuditLog.Event.LOGIN_FAILED, description="test")

        entry.description = "modifié"
        with self.assertRaisesMessage(ValueError, "immuables"):
            entry.save()

        with self.assertRaisesMessage(ValueError, "supprimées"):
            entry.delete()

    def test_audit_log_admin_is_read_only(self):
        model_admin = AuditLogAdmin(AuditLog, django_admin.site)

        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_change_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None))


class RoleChangeAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            email="admin@smartmed.test",
            password="MotDePasse123!",
            first_name="Amira",
            last_name="Zouari",
        )
        cls.patient = User.objects.create_user(
            email="patient@smartmed.test",
            password="MotDePasse123!",
            first_name="Sami",
            last_name="Khelifi",
        )

    def test_role_change_through_django_admin_is_audited(self):
        request = RequestFactory().post("/admin/accounts/user/")
        request.user = self.admin

        target = User.objects.get(pk=self.patient.pk)
        target.role = User.Role.DOCTOR
        UserAdmin(User, django_admin.site).save_model(request, target, None, change=True)

        entry = AuditLog.objects.get(event=AuditLog.Event.ROLE_CHANGED)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.target_user, target)
        self.assertEqual(entry.metadata, {"old_role": "patient", "new_role": "doctor"})

    def test_admin_dashboard_displays_the_audit_journal(self):
        self.client.force_login(self.admin)
        AuditLog.objects.create(
            event=AuditLog.Event.LOGIN_FAILED,
            description="inconnu@smartmed.test",
        )

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Journal d'audit")
        self.assertContains(response, "Échec de connexion")
        self.assertContains(response, "inconnu@smartmed.test")
