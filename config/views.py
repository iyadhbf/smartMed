from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView

from doctors.models import DoctorProfile, Specialty

SERVICES = [
    {
        "title": "Diagnostic avancé",
        "description": "Une imagerie médicale de dernière génération pour des diagnostics précis et rapides.",
        "image": "img/service-diagnostic.jpg",
        "alt": "Scanner d'imagerie médicale dans une salle claire",
        "icon": "activity",
    },
    {
        "title": "Chirurgies spécialisées",
        "description": "Des blocs opératoires équipés et des équipes expérimentées, dans un cadre rassurant.",
        "image": "img/service-surgery.jpg",
        "alt": "Bloc opératoire moderne équipé",
        "icon": "scissors",
    },
    {
        "title": "Assistant médical IA",
        "description": "Des réponses claires, fondées sur des documents médicaux fiables et toujours sourcées.",
        "image": "img/service-ai.jpg",
        "alt": "Médecin utilisant une interface numérique d'assistance",
        "icon": "stars",
    },
    {
        "title": "Suivi du dossier médical",
        "description": "Consultations, ordonnances et documents réunis dans un espace personnel sécurisé.",
        "image": "img/service-records.jpg",
        "alt": "Médecin consultant un dossier médical sur une tablette",
        "icon": "folder2-open",
    },
]

STEPS = [
    {
        "number": "01",
        "title": "Choisissez votre médecin",
        "text": "Parcourez les spécialités et les profils des praticiens de notre équipe.",
        "icon": "search",
    },
    {
        "number": "02",
        "title": "Réservez votre créneau",
        "text": "Sélectionnez la date et l'heure qui vous conviennent, en quelques secondes.",
        "icon": "calendar2-check",
    },
    {
        "number": "03",
        "title": "Consultez sereinement",
        "text": "Retrouvez ensuite vos comptes rendus et documents dans votre espace sécurisé.",
        "icon": "clipboard2-pulse",
    },
]


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        specialties = Specialty.objects.filter(is_active=True).order_by("display_order", "name")
        context["specialties"] = specialties
        context["booking_specialties"] = specialties.filter(
            is_bookable=True,
            doctors__is_active=True,
            doctors__user__is_active=True,
        ).distinct()

        context["doctors"] = (
            DoctorProfile.objects.filter(is_active=True, user__is_active=True)
            .select_related("user", "specialty")
            .order_by("display_order", "user__last_name", "user__first_name")[:3]
        )

        context["services"] = SERVICES
        context["steps"] = STEPS
        context["today"] = timezone.localdate().isoformat()
        return context


def privacy(request):
    return render(request, "pages/privacy.html")


def legal(request):
    return render(request, "pages/legal.html")


def handler403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def handler404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def handler500(request):
    return render(request, "errors/500.html", status=500)
