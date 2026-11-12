from django.urls import path

from .views import (
    AuditedPasswordChangeView,
    AuditedPasswordResetConfirmView,
    AuditedPasswordResetView,
    EmailLoginView,
    PasswordResetFinishedView,
    PasswordResetSentView,
    ProfileView,
    RegisterView,
    UserLogoutView,
)

app_name = "accounts"

urlpatterns = [
    path("connexion/", EmailLoginView.as_view(), name="login"),
    path("deconnexion/", UserLogoutView.as_view(), name="logout"),
    path("inscription/", RegisterView.as_view(), name="register"),
    path("profil/", ProfileView.as_view(), name="profile"),
    path("mot-de-passe/", AuditedPasswordChangeView.as_view(), name="password_change"),
    path(
        "mot-de-passe-oublie/",
        AuditedPasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "mot-de-passe/renvoye/",
        PasswordResetSentView.as_view(),
        name="password_reset_done",
    ),
    path(
        "reinitialiser/<uidb64>/<token>/",
        AuditedPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "reinitialiser/termine/",
        PasswordResetFinishedView.as_view(),
        name="password_reset_complete",
    ),
]
