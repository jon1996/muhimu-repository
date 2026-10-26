from ninja import Router, Schema
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.middleware.csrf import get_token
from ninja.errors import HttpError

from apps.audit.services import record_audit
from apps.identity.auth_login import attempt_password_login
from apps.identity.models import User
from apps.identity.session_policy import session_status_payload
from apps.platform.access import user_can_access_organization
from apps.tenancy.models import Membership
from apps.tenancy.schemas import MembershipOut, OrganizationOut

router = Router(tags=["identity"])


class LoginIn(Schema):
    email: str
    password: str


class PasswordChangeIn(Schema):
    current_password: str
    new_password: str


class UserOut(Schema):
    id: str
    email: str
    full_name: str
    is_staff: bool


class MeOut(Schema):
    user: UserOut
    memberships: list[MembershipOut]


class CsrfOut(Schema):
    csrfToken: str


class MessageOut(Schema):
    ok: bool


class SessionStatusOut(Schema):
    authenticated: bool
    idle_timeout_seconds: int
    absolute_timeout_seconds: int
    warn_before_seconds: int
    auth_at: float | None
    last_activity_at: float | None
    idle_expires_at: float | None
    absolute_expires_at: float | None


def serialize_user(user: User) -> UserOut:
    return UserOut(id=str(user.id), email=user.email, full_name=user.full_name, is_staff=user.is_staff)


@router.get("/health", auth=None, response=dict)
def health(request):
    return {"status": "ok"}


@router.get("/csrf", auth=None, response=CsrfOut)
def csrf_token(request):
    return CsrfOut(csrfToken=get_token(request))


@router.post("/auth/login", auth=None, response=MeOut)
def auth_login(request, payload: LoginIn):
    user = attempt_password_login(
        request,
        scope="erp",
        email=payload.email,
        password=payload.password,
        require_staff=False,
        audit_action="auth.login",
    )
    return _me_payload(user)


@router.post("/auth/logout", auth=None, response=MessageOut)
def auth_logout(request):
    if request.user.is_authenticated:
        record_audit(
            request,
            action="auth.logout",
            resource_type="user",
            resource_id=str(request.user.id),
        )
    logout(request)
    return MessageOut(ok=True)


@router.get("/auth/me", response=MeOut)
def auth_me(request):
    return _me_payload(request.user)


@router.get("/auth/session", response=SessionStatusOut)
def auth_session_status(request):
    """Métadonnées d'expiration — ne compte pas comme activité utilisateur."""
    return SessionStatusOut(**session_status_payload(request))


@router.post("/auth/password/change", response=MessageOut)
def auth_password_change(request, payload: PasswordChangeIn):
    user = request.user
    if not user.is_authenticated or not user.is_active:
        raise HttpError(401, "Authentification requise.")
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
        action="auth.password_change",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"scope": "erp"},
    )
    return MessageOut(ok=True)


def _me_payload(user: User) -> MeOut:
    memberships = [
        m
        for m in (
            Membership.objects.filter(user=user, is_active=True)
            .select_related("organization")
            .order_by("organization__name")
        )
        if user_can_access_organization(user, m.organization)
    ]
    return MeOut(
        user=serialize_user(user),
        memberships=[
            MembershipOut(
                id=str(m.id),
                role=m.role,
                organization=OrganizationOut(
                    id=str(m.organization_id),
                    name=m.organization.name,
                    slug=m.organization.slug,
                    type=m.organization.type,
                    setup_data=m.organization.setup_data or "",
                    is_demo=bool(m.organization.is_demo),
                ),
            )
            for m in memberships
        ],
    )
