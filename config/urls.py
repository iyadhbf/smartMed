from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from accounts.views import (
    AdminDashboardView,
    DoctorCreateView,
    DoctorDashboardView,
    PatientAdminListView,
    PatientDashboardView,
    patient_toggle_status,
)
from appointments.views import DoctorAgendaView, DoctorAppointmentActionView
from doctors.views import (
    DoctorAdminListView,
    DoctorAdminUpdateView,
    DoctorAvailabilityView,
    DoctorDirectoryView,
    DoctorPublicDetailView,
    SpecialtyAdminListView,
    SpecialtyCreateView,
    SpecialtyUpdateView,
    doctor_toggle_status,
    specialty_toggle_status,
)

from . import views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("confidentialite/", views.privacy, name="privacy"),
    path("mentions-legales/", views.legal, name="legal"),
    path("compte/", include("accounts.urls")),
    path("medecins/", DoctorDirectoryView.as_view(), name="doctor_directory"),
    path("medecins/<int:pk>/", DoctorPublicDetailView.as_view(), name="doctor_public"),
    path("patient/", PatientDashboardView.as_view(), name="patient_dashboard"),
    path("doctor/", DoctorDashboardView.as_view(), name="doctor_dashboard"),
    path(
        "doctor/disponibilites/",
        DoctorAvailabilityView.as_view(),
        name="doctor_availability",
    ),
    path("doctor/rendez-vous/", DoctorAgendaView.as_view(), name="doctor_agenda"),
    path(
        "doctor/rendez-vous/<int:pk>/<str:action>/",
        DoctorAppointmentActionView.as_view(),
        name="doctor_appointment_action",
    ),
    path("admin-panel/", AdminDashboardView.as_view(), name="admin_dashboard"),
    path(
        "admin-panel/patients/",
        PatientAdminListView.as_view(),
        name="patient_admin_list",
    ),
    path(
        "admin-panel/patients/<int:pk>/statut/",
        patient_toggle_status,
        name="patient_toggle_status",
    ),
    path(
        "admin-panel/medecins/",
        DoctorAdminListView.as_view(),
        name="doctor_admin_list",
    ),
    path("admin-panel/medecins/nouveau/", DoctorCreateView.as_view(), name="doctor_create"),
    path(
        "admin-panel/medecins/<int:pk>/modifier/",
        DoctorAdminUpdateView.as_view(),
        name="doctor_edit",
    ),
    path(
        "admin-panel/medecins/<int:pk>/statut/",
        doctor_toggle_status,
        name="doctor_toggle_status",
    ),
    path(
        "admin-panel/specialites/",
        SpecialtyAdminListView.as_view(),
        name="specialty_admin_list",
    ),
    path(
        "admin-panel/specialites/nouvelle/",
        SpecialtyCreateView.as_view(),
        name="specialty_create",
    ),
    path(
        "admin-panel/specialites/<int:pk>/modifier/",
        SpecialtyUpdateView.as_view(),
        name="specialty_edit",
    ),
    path(
        "admin-panel/specialites/<int:pk>/statut/",
        specialty_toggle_status,
        name="specialty_toggle_status",
    ),
    path("rendez-vous/", include("appointments.urls")),
    path("", include("medical_records.urls")),
    path("api/", include("doctors.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = views.handler403
handler404 = views.handler404
handler500 = views.handler500
