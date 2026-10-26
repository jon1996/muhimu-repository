"""Conversion SME → CABINET pour beta-test-01 uniquement (BETA-UAT-02)."""

from __future__ import annotations

from django.db import transaction

from apps.identity.beta_test01.constants import COMPANY_ISOL, COMPANY_MAIN, ORG_SLUG, USER_SPECS
from apps.identity.beta_test01.provision import assert_beta_database
from apps.ledger.models import Entry, EntryStatus
from apps.platform.models import DemoGrant
from apps.tenancy.models import (
    Company,
    CompanyAccess,
    Membership,
    Organization,
    OrganizationType,
    Role,
)
from apps.tenancy.rls import bypass_rls


def convert_beta_test01_to_cabinet() -> dict:
    assert_beta_database()
    summary: dict = {"org_slug": ORG_SLUG, "actions": []}

    with bypass_rls(), transaction.atomic():
        org = Organization.objects.filter(slug=ORG_SLUG).first()
        if org is None:
            raise RuntimeError(f"Organisation {ORG_SLUG!r} absente — rien à convertir.")
        if Organization.objects.exclude(slug=ORG_SLUG).exists():
            raise RuntimeError("Refus : d'autres organisations existent — conversion hors périmètre.")

        prev_type = org.type
        org.type = OrganizationType.CABINET
        org.is_demo = True
        org.save(update_fields=["type", "is_demo", "updated_at"])
        summary["actions"].append(f"type: {prev_type} → cabinet")

        co_main = Company.objects.get(organization=org, name=COMPANY_MAIN)
        co_isol = Company.objects.get(organization=org, name=COMPANY_ISOL)

        users_by_key = {}
        role_map = {
            "owner": Role.OWNER,
            "accountant": Role.ACCOUNTANT,
            "viewer": Role.VIEWER,
            "isol": Role.VIEWER,
        }
        for email, _full, role_key in USER_SPECS:
            membership = Membership.objects.select_related("user").get(
                organization=org, user__email=email
            )
            users_by_key[role_key] = membership.user
            if membership.role != role_map[role_key]:
                membership.role = role_map[role_key]
                membership.save(update_fields=["role"])

        owner = users_by_key["owner"]
        accountant = users_by_key["accountant"]
        viewer = users_by_key["viewer"]
        isol_user = users_by_key["isol"]

        # Réinitialise les accès dossier (cabinet) — owner/admin : implicite via middleware.
        CompanyAccess.objects.filter(organization=org).delete()
        summary["actions"].append("companyaccess: reset")

        for user in (owner, accountant, viewer):
            CompanyAccess.objects.create(organization=org, company=co_main, user=user)
        CompanyAccess.objects.create(organization=org, company=co_isol, user=owner)
        CompanyAccess.objects.create(organization=org, company=co_isol, user=isol_user)

        for user in users_by_key.values():
            DemoGrant.objects.update_or_create(
                user=user,
                defaults={
                    "access_pme": True,
                    "access_cabinet": True,
                    "is_active": True,
                    "notes": "BETA-TEST-01 sandbox fictif",
                },
            )

        summary["company_ids"] = {"main": str(co_main.id), "isol": str(co_isol.id)}
        summary["entry_counts"] = {
            "main": Entry.objects.filter(
                company=co_main, status=EntryStatus.POSTED
            ).count(),
            "isol": Entry.objects.filter(
                company=co_isol, status=EntryStatus.POSTED
            ).count(),
        }
    return summary
