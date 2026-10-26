"""Rate-limit des tentatives de connexion (Redis, fail-closed).

Seuils par défaut (bêta privée) :
- 5 échecs / email / 10 min → lockout 15 min (cible brute-force compte).
- 40 échecs / IP / 10 min → lockout 15 min (spray ; seuil plus haut pour NAT bureau).
Pas de verrouillage permanent.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from django.conf import settings
from ninja.errors import HttpError

logger = logging.getLogger("muhimu.auth")

GENERIC_LOCK_MESSAGE = "Trop de tentatives. Réessayez plus tard."
GENERIC_UNAVAILABLE_MESSAGE = "Authentification temporairement indisponible. Réessayez plus tard."


@dataclass(frozen=True)
class ThrottleDecision:
    allowed: bool
    retry_after: int = 0
    reason: str = ""


class _MemoryStore:
    """Backend mémoire pour tests isolés (pas pour multi-instances)."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> int | None:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            value, expires = item
            if expires < time.time():
                del self._data[key]
                return None
            return value

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            now = time.time()
            item = self._data.get(key)
            if not item or item[1] < now:
                self._data[key] = (1, now + ttl)
                return 1
            value, expires = item
            value += 1
            self._data[key] = (value, expires)
            return value

    def setex(self, key: str, ttl: int, value: int) -> None:
        with self._lock:
            self._data[key] = (value, time.time() + ttl)

    def delete(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._data.pop(key, None)

    def ttl(self, key: str) -> int:
        with self._lock:
            item = self._data.get(key)
            if not item:
                return -2
            remaining = int(item[1] - time.time())
            return remaining if remaining > 0 else -2

    def ping(self) -> bool:
        return True


_memory_singleton: _MemoryStore | None = None


def _memory_store() -> _MemoryStore:
    global _memory_singleton
    if _memory_singleton is None:
        _memory_singleton = _MemoryStore()
    return _memory_singleton


def reset_memory_store() -> None:
    """Réinitialise le store mémoire (tests)."""
    global _memory_singleton
    _memory_singleton = _MemoryStore()


class _RedisStore:
    def __init__(self, client) -> None:
        self._client = client

    def get(self, key: str) -> int | None:
        raw = self._client.get(key)
        if raw is None:
            return None
        return int(raw)

    def incr(self, key: str, ttl: int) -> int:
        count = int(self._client.incr(key))
        if count == 1:
            self._client.expire(key, ttl)
        return count

    def setex(self, key: str, ttl: int, value: int) -> None:
        self._client.setex(key, ttl, value)

    def delete(self, *keys: str) -> None:
        if keys:
            self._client.delete(*keys)

    def ttl(self, key: str) -> int:
        return int(self._client.ttl(key))

    def ping(self) -> bool:
        return bool(self._client.ping())


def _redis_client():
    import redis

    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )


def get_store():
    backend = getattr(settings, "AUTH_LOGIN_THROTTLE_BACKEND", "redis")
    if backend == "memory":
        return _memory_store()
    return _RedisStore(_redis_client())


def _enabled() -> bool:
    return bool(getattr(settings, "AUTH_LOGIN_RATE_LIMIT_ENABLED", True))


def _window() -> int:
    return int(getattr(settings, "AUTH_LOGIN_WINDOW_SECONDS", 600))


def _lockout() -> int:
    return int(getattr(settings, "AUTH_LOGIN_LOCKOUT_SECONDS", 900))


def _max_email() -> int:
    return int(getattr(settings, "AUTH_LOGIN_MAX_ATTEMPTS_EMAIL", 5))


def _max_ip() -> int:
    return int(getattr(settings, "AUTH_LOGIN_MAX_ATTEMPTS_IP", 40))


def _keys(scope: str, email: str, ip: str) -> dict[str, str]:
    email_n = (email or "").strip().lower()
    ip_n = (ip or "unknown").strip()
    prefix = f"muhimu:auth:login:{scope}"
    return {
        "fail_email": f"{prefix}:fail:email:{email_n}",
        "fail_ip": f"{prefix}:fail:ip:{ip_n}",
        "lock_email": f"{prefix}:lock:email:{email_n}",
        "lock_ip": f"{prefix}:lock:ip:{ip_n}",
    }


def check_login_allowed(*, scope: str, email: str, ip: str) -> ThrottleDecision:
    if not _enabled():
        return ThrottleDecision(allowed=True)

    try:
        store = get_store()
        store.ping()
    except Exception:
        logger.warning("login_throttle_unavailable scope=%s", scope)
        return ThrottleDecision(allowed=False, retry_after=60, reason="unavailable")

    keys = _keys(scope, email, ip)
    try:
        for lock_key in (keys["lock_email"], keys["lock_ip"]):
            ttl = store.ttl(lock_key)
            if ttl and ttl > 0:
                return ThrottleDecision(allowed=False, retry_after=ttl, reason="locked")
            if store.get(lock_key) is not None:
                return ThrottleDecision(allowed=False, retry_after=_lockout(), reason="locked")
    except Exception:
        logger.warning("login_throttle_check_failed scope=%s", scope)
        return ThrottleDecision(allowed=False, retry_after=60, reason="unavailable")

    return ThrottleDecision(allowed=True)


def register_login_failure(*, scope: str, email: str, ip: str) -> ThrottleDecision:
    """Incrémente les compteurs ; active un lockout temporaire si seuil atteint."""
    if not _enabled():
        return ThrottleDecision(allowed=True)

    try:
        store = get_store()
        store.ping()
    except Exception:
        logger.warning("login_throttle_unavailable scope=%s", scope)
        return ThrottleDecision(allowed=False, retry_after=60, reason="unavailable")

    keys = _keys(scope, email, ip)
    window = _window()
    lockout = _lockout()
    try:
        email_count = store.incr(keys["fail_email"], window)
        ip_count = store.incr(keys["fail_ip"], window)
        locked = False
        retry = 0
        if email_count >= _max_email():
            store.setex(keys["lock_email"], lockout, 1)
            locked = True
            retry = max(retry, lockout)
            logger.warning(
                "login_lockout scope=%s dimension=email attempts=%s",
                scope,
                email_count,
            )
        if ip_count >= _max_ip():
            store.setex(keys["lock_ip"], lockout, 1)
            locked = True
            retry = max(retry, lockout)
            logger.warning(
                "login_lockout scope=%s dimension=ip attempts=%s",
                scope,
                ip_count,
            )
        if locked:
            return ThrottleDecision(allowed=False, retry_after=retry or lockout, reason="locked")
        return ThrottleDecision(allowed=True)
    except Exception:
        logger.warning("login_throttle_register_failed scope=%s", scope)
        return ThrottleDecision(allowed=False, retry_after=60, reason="unavailable")


def clear_login_failures(*, scope: str, email: str, ip: str) -> None:
    """Réinitialise les compteurs email après succès (IP conservée anti-spray)."""
    if not _enabled():
        return
    try:
        store = get_store()
        keys = _keys(scope, email, ip)
        store.delete(keys["fail_email"], keys["lock_email"])
    except Exception:
        logger.warning("login_throttle_clear_failed scope=%s", scope)


def enforce_login_allowed(*, scope: str, email: str, ip: str) -> None:
    decision = check_login_allowed(scope=scope, email=email, ip=ip)
    if decision.allowed:
        return
    headers = {}
    if decision.retry_after:
        headers["Retry-After"] = str(decision.retry_after)
    if decision.reason == "unavailable":
        raise HttpError(503, GENERIC_UNAVAILABLE_MESSAGE)
    raise HttpError(429, GENERIC_LOCK_MESSAGE)


def raise_if_locked_after_failure(*, scope: str, email: str, ip: str) -> None:
    decision = register_login_failure(scope=scope, email=email, ip=ip)
    if decision.allowed:
        return
    if decision.reason == "unavailable":
        raise HttpError(503, GENERIC_UNAVAILABLE_MESSAGE)
    raise HttpError(429, GENERIC_LOCK_MESSAGE)
