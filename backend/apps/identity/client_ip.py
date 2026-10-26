"""Résolution d'IP client pour auth / audit — ne pas faire confiance aux en-têtes libres."""

from __future__ import annotations

import ipaddress

from django.conf import settings


def _parse_networks(raw: str) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    for part in (raw or "").split(","):
        token = part.strip()
        if not token:
            continue
        try:
            if "/" in token:
                nets.append(ipaddress.ip_network(token, strict=False))
            else:
                ip = ipaddress.ip_address(token)
                nets.append(ipaddress.ip_network(f"{ip}/{ip.max_prefixlen}", strict=False))
        except ValueError:
            continue
    return nets


def _remote_is_trusted(remote: str) -> bool:
    if not remote:
        return False
    if getattr(settings, "AUTH_TRUST_PROXY", False):
        allowlist = _parse_networks(getattr(settings, "AUTH_TRUSTED_PROXIES", "") or "")
        if not allowlist:
            # Backend non exposé + reverse proxy unique (bêta) : on accepte.
            return True
        try:
            addr = ipaddress.ip_address(remote)
        except ValueError:
            return False
        return any(addr in net for net in allowlist)
    return False


def client_ip(request) -> str:
    """
    IP pour rate-limit / audit.

    - Sans proxy de confiance : REMOTE_ADDR uniquement (ignore X-Forwarded-For / X-Real-IP).
    - Avec proxy de confiance : privilégie X-Real-IP (posé par nginx à $remote_addr),
      sinon le dernier hop de X-Forwarded-For ajouté par le proxy.
    """
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    if _remote_is_trusted(remote):
        real = (request.META.get("HTTP_X_REAL_IP") or "").strip()
        if real:
            return real.split(",")[0].strip() or remote or "unknown"
        forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
        if forwarded:
            # nginx $proxy_add_x_forwarded_for append : le dernier élément est le pair TCP.
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                return parts[-1]
    return remote or "unknown"
