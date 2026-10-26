"""Annuaire SaaS — organisations, sociétés et utilisateurs (vue staff)."""

from __future__ import annotations

from django.db.models import Prefetch

from apps.identity.emails import visible_users
from apps.platform.models import DemoGrant
from apps.tenancy.liasse import LEGAL_FORM_LABELS, TAX_REGIME_LABELS, identity_missing_fields
from apps.tenancy.models import Company, Membership, Organization, OrganizationType
from apps.tenancy.ohada import country_label

ROLE_LABELS = {
    "owner": "Propriétaire",
    "admin": "Administrateur",
    "accountant": "Comptable",
    "auditor": "Auditeur",
    "viewer": "Lecteur",
}
TYPE_LABELS = {"sme": "PME", "cabinet": "Cabinet"}
REGIME_LABELS = {"normal": "Système normal", "smt": "SMT"}
ACTIVITY_LABELS = {"trade": "Négoce", "craft": "Artisanat", "services": "Services"}


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def serialize_company(company: Company) -> dict:
    officers = list(company.officers.all())
    missing = identity_missing_fields(company, officers=officers)
    return {
        "id": str(company.id),
        "name": company.name,
        "legal_name": company.legal_name or company.name,
        "country_code": company.country_code,
        "country_label": country_label(company.country_code),
        "currency_code": company.currency_code,
        "rccm": company.rccm,
        "tax_id": company.tax_id,
        "legal_form": company.legal_form,
        "legal_form_label": LEGAL_FORM_LABELS.get(company.legal_form, company.legal_form),
        "tax_regime": company.tax_regime,
        "tax_regime_label": TAX_REGIME_LABELS.get(company.tax_regime, company.tax_regime),
        "accounting_regime": company.accounting_regime,
        "accounting_regime_label": REGIME_LABELS.get(
            company.accounting_regime, company.accounting_regime
        ),
        "activity_kind": company.activity_kind,
        "activity_label": ACTIVITY_LABELS.get(company.activity_kind, company.activity_kind),
        "city": company.city,
        "address": company.address,
        "is_active": company.is_active,
        "identity_complete": not missing,
        "identity_missing": missing,
        "officers": [
            {
                "full_name": officer.full_name,
                "role": officer.role,
                "role_label": officer.get_role_display(),
            }
            for officer in officers
        ],
        "created_at": _iso(company.created_at),
    }


def serialize_member(membership: Membership) -> dict:
    user = membership.user
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": membership.role,
        "role_label": ROLE_LABELS.get(membership.role, membership.role),
        "is_active": bool(membership.is_active and user.is_active),
        "last_login": _iso(user.last_login),
        "date_joined": _iso(user.date_joined),
    }


def serialize_org(org: Organization) -> dict:
    companies = list(org.companies.all())
    members = list(org.memberships.all())
    complete = bool(companies) and all(
        not identity_missing_fields(company, officers=list(company.officers.all()))
        for company in companies
    )
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "type": org.type,
        "type_label": TYPE_LABELS.get(org.type, org.type),
        "is_demo": bool(org.is_demo),
        "setup_data": org.setup_data or "",
        "identity_complete": complete,
        "company_count": len(companies),
        "member_count": len(members),
        "created_at": _iso(org.created_at),
        "updated_at": _iso(org.updated_at),
        "companies": [serialize_company(company) for company in companies],
        "members": [serialize_member(item) for item in members],
    }


def tenant_directory() -> dict:
    orgs = list(
        Organization.objects.prefetch_related(
            Prefetch(
                "companies",
                queryset=Company.objects.prefetch_related("officers").order_by("name"),
            ),
            Prefetch(
                "memberships",
                queryset=Membership.objects.select_related("user").order_by("role", "user__email"),
            ),
        ).order_by("-created_at")
    )
    serialized = [serialize_org(org) for org in orgs]
    demo_count = sum(1 for org in orgs if org.is_demo)
    return {
        "org_count": len(orgs),
        "pme_count": sum(1 for org in orgs if org.type == OrganizationType.SME),
        "cabinet_count": sum(1 for org in orgs if org.type == OrganizationType.CABINET),
        "demo_count": demo_count,
        "client_count": len(orgs) - demo_count,
        "company_count": sum(item["company_count"] for item in serialized),
        "user_count": visible_users().filter(is_staff=False).count(),
        "organizations": serialized,
    }


def user_directory() -> list[dict]:
    grant_ids = set(DemoGrant.objects.filter(is_active=True).values_list("user_id", flat=True))
    users = visible_users().prefetch_related(
        Prefetch(
            "memberships",
            queryset=Membership.objects.select_related("organization")
            .filter(is_active=True)
            .order_by("organization__name"),
        )
    ).order_by("email")
    rows = []
    for user in users:
        rows.append(
            {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "last_login": _iso(user.last_login),
                "date_joined": _iso(user.date_joined),
                "has_demo_grant": user.id in grant_ids,
                "organizations": [
                    {
                        "id": str(item.organization_id),
                        "name": item.organization.name,
                        "slug": item.organization.slug,
                        "type": item.organization.type,
                        "type_label": TYPE_LABELS.get(item.organization.type, item.organization.type),
                        "is_demo": bool(item.organization.is_demo),
                        "role": item.role,
                        "role_label": ROLE_LABELS.get(item.role, item.role),
                    }
                    for item in user.memberships.all()
                ],
            }
        )
    return rows
