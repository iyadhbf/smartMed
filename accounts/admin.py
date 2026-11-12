from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .audit import log_event
from .models import AuditLog, User


class AddUserForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


class ChangeUserForm(UserChangeForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")
    form = ChangeUserForm
    add_form = AddUserForm
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "role", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        previous_role = None
        if change:
            previous_role = User.objects.filter(pk=obj.pk).values_list("role", flat=True).first()

        super().save_model(request, obj, form, change)

        if change and previous_role and previous_role != obj.role:
            log_event(
                event=AuditLog.Event.ROLE_CHANGED,
                actor=request.user,
                target=obj,
                request=request,
                metadata={"old_role": previous_role, "new_role": obj.role},
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "actor", "target_user", "description", "ip_address")
    list_filter = ("event", "created_at")
    search_fields = ("description", "actor__email", "target_user__email")
    date_hierarchy = "created_at"
    readonly_fields = (
        "actor",
        "target_user",
        "event",
        "description",
        "ip_address",
        "user_agent",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
