"""Helpers partagés login ERP / console (throttle, audit, messages génériques)."""

from __future__ import annotations

from django.contrib.auth import authenticate, login

from apps.audit.services import record_audit
from apps.identity.client_ip import client_ip
from apps.identity.emails import allow_local_dev_accounts, is_local_dev_email
from apps.identity.login_throttle import (
    clear_login_failures,
    enforce_login_allowed,
    raise_if_locked_after_failure,
)
from apps.identity.models import User
from ninja.errors import HttpError

INVALID_CREDENTIALS = "Identifiants invalides."


def attempt_password_login(
    request,
    *,
    scope: str,
    email: str,
    password: str,
    require_staff: bool = False,
    audit_action: str = "auth.login",
) -> User:
    """
    Authentifie sans fuite d'existence de compte.
    Ne journalise jamais le mot de passe.
    login() Django cycle la clé de session (anti-fixation).
    """
    normalized = (email or "").lower().strip()
    ip = client_ip(request)

    enforce_login_allowed(scope=scope, email=normalized, ip=ip)

    if not allow_local_dev_accounts() and is_local_dev_email(normalized):
        raise_if_locked_after_failure(scope=scope, email=normalized, ip=ip)
        raise HttpError(401, INVALID_CREDENTIALS)

    user = authenticate(request, username=normalized, password=password)
    if user is None or not user.is_active:
        raise_if_locked_after_failure(scope=scope, email=normalized, ip=ip)
        raise HttpError(401, INVALID_CREDENTIALS)

    if require_staff and not user.is_staff:
        # Mot de passe correct mais non autorisé console : ne pas compter comme
        # échec brute-force (évite DoS d'un staff via un compte ERP connu).
        raise HttpError(403, "Ce compte n'a pas accès à la console SaaS.")

    clear_login_failures(scope=scope, email=normalized, ip=ip)
    login(request, user)
    record_audit(
        request,
        action=audit_action,
        resource_type="user",
        resource_id=str(user.id),
        metadata={"scope": scope},
    )
    return user
