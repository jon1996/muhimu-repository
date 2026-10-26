from django.db import connection

from apps.audit.models import AuditLog
from apps.identity.client_ip import client_ip


def record_audit(
    request,
    *,
    action: str,
    resource_type: str,
    resource_id: str = "",
    metadata: dict | None = None,
    organization=None,
    company=None,
) -> AuditLog:
    actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    org = organization if organization is not None else getattr(request, "organization", None)
    co = company if company is not None else getattr(request, "company", None)
    ip = client_ip(request)
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    if org is not None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_organization_id', %s, false)",
                [str(org.id)],
            )
    return AuditLog.objects.create(
        organization=org,
        company=co,
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id or "",
        metadata=metadata or {},
        ip_address=ip if ip != "unknown" else None,
        user_agent=ua,
    )
