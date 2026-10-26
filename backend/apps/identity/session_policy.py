"""Politique de session ERP/console : plafond absolu + expiration d'inactivité."""

from __future__ import annotations

from typing import Literal

from django.conf import settings
from django.utils import timezone

SESSION_AUTH_AT_KEY = "_muhimu_auth_at"
SESSION_LAST_ACTIVITY_KEY = "_muhimu_last_activity_at"

SessionExpiryReason = Literal["idle", "absolute"]


def _now_ts() -> float:
    return timezone.now().timestamp()


def stamp_session_on_login(request) -> None:
    now = _now_ts()
    request.session[SESSION_AUTH_AT_KEY] = now
    request.session[SESSION_LAST_ACTIVITY_KEY] = now
    request.session.modified = True


def _ensure_session_timestamps(request) -> tuple[float, float]:
    """Sessions antérieures à SEC-SESSION-01 : ancrage au premier passage authentifié."""
    now = _now_ts()
    auth_at = request.session.get(SESSION_AUTH_AT_KEY)
    last_at = request.session.get(SESSION_LAST_ACTIVITY_KEY)
    if auth_at is None or last_at is None:
        auth_at = last_at = now
        request.session[SESSION_AUTH_AT_KEY] = auth_at
        request.session[SESSION_LAST_ACTIVITY_KEY] = last_at
        request.session.modified = True
    return float(auth_at), float(last_at)


def path_skips_idle_touch(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    for prefix in getattr(settings, "SESSION_IDLE_NO_TOUCH_PREFIXES", ()):
        p = prefix.rstrip("/") or "/"
        if normalized == p or normalized.startswith(p + "/"):
            return True
    return False


def request_counts_as_session_activity(request) -> bool:
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return False
    if request.method in ("HEAD", "OPTIONS", "TRACE"):
        return False
    if path_skips_idle_touch(request.path):
        return False
    if request.headers.get("X-Muhimu-Session-Activity", "").lower() == "background":
        return False
    return True


def session_expiry_reason(request) -> SessionExpiryReason | None:
    if not getattr(settings, "SESSION_POLICY_ENABLED", True):
        return None
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None

    auth_at, last_at = _ensure_session_timestamps(request)
    now = _now_ts()
    absolute_limit = int(getattr(settings, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 43200))
    idle_limit = int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))

    if now - auth_at > absolute_limit:
        return "absolute"
    if now - last_at > idle_limit:
        return "idle"
    return None


def touch_session_activity(request) -> None:
    if not request_counts_as_session_activity(request):
        return
    request.session[SESSION_LAST_ACTIVITY_KEY] = _now_ts()
    request.session.modified = True


def session_status_payload(request) -> dict:
    idle_limit = int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))
    absolute_limit = int(getattr(settings, "SESSION_ABSOLUTE_TIMEOUT_SECONDS", 43200))
    warn = int(getattr(settings, "SESSION_IDLE_WARN_BEFORE_SECONDS", 300))
    if not request.user.is_authenticated:
        return {
            "authenticated": False,
            "idle_timeout_seconds": idle_limit,
            "absolute_timeout_seconds": absolute_limit,
            "warn_before_seconds": warn,
            "auth_at": None,
            "last_activity_at": None,
            "idle_expires_at": None,
            "absolute_expires_at": None,
        }
    auth_at, last_at = _ensure_session_timestamps(request)
    return {
        "authenticated": True,
        "idle_timeout_seconds": idle_limit,
        "absolute_timeout_seconds": absolute_limit,
        "warn_before_seconds": warn,
        "auth_at": auth_at,
        "last_activity_at": last_at,
        "idle_expires_at": last_at + idle_limit,
        "absolute_expires_at": auth_at + absolute_limit,
    }
