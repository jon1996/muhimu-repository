from ninja import Router, Schema
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from ninja.errors import HttpError

from apps.audit.services import record_audit
from apps.identity.auth_login import attempt_password_login
from apps.identity.models import User
from apps.platform.dashboard import dashboard_payload
from apps.platform.directory import tenant_directory, user_directory
from apps.platform.models import DemoGrant
from apps.platform.services.grants import (
    DemoSandboxMissing,
    revoke_demo_grant,
    upsert_demo_grant,
)
from apps.platform.services.mail import deliver_demo_mail, mail_status, send_test_mail

router = Router(tags=["platform"])


class LoginIn(Schema):
    email: str
    password: str


class PasswordChangeIn(Schema):
    current_password: str
    new_password: str


class StaffOut(Schema):
    id: str
    email: str
    full_name: str
    is_staff: bool
    is_superuser: bool


class MeOut(Schema):
    user: StaffOut


class CsrfOut(Schema):
    csrfToken: str


class MessageOut(Schema):
    ok: bool


class InviteIn(Schema):
    email: str
    full_name: str = ""
    access_pme: bool = True
    access_cabinet: bool = True
    notes: str = ""
    send_email: bool = True


class GrantPatchIn(Schema):
    access_pme: bool | None = None
    access_cabinet: bool | None = None
    notes: str | None = None
    send_email: bool = False


class GrantOut(Schema):
    id: str
    email: str
    full_name: str
    access_pme: bool
    access_cabinet: bool
    is_active: bool
    notes: str
    granted_by_email: str = ""
    last_emailed_at: str | None = None
    created_at: str
    temporary_password: str | None = None
    email_sent: bool = False
    email_error: str = ""


def require_staff(request) -> User:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff or not user.is_active:
        raise HttpError(403, "Console réservée à l'équipe Muhimu.")
    return user


def serialize_staff(user: User) -> StaffOut:
    return StaffOut(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
    )


def serialize_grant(
    grant: DemoGrant,
    password: str | None = None,
    *,
    email_sent: bool = False,
    email_error: str = "",
) -> GrantOut:
    return GrantOut(
        id=str(grant.id),
        email=grant.user.email,
        full_name=grant.user.full_name,
        access_pme=grant.access_pme,
        access_cabinet=grant.access_cabinet,
        is_active=grant.is_active,
        notes=grant.notes,
        granted_by_email=grant.granted_by.email if grant.granted_by_id else "",
        last_emailed_at=grant.last_emailed_at.isoformat() if grant.last_emailed_at else None,
        created_at=grant.created_at.isoformat(),
        temporary_password=password,
        email_sent=email_sent,
        email_error=email_error,
    )


def _maybe_email_grant(grant: DemoGrant, password: str | None, send_email: bool) -> tuple[bool, str]:
    if not send_email:
        return False, ""
    return deliver_demo_mail(grant, password)


@router.get("/health", auth=None, response=dict)
def health(request):
    return {"status": "ok", "role": "platform"}


@router.get("/csrf", auth=None, response=CsrfOut)
def csrf_token(request):
    return CsrfOut(csrfToken=get_token(request))


@router.post("/auth/login", auth=None, response=MeOut)
def auth_login(request, payload: LoginIn):
    user = attempt_password_login(
        request,
        scope="platform",
        email=payload.email,
        password=payload.password,
        require_staff=True,
        audit_action="platform.login",
    )
    return MeOut(user=serialize_staff(user))


@router.post("/auth/logout", auth=None, response=MessageOut)
def auth_logout(request):
    if request.user.is_authenticated:
        record_audit(
            request,
            action="platform.logout",
            resource_type="user",
            resource_id=str(request.user.id),
        )
    logout(request)
    return MessageOut(ok=True)


@router.get("/auth/me", response=MeOut)
def auth_me(request):
    user = require_staff(request)
    return MeOut(user=serialize_staff(user))


@router.post("/auth/password/change", response=MessageOut)
def auth_password_change(request, payload: PasswordChangeIn):
    user = require_staff(request)
    if not user.check_password(payload.current_password):
        raise HttpError(400, "Mot de passe actuel incorrect.")
    try:
        validate_password(payload.new_password, user=user)
    except ValidationError as exc:
        raise HttpError(400, "; ".join(exc.messages)) from exc
    user.set_password(payload.new_password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    record_audit(
        request,
        action="platform.password_change",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"scope": "platform"},
    )
    return MessageOut(ok=True)


@router.get("/demo/grants", response=list[GrantOut])
def list_grants(request):
    require_staff(request)
    grants = DemoGrant.objects.select_related("user", "granted_by").order_by("-created_at")
    return [serialize_grant(g) for g in grants]


@router.post("/demo/grants", response={201: GrantOut})
def invite_grant(request, payload: InviteIn):
    staff = require_staff(request)
    try:
        grant, password = upsert_demo_grant(
            email=payload.email,
            full_name=payload.full_name,
            access_pme=payload.access_pme,
            access_cabinet=payload.access_cabinet,
            notes=payload.notes,
            granted_by=staff,
            send_email=False,
            reset_password=True,
            activate=True,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except DemoSandboxMissing as exc:
        raise HttpError(409, str(exc)) from exc
    email_sent, email_error = _maybe_email_grant(grant, password, payload.send_email)
    record_audit(
        request,
        action="platform.demo.invite",
        resource_type="demo_grant",
        resource_id=str(grant.id),
        metadata={"email": grant.user.email, "email_sent": email_sent},
    )
    return 201, serialize_grant(grant, password, email_sent=email_sent, email_error=email_error)


@router.patch("/demo/grants/{grant_id}", response=GrantOut)
def patch_grant(request, grant_id: str, payload: GrantPatchIn):
    staff = require_staff(request)
    grant = DemoGrant.objects.select_related("user").filter(id=grant_id).first()
    if grant is None:
        raise HttpError(404, "Accès démo introuvable.")
    try:
        grant, password = upsert_demo_grant(
            email=grant.user.email,
            full_name=grant.user.full_name,
            access_pme=grant.access_pme if payload.access_pme is None else payload.access_pme,
            access_cabinet=grant.access_cabinet if payload.access_cabinet is None else payload.access_cabinet,
            notes=grant.notes if payload.notes is None else payload.notes,
            granted_by=staff,
            send_email=False,
            reset_password=payload.send_email,
            activate=True,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except DemoSandboxMissing as exc:
        raise HttpError(409, str(exc)) from exc
    email_sent, email_error = _maybe_email_grant(grant, password, payload.send_email)
    return serialize_grant(grant, password, email_sent=email_sent, email_error=email_error)


@router.post("/demo/grants/{grant_id}/resend", response=GrantOut)
def resend_grant(request, grant_id: str):
    staff = require_staff(request)
    grant = DemoGrant.objects.select_related("user").filter(id=grant_id).first()
    if grant is None:
        raise HttpError(404, "Accès démo introuvable.")
    try:
        grant, password = upsert_demo_grant(
            email=grant.user.email,
            full_name=grant.user.full_name,
            access_pme=grant.access_pme,
            access_cabinet=grant.access_cabinet,
            notes=grant.notes,
            granted_by=staff,
            send_email=False,
            reset_password=True,
            activate=True,
        )
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except DemoSandboxMissing as exc:
        raise HttpError(409, str(exc)) from exc
    email_sent, email_error = _maybe_email_grant(grant, password, True)
    record_audit(
        request,
        action="platform.demo.resend",
        resource_type="demo_grant",
        resource_id=str(grant.id),
        metadata={"email_sent": email_sent},
    )
    return serialize_grant(grant, password, email_sent=email_sent, email_error=email_error)


@router.post("/demo/grants/{grant_id}/revoke", response=GrantOut)
def revoke_grant(request, grant_id: str):
    require_staff(request)
    grant = DemoGrant.objects.select_related("user").filter(id=grant_id).first()
    if grant is None:
        raise HttpError(404, "Accès démo introuvable.")
    try:
        grant = revoke_demo_grant(grant)
    except DemoSandboxMissing as exc:
        raise HttpError(409, str(exc)) from exc
    record_audit(
        request,
        action="platform.demo.revoke",
        resource_type="demo_grant",
        resource_id=str(grant.id),
    )
    return serialize_grant(grant)


class TenantOfficerOut(Schema):
    full_name: str
    role: str
    role_label: str


class TenantCompanyOut(Schema):
    id: str
    name: str
    legal_name: str
    country_code: str
    country_label: str
    currency_code: str
    rccm: str
    tax_id: str
    legal_form: str
    legal_form_label: str
    tax_regime: str
    tax_regime_label: str
    accounting_regime: str
    accounting_regime_label: str
    activity_kind: str
    activity_label: str
    city: str
    address: str
    is_active: bool
    identity_complete: bool
    identity_missing: list[str]
    officers: list[TenantOfficerOut]
    created_at: str | None = None


class TenantMemberOut(Schema):
    id: str
    email: str
    full_name: str
    role: str
    role_label: str
    is_active: bool
    last_login: str | None = None
    date_joined: str | None = None


class TenantOrgOut(Schema):
    id: str
    name: str
    slug: str
    type: str
    type_label: str
    is_demo: bool
    setup_data: str
    identity_complete: bool
    company_count: int
    member_count: int
    created_at: str | None = None
    updated_at: str | None = None
    companies: list[TenantCompanyOut]
    members: list[TenantMemberOut]


class TenantDirectoryOut(Schema):
    org_count: int
    pme_count: int
    cabinet_count: int
    demo_count: int
    client_count: int
    company_count: int
    user_count: int
    organizations: list[TenantOrgOut]


class UserOrgOut(Schema):
    id: str
    name: str
    slug: str
    type: str
    type_label: str
    is_demo: bool
    role: str
    role_label: str


class PlatformUserOut(Schema):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_staff: bool
    last_login: str | None = None
    date_joined: str | None = None
    has_demo_grant: bool
    organizations: list[UserOrgOut]


@router.get("/tenants", response=TenantDirectoryOut)
def list_tenants(request):
    require_staff(request)
    return tenant_directory()


@router.get("/users", response=list[PlatformUserOut])
def list_platform_users(request):
    require_staff(request)
    return user_directory()


class ChartPointOut(Schema):
    label: str
    value: int
    code: str = ""


class DashboardKpisOut(Schema):
    org_count: int
    client_count: int
    demo_count: int
    company_count: int
    user_count: int
    grants_active: int
    identity_complete: int
    identity_incomplete: int
    identity_rate: int
    users_active_7d: int
    users_never: int
    entries_posted: int
    entries_draft: int


class DashboardWatchOut(Schema):
    id: str
    name: str
    slug: str
    type_label: str
    reason: str


class DashboardRecentOut(Schema):
    id: str
    name: str
    slug: str
    type_label: str
    is_demo: bool
    created_at: str | None = None


class DashboardGrantsOut(Schema):
    active: int
    revoked: int


class DashboardOut(Schema):
    kpis: DashboardKpisOut
    by_type: list[ChartPointOut]
    by_kind: list[ChartPointOut]
    by_identity: list[ChartPointOut]
    by_country: list[ChartPointOut]
    orgs_by_week: list[ChartPointOut]
    users_by_week: list[ChartPointOut]
    grants: DashboardGrantsOut
    watch: list[DashboardWatchOut]
    recent: list[DashboardRecentOut]


@router.get("/dashboard", response=DashboardOut)
def platform_dashboard(request):
    require_staff(request)
    return dashboard_payload()


class MailStatusOut(Schema):
    provider: str
    host: str
    port: int
    use_ssl: bool
    use_tls: bool
    username: str
    from_email: str
    password_set: bool
    backend: str
    mode: str
    configured: bool
    erp_url: str


class MailTestIn(Schema):
    to: str = ""


class MailTestOut(Schema):
    ok: bool
    to: str
    from_email: str
    mode: str
    message: str


@router.get("/mail/status", response=MailStatusOut)
def get_mail_status(request):
    require_staff(request)
    return mail_status()


@router.post("/mail/test", response=MailTestOut)
def post_mail_test(request, payload: MailTestIn):
    staff = require_staff(request)
    recipient = (payload.to or staff.email).lower().strip()
    status = mail_status()
    try:
        send_test_mail(recipient)
    except ValueError as exc:
        raise HttpError(400, str(exc)) from exc
    except Exception as exc:
        raise HttpError(502, f"Envoi impossible : {exc}") from exc
    record_audit(
        request,
        action="platform.mail.test",
        resource_type="mail",
        metadata={"to": recipient, "mode": status["mode"]},
    )
    return MailTestOut(
        ok=True,
        to=recipient,
        from_email=status["from_email"],
        mode=status["mode"],
        message="E-mail de test envoyé." if status["configured"] else "E-mail écrit (mode console / test).",
    )
