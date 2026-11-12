from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("", views.AppointmentListView.as_view(), name="appointment_list"),
    path("reserver/", views.book_entry, name="book_entry"),
    path("<int:pk>/annuler/", views.appointment_cancel, name="appointment_cancel"),
    path("<int:pk>/reprogrammer/", views.appointment_reschedule, name="appointment_reschedule"),
]
