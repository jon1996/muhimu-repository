from ninja import Router, Schema
from ninja.errors import HttpError

from apps.audit.models import AuditLog
from apps.tenancy.models import Role

router = Router(tags=["audit"])


class AuditLogOut(Schema):
    id: str
    action: str
    resource_type: str
    resource_id: str
    actor_email: str | None
    company_id: str | None
    metadata: dict
    created_at: str


@router.get("/audit-logs", response=list[AuditLogOut])
def list_audit_logs(request, limit: int = 50):
    if not request.organization or not request.membership:
        raise HttpError(403, "Organisation absente ou accès refusé.")
    if request.membership.role not in (Role.OWNER, Role.ADMIN, Role.AUDITOR):
        raise HttpError(403, "Consultation de l'audit réservée aux administrateurs et auditeurs.")
    limit = max(1, min(limit, 200))
    logs = (
        AuditLog.objects.filter(organization=request.organization)
        .select_related("actor", "company")
        .order_by("-created_at")[:limit]
    )
    return [
        AuditLogOut(
            id=str(log.id),
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            actor_email=log.actor.email if log.actor_id else None,
            company_id=str(log.company_id) if log.company_id else None,
            metadata=log.metadata,
            created_at=log.created_at.isoformat(),
        )
        for log in logs
    ]
