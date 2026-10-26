"""Read-only UAT probes (BETA-UAT-01) — no data mutation."""

from __future__ import annotations

import json

from django.test import Client
from django.test.utils import override_settings

from apps.identity.beta_test01.constants import ORG_SLUG
from apps.identity.beta_test01.provision import default_password
from apps.identity.beta_test01.runner_rls import beta_runner_tenant_context, org_and_companies_for_runner
from apps.tenancy.middleware import user_can_access_company
from apps.tenancy.models import Company, Membership


def run_uat_probes() -> dict:
    org, co_main, co_isol = org_and_companies_for_runner()
    out: dict = {"org_type": org.type, "org_is_demo": org.is_demo, "access_matrix": []}

    for email in (
        "beta-test.owner@beta-test.muhimu.local",
        "beta-test.isol@beta-test.muhimu.local",
        "beta-test.viewer@beta-test.muhimu.local",
    ):
        with beta_runner_tenant_context(organization_id=str(org.id)):
            membership = Membership.objects.select_related("user", "organization").get(
                organization=org, user__email=email
            )
            row = {
                "email": email,
                "role": membership.role,
                "can_access_main": user_can_access_company(
                    membership.user, membership, co_main
                ),
                "can_access_isol": user_can_access_company(
                    membership.user, membership, co_isol
                ),
                "api_main": None,
                "api_isol": None,
            }
        out["access_matrix"].append(row)

    with override_settings(
        ALLOWED_HOSTS=["testserver", "localhost"],
        AUTH_LOGIN_RATE_LIMIT_ENABLED=False,
    ):
        client = Client()

        def api_status(email: str, company: Company) -> int:
            c = Client()
            login = c.post(
                "/api/auth/login",
                data=json.dumps({"email": email, "password": default_password()}),
                content_type="application/json",
                REMOTE_ADDR="203.0.113.88",
            )
            if login.status_code != 200:
                return login.status_code
            return c.get(
                "/api/ledger/entries",
                HTTP_X_ORGANIZATION_SLUG=ORG_SLUG,
                HTTP_X_COMPANY_ID=str(company.id),
            ).status_code

        for row in out["access_matrix"]:
            email = row["email"]
            row["api_main"] = api_status(email, co_main)
            row["api_isol"] = api_status(email, co_isol)

        owner = Client()
        owner.post(
            "/api/auth/login",
            data=json.dumps(
                {
                    "email": "beta-test.owner@beta-test.muhimu.local",
                    "password": default_password(),
                }
            ),
            content_type="application/json",
            REMOTE_ADDR="203.0.113.88",
        )
        hid = {
            "HTTP_X_ORGANIZATION_SLUG": ORG_SLUG,
            "HTTP_X_COMPANY_ID": str(co_main.id),
        }
        out["beta_scope"] = owner.get("/api/ledger/beta-scope", **hid).json()
        out["consolidation_status"] = owner.get(
            "/api/ledger/consolidation", **hid
        ).status_code
        pdf = owner.get("/api/ledger/statements/pdf?kind=bilan", **hid)
        out["pdf_status"] = pdf.status_code
        out["pdf_has_disclaimer"] = (
            b"DOCUMENT DE TEST" in pdf.content if pdf.status_code == 200 else False
        )

    return out
