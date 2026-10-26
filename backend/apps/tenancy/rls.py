"""Contexte RLS PostgreSQL (A1′).

Menace modèle : ``app.current_user_id`` / ``app.current_organization_id`` sont des
GUC de session posés par Django — **pas** une preuve cryptographique d'identité.
Ils protègent contre les oublis de filtre ORM sous ``muhimu_app``. Une compromission
SQL sous ce rôle peut forger les GUC ; le contournement total via
``app.bypass_rls`` a été retiré (A1′). Les opérations privilégiées utilisent un
rôle PostgreSQL distinct avec ``BYPASSRLS`` (``muhimu`` / ``muhimu_platform``).
"""

from __future__ import annotations

from contextlib import contextmanager

from django.db import connection


def bind_tenant_context(
    *,
    user_id: str | None = "",
    organization_id: str | None = "",
    is_local: bool = False,
) -> None:
    """Pose le contexte tenant pour la session (ou la transaction si is_local)."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_user_id', %s, %s)",
            [str(user_id or ""), is_local],
        )
        cursor.execute(
            "SELECT set_config('app.current_organization_id', %s, %s)",
            [str(organization_id or ""), is_local],
        )


def clear_tenant_context(*, is_local: bool = False) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.current_user_id', '', %s)", [is_local])
        cursor.execute(
            "SELECT set_config('app.current_organization_id', '', %s)", [is_local]
        )


@contextmanager
def tenant_context(
    *,
    user_id: str | None = "",
    organization_id: str | None = "",
    is_local: bool = False,
):
    """Context manager pour Celery / commandes (fail closed hors contexte)."""
    bind_tenant_context(
        user_id=user_id, organization_id=organization_id, is_local=is_local
    )
    try:
        yield
    finally:
        clear_tenant_context(is_local=is_local)


@contextmanager
def bypass_rls():
    """Compatibilité : no-op sous A1′.

    Le GUC ``app.bypass_rls`` est ignoré. Les commandes bootstrap / migrate doivent
    s'exécuter sous ``muhimu`` (superuser) ou ``muhimu_platform`` (BYPASSRLS).
    """
    yield
