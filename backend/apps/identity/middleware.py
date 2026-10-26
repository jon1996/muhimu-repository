"""Expiration absolue et inactivité — après AuthenticationMiddleware."""

from __future__ import annotations

from django.contrib.auth import logout

from apps.identity.session_policy import (
    session_expiry_reason,
    touch_session_activity,
)


class SessionPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._session_expired_reason = None  # noqa: SLF001 — consommé par la couche réponse
        reason = session_expiry_reason(request)
        if reason:
            request._session_expired_reason = reason
            logout(request)
            request.session.flush()
        elif getattr(request, "user", None) and request.user.is_authenticated:
            touch_session_activity(request)

        response = self.get_response(request)

        expired = getattr(request, "_session_expired_reason", None)
        if expired and response.status_code in (401, 403):
            response["X-Muhimu-Session-Expired"] = expired
        return response
