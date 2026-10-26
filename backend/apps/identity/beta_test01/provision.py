from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.identity.beta_test01.constants import (
    CLOSE_YEAR,
    COMPANY_ISOL,
    COMPANY_MAIN,
    OPERATIONS_YEAR,
    ORG_NAME,
    ORG_SLUG,
    PROVISION_TAG,
    SALE_AMOUNT,
    SALE_CREDIT_ACCOUNT,
    SALE_DEBIT_ACCOUNT,
    THIRD_PARTIES,
    USER_SPECS,
)
from apps.identity.models import User
from apps.platform.models import DemoGrant
from apps.ledger.models import Account, Entry, Exercise, ExerciseStatus, Journal, PartyKind, ThirdParty
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.services.setup import ensure_company_ledger
from apps.tenancy.models import (
    Company,
    CompanyAccess,
    Membership,
    Organization,
    OrganizationType,
    Role,
)
from apps.tenancy.rls import bypass_rls


def assert_beta_database() -> str:
    db = settings.DATABASES["default"]["NAME"]
    allowed = os.getenv("BETA_TEST01_ALLOWED_DB", "muhimu_beta").split(",")
    if db not in allowed:
        raise RuntimeError(
            f"Refus provisioning : base={db!r}, attendu une de {allowed!r}. "
            "Cible non bêta ou confirmation manquante."
        )
    return db


def default_password(*, required: bool = True) -> str:
    pwd = (os.getenv("BETA_TEST01_DEFAULT_PASSWORD") or "").strip()
    if not pwd:
        if required:
            raise RuntimeError(
                "BETA_TEST01_DEFAULT_PASSWORD manquant — définir dans .env.beta (hors Git)."
            )
        return ""
    return pwd


def _ensure_user(
    email: str, full_name: str, *, staff: bool = False, rotate_password: bool = False
) -> User:
    user, created = User.objects.get_or_create(
        email=email.lower(),
        defaults={"full_name": full_name, "is_active": True},
    )
    if rotate_password or created or not user.has_usable_password():
        user.set_password(default_password())
    user.full_name = full_name
    user.is_active = True
    user.is_staff = staff
    user.is_superuser = staff
    user.save()
    return user


def _company_defaults() -> dict:
    return {
        "legal_name": "",
        "country_code": "CG",
        "currency_code": "XAF",
        "legal_form": "sarl",
        "tax_regime": "reel_normal",
        "control_kind": "private_national",
        "rccm": "CG-BZV-2019-B-99901",
        "tax_id": "CGFICT000999",
        "city": "Brazzaville",
        "address": "14 avenue Matsoua (fictif)",
        "email": "contact@fleuve-congo.demo",
    }


@transaction.atomic
def provision_beta_test01(*, force_entries: bool = False, rotate_passwords: bool = False) -> dict:
    """Crée ou complète l'organisation beta-test-01 (idempotent)."""
    assert_beta_database()
    summary: dict = {"created": [], "skipped": [], "org_slug": ORG_SLUG}

    with bypass_rls():
        org, org_created = Organization.objects.get_or_create(
            slug=ORG_SLUG,
            defaults={
                "name": ORG_NAME,
                "type": OrganizationType.CABINET,
                "is_demo": True,
                "setup_data": PROVISION_TAG,
            },
        )
        if not org_created:
            org.is_demo = True
            org.setup_data = PROVISION_TAG
            org.name = ORG_NAME
            org.type = OrganizationType.CABINET
            org.save(update_fields=["is_demo", "setup_data", "name", "type", "updated_at"])
            summary["skipped"].append("organization")
        else:
            summary["created"].append("organization")

        co_main, main_created = Company.objects.get_or_create(
            organization=org,
            name=COMPANY_MAIN,
            defaults={**_company_defaults(), "legal_name": COMPANY_MAIN, "acronym": "FLEUVE"},
        )
        co_isol, isol_created = Company.objects.get_or_create(
            organization=org,
            name=COMPANY_ISOL,
            defaults={
                **_company_defaults(),
                "legal_name": COMPANY_ISOL,
                "acronym": "NIARI",
                "email": "contact@niari-logistique.demo",
                "rccm": "CG-BZV-2020-B-99902",
            },
        )
        for label, created in (("company_main", main_created), ("company_isol", isol_created)):
            (summary["created"] if created else summary["skipped"]).append(label)

        role_map = {
            "owner": Role.OWNER,
            "accountant": Role.ACCOUNTANT,
            "viewer": Role.VIEWER,
            "isol": Role.VIEWER,
        }
        users: dict[str, User] = {}
        for email, full_name, role_key in USER_SPECS:
            user = _ensure_user(email, full_name, rotate_password=rotate_passwords)
            users[role_key] = user
            role = role_map[role_key]
            _, m_created = Membership.objects.get_or_create(
                organization=org,
                user=user,
                defaults={"role": role},
            )
            if not m_created:
                Membership.objects.filter(organization=org, user=user).update(role=role)
            DemoGrant.objects.update_or_create(
                user=user,
                defaults={
                    "access_pme": True,
                    "access_cabinet": True,
                    "is_active": True,
                    "notes": "BETA-TEST-01 sandbox fictif",
                },
            )

        owner = users["owner"]
        accountant = users["accountant"]
        viewer = users["viewer"]
        isol_user = users["isol"]

        for user in (owner, accountant, viewer):
            CompanyAccess.objects.get_or_create(organization=org, company=co_main, user=user)
        CompanyAccess.objects.get_or_create(organization=org, company=co_isol, user=owner)
        CompanyAccess.objects.get_or_create(organization=org, company=co_isol, user=isol_user)
        # Comptable / viewer : dossier Fleuve uniquement ; isol_user : Niari uniquement.

        ex_main_26 = ensure_company_ledger(co_main, year=OPERATIONS_YEAR)
        ex_main_25 = ensure_company_ledger(co_main, year=CLOSE_YEAR)
        ex_isol_26 = ensure_company_ledger(co_isol, year=OPERATIONS_YEAR)

        summary["exercises"] = {
            "main_ops": ex_main_26.year,
            "main_close": ex_main_25.year,
            "isol_ops": ex_isol_26.year,
        }

        for company in (co_main, co_isol):
            acc411 = Account.objects.filter(company=company, code="411").first()
            acc401 = Account.objects.filter(company=company, code="401").first()
            if acc411 and not ThirdParty.objects.filter(company=company, reference="CLI-FICT-01").exists():
                ThirdParty.objects.create(
                    organization=org,
                    company=company,
                    kind=PartyKind.CUSTOMER,
                    name=THIRD_PARTIES[0][2],
                    reference="CLI-FICT-01",
                    tax_id="CGFICTCLI01",
                    account=acc411,
                )
                summary["created"].append(f"party_cli_{company.acronym}")
            if acc401 and not ThirdParty.objects.filter(company=company, reference="FOU-FICT-01").exists():
                ThirdParty.objects.create(
                    organization=org,
                    company=company,
                    kind=PartyKind.SUPPLIER,
                    name=THIRD_PARTIES[1][2],
                    reference="FOU-FICT-01",
                    tax_id="CGFICTFOU01",
                    account=acc401,
                )
                summary["created"].append(f"party_fou_{company.acronym}")

        journal_main = Journal.objects.filter(company=co_main, code="OD").first()
        if journal_main and (
            force_entries or not Entry.objects.filter(company=co_main, exercise=ex_main_26).exists()
        ):
            acc_d = Account.objects.get(company=co_main, code=SALE_DEBIT_ACCOUNT)
            acc_c = Account.objects.get(company=co_main, code=SALE_CREDIT_ACCOUNT)
            draft = create_draft(
                company=co_main,
                journal=journal_main,
                accounting_date=date(OPERATIONS_YEAR, 3, 15),
                value_date=date(OPERATIONS_YEAR, 3, 15),
                description="Vente fictive marchandises BETA-TEST-01",
                document_ref="BT01-SALE-001",
                raw_lines=[
                    {"account_id": str(acc_d.id), "debit": SALE_AMOUNT, "credit": "0"},
                    {"account_id": str(acc_c.id), "debit": "0", "credit": SALE_AMOUNT},
                ],
            )
            post_entry(draft, owner)
            summary["created"].append("entry_main_sale_posted")

        journal_isol = Journal.objects.filter(company=co_isol, code="OD").first()
        if journal_isol and (
            force_entries or not Entry.objects.filter(company=co_isol, exercise=ex_isol_26).exists()
        ):
            acc411 = Account.objects.get(company=co_isol, code="411")
            acc701 = Account.objects.get(company=co_isol, code="701")
            draft_i = create_draft(
                company=co_isol,
                journal=journal_isol,
                accounting_date=date(OPERATIONS_YEAR, 4, 1),
                value_date=date(OPERATIONS_YEAR, 4, 1),
                description="Vente isolation société B",
                document_ref="BT01-ISOL-001",
                raw_lines=[
                    {"account_id": str(acc411.id), "debit": "250000", "credit": "0"},
                    {"account_id": str(acc701.id), "debit": "0", "credit": "250000"},
                ],
            )
            post_entry(draft_i, owner)
            summary["created"].append("entry_isol_sale_posted")

        if ex_main_25.status == ExerciseStatus.OPEN and not Entry.objects.filter(
            company=co_main, exercise=ex_main_25
        ).exists():
            j25 = Journal.objects.filter(company=co_main, code="OD").first()
            codes = {
                "601": ("500000", "0"),
                "701": ("0", "800000"),
                "622": ("100000", "0"),
                "521": ("400000", "0"),
                "401": ("0", "200000"),
            }
            raw = []
            for code, (d, c) in codes.items():
                acc = Account.objects.get(company=co_main, code=code)
                raw.append(
                    {"account_id": str(acc.id), "debit": d, "credit": c, "label": "Seed close 2025"}
                )
            draft_close_seed = create_draft(
                company=co_main,
                journal=j25,
                accounting_date=date(CLOSE_YEAR, 12, 20),
                value_date=date(CLOSE_YEAR, 12, 20),
                description="Opérations fictives clôture 2025",
                document_ref="BT01-CLOSE-SEED",
                raw_lines=raw,
            )
            post_entry(draft_close_seed, owner)
            summary["created"].append("entry_close_year_seed")

        summary["company_ids"] = {
            "main": str(co_main.id),
            "isol": str(co_isol.id),
        }
        summary["users"] = [email for email, _, _ in USER_SPECS]
    return summary


def purge_beta_test01() -> int:
    assert_beta_database()
    with bypass_rls():
        deleted, _ = Organization.objects.filter(slug=ORG_SLUG).delete()
    return deleted
