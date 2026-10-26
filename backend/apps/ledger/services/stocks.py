"""Stocks SYSCOHADA — inventaire intermittent, variation 3/603–73, notes 6 et 7 (VIII.14)."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    EntryStatus,
    InventoryCampaign,
    InventoryStatus,
    Journal,
    JournalType,
    StockMethod,
)
from apps.ledger.money import parse_amount, quantize_amount
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.balance import trial_balance
from apps.ledger.services.posting import create_draft, post_entry

ZERO = Decimal("0")
STOCK_CODE_RE = re.compile(r"(?<!\d)(3[0-8]\d{0,2})(?!\d)")

METHOD_LABELS = {
    StockMethod.CUMP: "CUMP",
    StockMethod.PEPS: "PEPS",
}

FAMILY_LABELS = {
    "31": "Marchandises",
    "32": "Matières premières",
    "33": "Autres approvisionnements",
    "34": "En-cours de production",
    "35": "En-cours de services",
    "36": "Produits finis",
    "37": "Produits intermédiaires",
    "38": "Stocks en cours de route",
}


def is_stock_account(code: str) -> bool:
    code = (code or "").strip()
    return bool(code) and code.startswith("3") and not code.startswith("39")


def variation_code(stock_code: str) -> str:
    code = (stock_code or "").strip()
    if code.startswith("31"):
        return "6031"
    if code.startswith("32"):
        return "6032"
    if code.startswith("33") or code.startswith("38"):
        return "6033"
    if code.startswith("34") or code.startswith("35"):
        return "734"
    if code.startswith("36"):
        return "736"
    if code.startswith("37"):
        return "737"
    raise HttpError(400, f"Le compte {stock_code} n’est pas un compte de stocks (classe 3 hors 39).")


def family_key(code: str) -> str:
    code = (code or "").strip()
    return code[:2] if len(code) >= 2 else code


def family_label(code: str) -> str:
    return FAMILY_LABELS.get(family_key(code), f"Stocks {family_key(code)}")


def account_net(rows: list[dict], account_id: str) -> Decimal:
    for row in rows:
        if str(row.get("account_id")) == str(account_id):
            return (row.get("close_debit") or ZERO) - (row.get("close_credit") or ZERO)
    return ZERO


def infer_stock_code(text: str) -> str | None:
    """Ex. « compte 31 », « 311 marchandises » → code de stock."""
    for match in STOCK_CODE_RE.finditer(text or ""):
        code = match.group(1)
        if is_stock_account(code):
            return code
    return None


def line_stock_code(line) -> str:
    account = getattr(line, "account", None)
    if account and is_stock_account(account.code):
        return account.code
    return infer_stock_code(getattr(line, "description", "") or "") or ""


def campaign_has_stock(campaign: InventoryCampaign) -> bool:
    for line in campaign.lines.all():
        if (line.amount or ZERO) != 0 and line_stock_code(line):
            return True
        if (line.amount or ZERO) != 0:
            return True
    return False


def attach_inferred_accounts(campaign: InventoryCampaign) -> None:
    company = campaign.company
    for line in campaign.lines.select_related("account").all():
        if line.account_id:
            continue
        code = infer_stock_code(line.description)
        if not code:
            continue
        account = resolve_account(company, code) or Account.objects.filter(
            company=company, code=code, is_active=True
        ).first()
        if account and is_stock_account(account.code):
            line.account = account
            line.save(update_fields=["account"])


def stock_campaign_for(company, exercise) -> InventoryCampaign | None:
    campaigns = (
        InventoryCampaign.objects.filter(company=company, exercise=exercise)
        .prefetch_related("lines__account")
        .order_by("-inventoried_on", "-created_at")
    )
    draft = None
    for campaign in campaigns:
        if not campaign_has_stock(campaign):
            continue
        if campaign.status == InventoryStatus.CLOSED:
            return campaign
        if draft is None:
            draft = campaign
    return draft


def counted_by_account(campaign: InventoryCampaign, currency: str) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for line in campaign.lines.select_related("account").all():
        if not line.account_id:
            continue
        code = line.account.code
        if not is_stock_account(code):
            continue
        amount = quantize_amount(line.amount, currency)
        bucket = grouped.setdefault(
            str(line.account_id),
            {"account": line.account, "amount": ZERO, "quantity": ZERO},
        )
        bucket["amount"] += amount
        bucket["quantity"] += line.quantity or ZERO
    return grouped


def period_for_inventory(campaign: InventoryCampaign) -> AccountingPeriod | None:
    return (
        AccountingPeriod.objects.filter(
            company=campaign.company,
            starts_on__lte=campaign.inventoried_on,
            ends_on__gte=campaign.inventoried_on,
        ).first()
        or AccountingPeriod.objects.filter(exercise=campaign.exercise).order_by("-starts_on").first()
    )


def stock_deltas(campaign: InventoryCampaign, rows: list[dict] | None = None) -> list[dict]:
    currency = campaign.company.currency_code or "XOF"
    period = period_for_inventory(campaign)
    if rows is None:
        rows = trial_balance(campaign.company, period) if period else []
    deltas = []
    for account_id, bucket in counted_by_account(campaign, currency).items():
        counted = quantize_amount(bucket["amount"], currency)
        book = quantize_amount(account_net(rows, account_id), currency)
        delta = counted - book
        if delta == 0:
            continue
        deltas.append(
            {
                "account": bucket["account"],
                "counted": counted,
                "book": book,
                "delta": delta,
                "quantity": bucket["quantity"],
                "variation_code": variation_code(bucket["account"].code),
            }
        )
    return deltas


def note6_text(company, exercise) -> str:
    campaign = stock_campaign_for(company, exercise)
    if not campaign:
        return ""
    currency = company.currency_code or "XOF"
    families: dict[str, dict] = defaultdict(lambda: {"amount": ZERO, "quantity": ZERO, "codes": set()})
    unlabeled = ZERO
    total = ZERO
    for line in campaign.lines.select_related("account").all():
        amount = quantize_amount(line.amount, currency)
        if amount == 0:
            continue
        code = line_stock_code(line)
        if not code:
            unlabeled += amount
            total += amount
            continue
        key = family_key(code)
        families[key]["amount"] += amount
        families[key]["quantity"] += line.quantity or ZERO
        families[key]["codes"].add(code)
        total += amount
    if not families and unlabeled == 0:
        return ""
    method = METHOD_LABELS.get(campaign.method, campaign.method)
    parts = [f"méthode {method} (inventaire intermittent)"]
    for key in sorted(families):
        item = families[key]
        codes = ", ".join(sorted(item["codes"]))
        parts.append(f"{family_label(key)} ({codes}) : {item['amount']} (qté {item['quantity']})")
    if unlabeled:
        parts.append(f"autres postes : {unlabeled}")
    parts.append(f"total {total}")
    if campaign.status != InventoryStatus.CLOSED:
        parts.append("inventaire encore en cours — arrêtez-le pour passer l’OD")
    return " · ".join(parts)


def note7_text(rows: list[dict]) -> str:
    clients = ZERO
    doubtful = ZERO
    accrued = ZERO
    for row in rows:
        code = row.get("code") or ""
        net = (row.get("close_debit") or ZERO) - (row.get("close_credit") or ZERO)
        if code.startswith("419") or code.startswith("491"):
            continue
        if code.startswith("416"):
            doubtful += net
        if code.startswith("418"):
            accrued += net
        if code.startswith("41"):
            clients += net
    if clients == 0 and accrued == 0:
        return ""
    parts = [f"Clients 41 : {clients}"]
    if doubtful:
        parts.append(f"dont douteux 416 : {doubtful}")
    if accrued:
        parts.append(f"produits à recevoir 418 : {accrued}")
    return " · ".join(parts)


@transaction.atomic
def post_stock_variation(campaign: InventoryCampaign, user):
    attach_inferred_accounts(campaign)
    campaign.refresh_from_db()
    if campaign.variation_entry_id:
        return campaign.variation_entry
    deltas = stock_deltas(campaign)
    if not deltas:
        return None
    company = campaign.company
    journal = Journal.objects.filter(company=company, type=JournalType.OD).first()
    if not journal:
        raise HttpError(400, "Journal OD introuvable.")
    raw_lines: list[dict] = []
    for item in deltas:
        stock = item["account"]
        contra = resolve_account(company, item["variation_code"])
        if not contra:
            raise HttpError(400, f"Compte de variation {item['variation_code']} introuvable pour {stock.code}.")
        amount = abs(item["delta"])
        label = f"Variation de stock {stock.code}"
        if item["delta"] > 0:
            raw_lines.append({"account_id": str(stock.id), "debit": str(amount), "credit": "0", "label": label})
            raw_lines.append({"account_id": str(contra.id), "debit": "0", "credit": str(amount), "label": label})
        else:
            raw_lines.append({"account_id": str(contra.id), "debit": str(amount), "credit": "0", "label": label})
            raw_lines.append({"account_id": str(stock.id), "debit": "0", "credit": str(amount), "label": label})
    key = hashlib.sha256(f"stock-var:{campaign.id}".encode()).hexdigest()
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=campaign.inventoried_on,
        value_date=campaign.inventoried_on,
        description=f"Variation de stocks au {campaign.inventoried_on.isoformat()} ({METHOD_LABELS.get(campaign.method, campaign.method)})",
        document_ref=f"INV-{campaign.inventoried_on.isoformat()}",
        raw_lines=raw_lines,
        idempotency_key=key,
        source="stock_variation",
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    campaign.variation_entry = entry
    campaign.save(update_fields=["variation_entry"])
    return entry


@transaction.atomic
def close_inventory(campaign: InventoryCampaign, user) -> InventoryCampaign:
    if campaign.status == InventoryStatus.CLOSED and campaign.variation_entry_id:
        return campaign
    post_stock_variation(campaign, user)
    campaign.status = InventoryStatus.CLOSED
    campaign.save(update_fields=["status"])
    return campaign
