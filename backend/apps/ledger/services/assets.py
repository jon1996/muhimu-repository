"""Journal des immobilisations — plans, DAP, flux d’investissement."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    AssetKind,
    AssetStatus,
    DepreciationCharge,
    EntryStatus,
    FixedAsset,
    Journal,
    JournalType,
)
from apps.ledger.money import parse_amount
from apps.ledger.services.amortization import linear_charge
from apps.ledger.services.posting import create_draft, post_entry

ZERO = Decimal("0")


def next_reference(company) -> str:
    last = (
        FixedAsset.objects.filter(company=company, reference__startswith="IMM-")
        .order_by("-reference")
        .values_list("reference", flat=True)
        .first()
    )
    if last:
        try:
            number = int(last.split("-")[-1]) + 1
        except ValueError:
            number = FixedAsset.objects.filter(company=company).count() + 1
    else:
        number = 1
    return f"IMM-{number:04d}"


def suggest_contra_codes(asset_code: str) -> tuple[str, str]:
    """Propose 28xx / 681x à partir du compte d’immobilisation."""
    code = (asset_code or "").strip()
    expense = "6813"
    if code.startswith("21"):
        expense = "6812"
        amort = "281" + code[2:]
    elif code.startswith("22"):
        amort = "282" + code[2:]
    elif code.startswith("23"):
        amort = "283" + code[2:]
    elif code.startswith("24"):
        amort = "284" + code[2:]
    elif code.startswith("25"):
        amort = "295" + code[2:]
        expense = "6914"
    elif code.startswith("26"):
        amort = "296" + code[2:]
        expense = "6972"
    elif code.startswith("27"):
        amort = "297" + code[2:]
        expense = "6972"
    else:
        amort = "28" + code[1:]
    return amort, expense


def resolve_account(company, code: str) -> Account | None:
    code = (code or "").strip()
    while code:
        account = Account.objects.filter(
            company=company, code=code, is_active=True, is_postable=True
        ).first()
        if account:
            return account
        code = code[:-1]
    return None


def accumulated(asset: FixedAsset, before: date | None = None) -> Decimal:
    qs = DepreciationCharge.objects.filter(asset=asset)
    if before:
        qs = qs.filter(period__ends_on__lt=before)
    return qs.aggregate(total=Sum("amount"))["total"] or ZERO


def net_book_value(asset: FixedAsset, at: date | None = None) -> Decimal:
    return asset.cost - accumulated(asset, before=at)


def validate_asset_payload(company, payload: dict) -> dict:
    currency = company.currency_code or "XOF"
    cost = parse_amount(payload.get("cost") or "0", currency)
    residual = parse_amount(payload.get("residual_value") or "0", currency)
    if cost <= 0:
        raise HttpError(400, "Le coût d’entrée doit être positif.")
    if residual < 0 or residual >= cost:
        raise HttpError(400, "La valeur résiduelle doit être nulle ou inférieure au coût.")
    life = int(payload.get("useful_life_months") or 0)
    kind = payload.get("kind") or AssetKind.STANDALONE
    if kind == AssetKind.COMPONENT and 0 < life < 12:
        raise HttpError(400, "Un composant dont le cycle est inférieur à 12 mois est une charge (VIII.4).")
    parent = None
    parent_id = payload.get("parent_id")
    if parent_id:
        parent = FixedAsset.objects.filter(id=parent_id, company=company).first()
        if not parent:
            raise HttpError(404, "Immobilisation parente introuvable.")
    if kind == AssetKind.COMPONENT and parent is None:
        raise HttpError(400, "Un composant doit être rattaché à une immobilisation (VIII.4).")
    asset_account = Account.objects.filter(
        id=payload.get("asset_account_id"), company=company, is_active=True, is_postable=True
    ).first()
    if not asset_account or not asset_account.code.startswith("2") or asset_account.code.startswith("28") or asset_account.code.startswith("29"):
        raise HttpError(400, "Le compte d’immobilisation doit être un compte de classe 2 (hors 28/29).")
    amort = None
    expense = None
    if life > 0:
        amort = Account.objects.filter(
            id=payload.get("amort_account_id"), company=company, is_active=True, is_postable=True
        ).first()
        expense = Account.objects.filter(
            id=payload.get("expense_account_id"), company=company, is_active=True, is_postable=True
        ).first()
        if not amort:
            suggested, _ = suggest_contra_codes(asset_account.code)
            amort = resolve_account(company, suggested)
        if not expense:
            _, suggested_exp = suggest_contra_codes(asset_account.code)
            expense = resolve_account(company, suggested_exp)
        if not amort or not expense:
            raise HttpError(400, "Comptes d’amortissement (28) et de dotation (681/691/697) requis.")
    in_service = payload["in_service_on"]
    acquired = payload["acquired_on"]
    if in_service < acquired:
        raise HttpError(400, "La mise en service ne peut pas précéder l’acquisition.")
    return {
        "cost": cost,
        "residual_value": residual,
        "useful_life_months": life,
        "kind": kind,
        "asset_account": asset_account,
        "amort_account": amort,
        "expense_account": expense,
        "parent": parent,
        "acquired_on": acquired,
        "in_service_on": in_service,
    }


def charge_for_period(asset: FixedAsset, period: AccountingPeriod) -> Decimal:
    if not asset.depreciable:
        return ZERO
    if asset.disposed_on and asset.disposed_on <= period.starts_on:
        return ZERO
    already_before = accumulated(asset, before=period.starts_on)
    return linear_charge(
        cost=asset.cost,
        residual=asset.residual_value,
        useful_life_months=asset.useful_life_months,
        in_service_on=asset.in_service_on,
        period_start=period.starts_on,
        period_end=period.ends_on,
        already_charged=already_before,
        currency=asset.company.currency_code or "XOF",
        disposed_on=asset.disposed_on,
    )


@transaction.atomic
def post_period_depreciation(company, period: AccountingPeriod, user) -> Entry | None:
    if period.company_id != company.id:
        raise HttpError(400, "Période d’une autre société.")
    assets = list(
        FixedAsset.objects.filter(company=company, status=AssetStatus.IN_SERVICE).select_related(
            "asset_account", "amort_account", "expense_account"
        )
    )
    already = set(
        DepreciationCharge.objects.filter(company=company, period=period).values_list("asset_id", flat=True)
    )
    lines_by_pair: dict[tuple[str, str], Decimal] = {}
    charges: list[tuple[FixedAsset, Decimal]] = []
    for asset in assets:
        if asset.id in already or not asset.depreciable:
            continue
        amount = charge_for_period(asset, period)
        if amount <= 0:
            continue
        if not asset.expense_account_id or not asset.amort_account_id:
            raise HttpError(400, f"{asset.reference} : comptes de dotation manquants.")
        key = (str(asset.expense_account_id), str(asset.amort_account_id))
        lines_by_pair[key] = lines_by_pair.get(key, ZERO) + amount
        charges.append((asset, amount))
    if not charges:
        return None
    journal = Journal.objects.filter(company=company, type=JournalType.OD).first()
    if not journal:
        raise HttpError(400, "Journal OD introuvable.")
    raw_lines: list[dict] = []
    for (expense_id, amort_id), amount in lines_by_pair.items():
        raw_lines.append({"account_id": expense_id, "debit": str(amount), "credit": "0", "label": "Dotations aux amortissements"})
        raw_lines.append({"account_id": amort_id, "debit": "0", "credit": str(amount), "label": "Amortissements"})
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=period.ends_on,
        value_date=period.ends_on,
        description=f"Dotations aux amortissements {period.year}-{period.month:02d}",
        document_ref=f"DAP-{period.year}-{period.month:02d}",
        raw_lines=raw_lines,
        source="depreciation",
        idempotency_key=hashlib.sha256(
            f"dap:{company.id}:{period.id}:{len(charges)}:{sum((a for _, a in charges), ZERO)}".encode()
        ).hexdigest(),
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    DepreciationCharge.objects.bulk_create(
        [
            DepreciationCharge(
                organization=company.organization,
                company=company,
                asset=asset,
                period=period,
                entry=entry,
                amount=amount,
            )
            for asset, amount in charges
        ]
    )
    return entry


def tft_investment_from_register(company, period: AccountingPeriod) -> dict[str, Decimal] | None:
    assets = FixedAsset.objects.filter(company=company).select_related("asset_account")
    if not assets.exists():
        return None
    start = period.exercise.starts_on
    end = period.ends_on
    ff = ZERO
    fg = ZERO
    fh = ZERO
    for asset in assets:
        if not (start <= asset.acquired_on <= end):
            continue
        code = asset.asset_account.code
        if code.startswith("21"):
            ff -= asset.cost
        elif code.startswith(("22", "23", "24", "25")):
            fg -= asset.cost
        elif code.startswith(("26", "27")):
            fh -= asset.cost
    return {"ff": ff, "fg": fg, "fh": fh}


def note3_movements(company, exercise) -> str:
    assets = list(FixedAsset.objects.filter(company=company).select_related("asset_account"))
    if not assets:
        return ""
    start, end = exercise.starts_on, exercise.ends_on
    opening_gross = ZERO
    acquisitions = ZERO
    closing_gross = ZERO
    opening_amort = ZERO
    dap = ZERO
    for asset in assets:
        if asset.acquired_on < start:
            opening_gross += asset.cost
        if start <= asset.acquired_on <= end:
            acquisitions += asset.cost
        if asset.status != AssetStatus.DISPOSED or (asset.disposed_on and asset.disposed_on > end):
            closing_gross += asset.cost
        opening_amort += accumulated(asset, before=start)
        dap += (
            DepreciationCharge.objects.filter(
                asset=asset, period__starts_on__gte=start, period__ends_on__lte=end
            ).aggregate(total=Sum("amount"))["total"]
            or ZERO
        )
    closing_amort = opening_amort + dap
    net_open = opening_gross - opening_amort
    net_close = closing_gross - closing_amort
    return (
        f"3A brut : ouverture {opening_gross} · acquisitions {acquisitions} · clôture {closing_gross}. "
        f"3C amortissements : ouverture {opening_amort} · DAP {dap} · clôture {closing_amort}. "
        f"Net : ouverture {net_open} · clôture {net_close}."
    )


def serialize_asset(asset: FixedAsset, at: date | None = None) -> dict:
    accum = accumulated(asset, before=at)
    return {
        "id": str(asset.id),
        "reference": asset.reference,
        "label": asset.label,
        "kind": asset.kind,
        "parent_id": str(asset.parent_id) if asset.parent_id else None,
        "acquired_on": asset.acquired_on.isoformat(),
        "in_service_on": asset.in_service_on.isoformat(),
        "cost": format(asset.cost, "f"),
        "residual_value": format(asset.residual_value, "f"),
        "useful_life_months": asset.useful_life_months,
        "method": asset.method,
        "asset_account_id": str(asset.asset_account_id),
        "asset_account_code": asset.asset_account.code,
        "amort_account_id": str(asset.amort_account_id) if asset.amort_account_id else None,
        "amort_account_code": asset.amort_account.code if asset.amort_account else "",
        "expense_account_id": str(asset.expense_account_id) if asset.expense_account_id else None,
        "expense_account_code": asset.expense_account.code if asset.expense_account else "",
        "status": asset.status,
        "disposed_on": asset.disposed_on.isoformat() if asset.disposed_on else None,
        "notes": asset.notes,
        "accumulated": format(accum, "f"),
        "net": format(asset.cost - accum, "f"),
        "depreciable": asset.depreciable,
    }
