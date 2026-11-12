from django.contrib import admin

from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "birth_date", "phone", "consent_given_at", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
