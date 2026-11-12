from django.contrib import admin

from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "start_time",
        "doctor",
        "patient",
        "status",
    )
    list_filter = ("status", "doctor__specialty", "date")
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "patient__email",
        "doctor__user__last_name",
    )
    list_select_related = ("patient", "doctor__user", "slot")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
