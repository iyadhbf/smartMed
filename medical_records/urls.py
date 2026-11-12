from django.urls import path

from . import views

app_name = "records"

urlpatterns = [
    path("dossier/", views.PatientRecordView.as_view(), name="patient_record"),
    path("doctor/patients/", views.DoctorPatientListView.as_view(), name="doctor_patients"),
    path(
        "doctor/patients/<int:pk>/",
        views.DoctorPatientRecordView.as_view(),
        name="doctor_patient_record",
    ),
    path(
        "documents/<int:pk>/telecharger/",
        views.document_download,
        name="document_download",
    ),
]
