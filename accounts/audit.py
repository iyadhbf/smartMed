"""Helpers to write append-only audit entries."""

import ipaddress

from .models import AuditLog


def _client_ip(request):
    if request is None:
        return None
    raw_ip = request.META.get("REMOTE_ADDR", "")
    try:
        return str(ipaddress.ip_address(raw_ip))
    except ValueError:
        return None


def _user_agent(request):
    if request is None:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def log_event(*, event, actor=None, target=None, request=None, description="", metadata=None):
    return AuditLog.objects.create(
        event=event,
        actor=actor,
        target_user=target,
        description=(description or "")[:255],
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
        metadata=metadata or {},
    )
