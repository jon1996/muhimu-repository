"""Adresses de développement (@muhimu.local) vs production."""

from __future__ import annotations

from django.conf import settings
from django.db.models import QuerySet

LOCAL_DEV_DOMAIN = "muhimu.local"


def is_local_dev_email(email: str) -> bool:
    return (email or "").lower().endswith(f"@{LOCAL_DEV_DOMAIN}")


def allow_local_dev_accounts() -> bool:
    return bool(getattr(settings, "BOOTSTRAP_LOCAL_ACCOUNTS", settings.DEBUG))


def reject_local_email_in_production(email: str) -> str:
    cleaned = (email or "").lower().strip()
    if not allow_local_dev_accounts() and is_local_dev_email(cleaned):
        raise ValueError("Les adresses @muhimu.local sont réservées au développement local.")
    return cleaned


def visible_users() -> QuerySet:
    from apps.identity.models import User

    queryset = User.objects.all()
    if not allow_local_dev_accounts():
        queryset = queryset.exclude(email__iendswith=f"@{LOCAL_DEV_DOMAIN}")
    return queryset
