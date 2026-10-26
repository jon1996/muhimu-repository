"""Jeu de démonstration SYSCOHADA — à charger uniquement si l'utilisateur le demande."""

from __future__ import annotations

from calendar import monthrange
from datetime import date

from django.db import transaction
from django.utils import timezone
from ninja.errors import HttpError

from apps.ledger.models import (
    AssetKind,
    AssetMethod,
    AssetStatus,
    Entry,
    EntryStatus,
    Exercise,
    ExerciseStatus,
    FixedAsset,
    Journal,
    PartyKind,
    ThirdParty,
)
from apps.ledger.services.assets import next_reference, resolve_account, suggest_contra_codes
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.services.setup import ensure_company_ledger


SETUP_EMPTY = "empty"
SETUP_DEMO = "demo"

PME_PROFILE = {
    "customer": ("CLI-0001", "Client Koffi Distribution"),
    "supplier": ("FOU-0001", "SOCOCIM Fournisseur"),
    "capital": "5000000",
    "purchase": "1200000",
    "sale": "2400000",
    "pay_sup": "800000",
    "pay_cli": "1500000",
    "rent": "200000",
    "cash": "150000",
    "asset": "3500000",
    "asset_label": "Mobilier et matériel de bureau",
}

CABINET_PROFILES = [
    {
        "customer": ("CLI-A001", "Client N'Guessan Négoce"),
        "supplier": ("FOU-A001", "CFAO Industrie"),
        "capital": "8000000",
        "purchase": "1800000",
        "sale": "3600000",
        "pay_sup": "1200000",
        "pay_cli": "2200000",
        "rent": "350000",
        "cash": "220000",
        "asset": "4200000",
        "asset_label": "Matériel informatique Alpha",
    },
    {
        "customer": ("CLI-B001", "Client Dakar Trading"),
        "supplier": ("FOU-B001", "SOCOCIM Sénégal"),
        "capital": "3000000",
        "purchase": "700000",
        "sale": "1400000",
        "pay_sup": "400000",
        "pay_cli": "900000",
        "rent": "150000",
        "cash": "80000",
        "asset": "1800000",
        "asset_label": "Mobilier de bureau Beta",
    },
]


def profile_for(company, index: int = 0) -> dict:
    org_type = getattr(company.organization, "type", "")
    if org_type == "cabinet":
        return CABINET_PROFILES[index % len(CABINET_PROFILES)]
    return PME_PROFILE


def _date(year: int, month: int, day: int) -> date:
    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _account(company, code: str):
    account = resolve_account(company, code)
    if not account:
        raise HttpError(400, f"Compte {code} introuvable. Ouvrez d’abord le plan SYSCOHADA.")
    return account


def _journal(company, code: str) -> Journal:
    journal = Journal.objects.filter(company=company, code=code).first()
    if not journal:
        raise HttpError(400, f"Journal {code} introuvable.")
    return journal


def _party(company, *, kind: str, name: str, reference: str, account):
    party, _ = ThirdParty.objects.get_or_create(
        company=company,
        reference=reference,
        defaults={
            "organization": company.organization,
            "kind": kind,
            "name": name,
            "account": account,
        },
    )
    return party


def _post(company, user, *, journal_code: str, on: date, description: str, document_ref: str, lines: list[dict], key: str):
    entry = create_draft(
        company=company,
        journal=_journal(company, journal_code),
        accounting_date=on,
        value_date=on,
        description=description,
        document_ref=document_ref,
        raw_lines=lines,
        source="demo",
        idempotency_key=key[:64],
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    return entry


def _line(account, debit: str = "0", credit: str = "0", **extra) -> dict:
    return {
        "account_id": str(account.id),
        "debit": debit,
        "credit": credit,
        **extra,
    }


@transaction.atomic
def seed_demo_data(company, user=None, profile: dict | None = None) -> int:
    """Crée tiers + écritures validées. Idempotent. Refuse s'il existe déjà des pièces hors démo."""
    ensure_company_ledger(company)
    existing_demo = Entry.objects.filter(company=company, source="demo").count()
    if existing_demo:
        return existing_demo
    if Entry.objects.filter(company=company).exists():
        raise HttpError(400, "Des écritures existent déjà. Le jeu de démonstration n’est pas chargé.")

    profile = profile or profile_for(company)
    exercise = (
        Exercise.objects.filter(company=company)
        .exclude(status=ExerciseStatus.CLOSED)
        .order_by("-year")
        .first()
    )
    year = exercise.year if exercise else timezone.localdate().year
    prefix = f"d{str(company.id).replace('-', '')[:10]}"
    acc101 = _account(company, "101")
    acc401 = _account(company, "401")
    acc411 = _account(company, "411")
    acc521 = _account(company, "521")
    acc571 = _account(company, "571")
    acc601 = _account(company, "601")
    acc622 = _account(company, "622")
    acc701 = _account(company, "701")
    acc244 = _account(company, "2441")

    cust_ref, cust_name = profile["customer"]
    sup_ref, sup_name = profile["supplier"]
    customer = _party(
        company,
        kind=PartyKind.CUSTOMER,
        name=cust_name,
        reference=cust_ref,
        account=acc411,
    )
    supplier = _party(
        company,
        kind=PartyKind.SUPPLIER,
        name=sup_name,
        reference=sup_ref,
        account=acc401,
    )

    sale_on = _date(year, 2, 5)
    purchase_on = _date(year, 1, 20)
    asset_on = _date(year, 3, 12)

    _post(
        company,
        user,
        journal_code="OD",
        on=_date(year, 1, 15),
        description="Apport en capital social",
        document_ref="DEMO-CAP",
        key=f"{prefix}-cap",
        lines=[
            _line(acc521, debit=profile["capital"], label="Versement capital"),
            _line(acc101, credit=profile["capital"], label="Capital appelé, versé"),
        ],
    )
    _post(
        company,
        user,
        journal_code="AC",
        on=purchase_on,
        description=f"Achat de marchandises — {sup_name}",
        document_ref="FAC-F-001",
        key=f"{prefix}-ach",
        lines=[
            _line(acc601, debit=profile["purchase"], label="Achats marchandises"),
            _line(
                acc401,
                credit=profile["purchase"],
                label=f"Facture {sup_name}",
                third_party_id=str(supplier.id),
                due_on=str(_date(year, 2, 19)),
            ),
        ],
    )
    _post(
        company,
        user,
        journal_code="VT",
        on=sale_on,
        description=f"Vente de marchandises — {cust_name}",
        document_ref="FAC-C-001",
        key=f"{prefix}-vte",
        lines=[
            _line(
                acc411,
                debit=profile["sale"],
                label=f"Facture {cust_name}",
                third_party_id=str(customer.id),
                due_on=str(_date(year, 3, 7)),
            ),
            _line(acc701, credit=profile["sale"], label="Ventes marchandises"),
        ],
    )
    _post(
        company,
        user,
        journal_code="BQ",
        on=_date(year, 2, 10),
        description=f"Règlement fournisseur {sup_name}",
        document_ref="VIR-F-001",
        key=f"{prefix}-reg",
        lines=[
            _line(acc401, debit=profile["pay_sup"], label=f"Acompte {sup_name}", third_party_id=str(supplier.id)),
            _line(acc521, credit=profile["pay_sup"], label="Virement sortant"),
        ],
    )
    _post(
        company,
        user,
        journal_code="BQ",
        on=_date(year, 2, 18),
        description=f"Encaissement client {cust_name}",
        document_ref="VIR-C-001",
        key=f"{prefix}-enc",
        lines=[
            _line(acc521, debit=profile["pay_cli"], label="Virement reçu"),
            _line(acc411, credit=profile["pay_cli"], label=f"Règlement {cust_name}", third_party_id=str(customer.id)),
        ],
    )
    _post(
        company,
        user,
        journal_code="OD",
        on=_date(year, 3, 1),
        description="Loyer du siège — mars",
        document_ref="LOY-03",
        key=f"{prefix}-loy",
        lines=[
            _line(acc622, debit=profile["rent"], label="Loyer mars"),
            _line(acc521, credit=profile["rent"], label="Prélèvement loyer"),
        ],
    )
    _post(
        company,
        user,
        journal_code="CA",
        on=_date(year, 3, 3),
        description="Recette de caisse — ventes au comptant",
        document_ref="REC-001",
        key=f"{prefix}-cai",
        lines=[
            _line(acc571, debit=profile["cash"], label="Encaissement caisse"),
            _line(acc701, credit=profile["cash"], label="Ventes au comptant"),
        ],
    )
    _post(
        company,
        user,
        journal_code="AC",
        on=asset_on,
        description="Acquisition matériel de bureau",
        document_ref="FAC-IMM-001",
        key=f"{prefix}-imm",
        lines=[
            _line(acc244, debit=profile["asset"], label="Matériel de bureau"),
            _line(
                acc401,
                credit=profile["asset"],
                label="Facture matériel",
                third_party_id=str(supplier.id),
                due_on=str(_date(year, 4, 11)),
            ),
        ],
    )

    if not FixedAsset.objects.filter(company=company, reference="IMM-0001").exists():
        amort_code, expense_code = suggest_contra_codes(acc244.code)
        amort = resolve_account(company, amort_code)
        expense = resolve_account(company, expense_code)
        FixedAsset.objects.create(
            organization=company.organization,
            company=company,
            reference=next_reference(company) if FixedAsset.objects.filter(company=company).exists() else "IMM-0001",
            label=profile["asset_label"],
            kind=AssetKind.STANDALONE,
            acquired_on=asset_on,
            in_service_on=asset_on,
            cost=profile["asset"],
            residual_value="0",
            useful_life_months=60,
            method=AssetMethod.LINEAR,
            asset_account=acc244,
            amort_account=amort,
            expense_account=expense,
            status=AssetStatus.IN_SERVICE,
            notes="Jeu de démonstration",
        )

    return Entry.objects.filter(company=company, source="demo").count()


@transaction.atomic
def initialize_ledger(company, *, with_demo: bool, user=None) -> dict:
    """Ouvre le dossier d'une société et enregistre le choix vide / démo."""
    ensure_company_ledger(company)
    if company.setup_data in (SETUP_EMPTY, SETUP_DEMO):
        return {
            "setup_data": company.setup_data,
            "seeded": Entry.objects.filter(company=company, source="demo").count(),
            "already": True,
        }
    seeded = 0
    if with_demo:
        seeded = seed_demo_data(company, user, profile=profile_for(company))
        company.setup_data = SETUP_DEMO
    else:
        company.setup_data = SETUP_EMPTY
    company.save(update_fields=["setup_data", "updated_at"])
    return {"setup_data": company.setup_data, "seeded": seeded, "already": False}


@transaction.atomic
def initialize_organization(organization, *, with_demo: bool, user=None) -> dict:
    """Choix unique par organisation (PME ou cabinet), appliqué à toutes les sociétés."""
    from apps.tenancy.models import Company

    if organization.setup_data in (SETUP_EMPTY, SETUP_DEMO):
        return {
            "setup_data": organization.setup_data,
            "seeded": Entry.objects.filter(company__organization=organization, source="demo").count(),
            "companies": organization.companies.count(),
            "already": True,
        }
    companies = list(
        Company.objects.filter(organization=organization, is_active=True).order_by("name")
    )
    if not companies:
        raise HttpError(400, "Aucune société dans cette organisation.")
    seeded = 0
    choice = SETUP_DEMO if with_demo else SETUP_EMPTY
    for index, company in enumerate(companies):
        ensure_company_ledger(company)
        if with_demo and not Entry.objects.filter(company=company).exists():
            seeded += seed_demo_data(company, user, profile=profile_for(company, index))
        company.setup_data = choice
        company.save(update_fields=["setup_data", "updated_at"])
    organization.setup_data = choice
    organization.save(update_fields=["setup_data", "updated_at"])
    return {
        "setup_data": organization.setup_data,
        "seeded": seeded,
        "companies": len(companies),
        "already": False,
    }
