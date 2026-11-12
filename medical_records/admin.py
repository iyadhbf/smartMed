from django.contrib import admin

from .models import Consultation, Document, MedicalRecord, Prescription


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 0


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("patient", "updated_at")
    search_fields = (
        "patient__user__first_name",
        "patient__user__last_name",
        "patient__user__email",
    )


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ("record", "doctor", "occurred_at")
    list_filter = ("doctor",)
    date_hierarchy = "occurred_at"
    search_fields = ("record__patient__user__last_name", "report")
    inlines = [PrescriptionInline]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("consultation", "issued_on")
    date_hierarchy = "issued_on"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("patient", "document_type", "display_name", "uploaded_by", "created_at")
    list_filter = ("document_type",)
    search_fields = ("patient__user__last_name", "title")
