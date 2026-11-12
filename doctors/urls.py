from django.urls import path

from .views import doctor_list

app_name = "doctors"

urlpatterns = [
    path("doctors/", doctor_list, name="api_list"),
]
