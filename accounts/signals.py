from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .audit import log_event
from .models import AuditLog, User


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request=None, **kwargs):
    email = (credentials.get("username") or "").strip()[:254]
    actor = User.objects.filter(email__iexact=email).first() if email else None
    log_event(
        event=AuditLog.Event.LOGIN_FAILED,
        actor=actor,
        target=actor,
        request=request,
        description=email,
        metadata={"email": email} if email else {},
    )


@receiver(user_logged_in)
def log_successful_login(sender, request, user, **kwargs):
    log_event(
        event=AuditLog.Event.LOGIN_SUCCESS,
        actor=user,
        target=user,
        request=request,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user is not None:
        log_event(
            event=AuditLog.Event.LOGOUT,
            actor=user,
            target=user,
            request=request,
        )
