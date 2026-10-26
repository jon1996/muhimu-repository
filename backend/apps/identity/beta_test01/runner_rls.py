"""Contexte RLS pour commandes / runners bêta (équivalent middleware sans HTTP).

Sous ``muhimu_app``, les ORM sur ``Organization`` / ``Company`` exigent
``app.current_user_id`` (et souvent ``app.current_organization_id``), comme
``TenantMiddleware`` le pose sur les requêtes authentifiées.
"""

from __future__ import annotations

from contextlib import contextmanager

from apps.identity.models import User
from apps.tenancy.models import Company, Organization
from apps.tenancy.rls import tenant_context

from apps.identity.beta_test01.constants import COMPANY_ISOL, COMPANY_MAIN, ORG_SLUG

RUNNER_OWNER_EMAIL = "beta-test.owner@beta-test.muhimu.local"


@contextmanager
def beta_runner_tenant_context(*, organization_id: str | None = None):
    owner = User.objects.get(email=RUNNER_OWNER_EMAIL)
    org_id = organization_id or ""
    with tenant_context(user_id=str(owner.id), organization_id=org_id):
        yield owner


def org_and_companies_for_runner() -> tuple[Organization, Company, Company]:
    with beta_runner_tenant_context() as owner:
        org = Organization.objects.get(slug=ORG_SLUG)
        with tenant_context(user_id=str(owner.id), organization_id=str(org.id)):
            co_main = Company.objects.get(organization=org, name=COMPANY_MAIN)
            co_isol = Company.objects.get(organization=org, name=COMPANY_ISOL)
        return org, co_main, co_isol
