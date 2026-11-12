from django.contrib import admin

from .models import (
    Availability,
    AvailabilityException,
    DoctorProfile,
    Specialty,
    WeeklyAvailability,
)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "is_bookable", "is_active", "display_order")
    list_editable = ("is_bookable", "is_active", "display_order")
    list_filter = ("is_bookable", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "specialty",
        "professional_number",
        "consultation_duration",
        "is_active",
    )
    list_filter = ("specialty", "is_active")
    search_fields = ("user__first_name", "user__last_name", "user__email", "professional_number")
    list_select_related = ("user", "specialty")
    autocomplete_fields = ("user",)


@admin.register(WeeklyAvailability)
class WeeklyAvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "weekday", "start_time", "end_time", "is_active")
    list_filter = ("weekday", "is_active")
    list_select_related = ("doctor__user",)
    search_fields = ("doctor__user__first_name", "doctor__user__last_name")


@admin.register(AvailabilityException)
class AvailabilityExceptionAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "start_time", "end_time", "reason")
    list_filter = ("date",)
    list_select_related = ("doctor__user",)
    search_fields = ("doctor__user__first_name", "doctor__user__last_name", "reason")


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "start_time", "end_time")
    list_filter = ("date",)
    list_select_related = ("doctor__user",)
    date_hierarchy = "date"
