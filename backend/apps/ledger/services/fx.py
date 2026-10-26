"""Devises SYSCOHADA — conversion à l’imputation et écarts 478/479.

Cours : 1 unité de devise étrangère = `rate` unités de devise de tenue.
Les éléments monétaires (classes 4 et 5 hors 478/479) sont réévalués à la
date d’arrêté : perte latente → 478 (BU), gain latent → 479 (DV).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import Entry, EntryLine, EntryStatus, FxRate, Journal, JournalType
from apps.ledger.money import parse_rate, quantize_amount
from apps.ledger.services.assets import resolve_account
from apps.tenancy.models import Company

ZERO = Decimal("0")
ONE = Decimal("1")
SOURCE = "fx_reval"
MONETARY_CLASSES = frozenset("45")


def functional_currency(company: Company) -> str:
    return (company.currency_code or "XOF").upper()


def normalize_currency(code: str) -> str:
    value = (code or "").strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise HttpError(400, "Code devise ISO invalide (3 lettres).")
    return value


def rate_value(raw: str | Decimal | int | float | None) -> Decimal:
    try:
        return parse_rate(raw)
    except (ValueError, ArithmeticError) as exc:
        raise HttpError(400, "Cours invalide.") from exc


def get_rate(
    company: Company,
    currency_code: str,
    on: date,
    explicit: str | Decimal | int | float | None = None,
) -> Decimal:
    functional = functional_currency(company)
    currency_code = normalize_currency(currency_code)
    if currency_code == functional:
        return ONE
    if explicit not in (None, "", 0, "0"):
        return rate_value(explicit)
    row = (
        FxRate.objects.filter(company=company, currency_code=currency_code, rate_date__lte=on)
        .order_by("-rate_date")
        .first()
    )
    if not row:
        raise HttpError(
            400,
            f"Aucun cours {currency_code}/{functional} au {on.isoformat()}.",
        )
    return row.rate


def convert_amount(amount: Decimal, rate: Decimal, functional: str) -> Decimal:
    return quantize_amount(amount * rate, functional)


def upsert_rate(company: Company, currency_code: str, rate_date: date, rate) -> FxRate:
    currency_code = normalize_currency(currency_code)
    if currency_code == functional_currency(company):
        raise HttpError(400, "Pas de cours sur la devise de tenue.")
    value = rate_value(rate)
    obj, _created = FxRate.objects.update_or_create(
        company=company,
        currency_code=currency_code,
        rate_date=rate_date,
        defaults={"organization": company.organization, "rate": value},
    )
    return obj


def serialize_rate(row: FxRate) -> dict:
    return {
        "id": str(row.id),
        "currency_code": row.currency_code,
        "rate_date": row.rate_date.isoformat(),
        "rate": format(row.rate, "f"),
    }


def _is_monetary(code: str) -> bool:
    if not code or code[:1] not in MONETARY_CLASSES:
        return False
    return not (code.startswith("478") or code.startswith("479"))


def _signed_foreign(line: EntryLine) -> Decimal:
    if line.foreign_amount == 0:
        return ZERO
    if line.debit != 0:
        return line.foreign_amount
    return -line.foreign_amount


def compute_revalue(company: Company, as_of: date) -> dict:
    functional = functional_currency(company)
    positions: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "account": None,
            "currency": "",
            "foreign_net": ZERO,
            "book_net": ZERO,
        }
    )
    qs = (
        EntryLine.objects.filter(
            company=company,
            entry__status=EntryStatus.POSTED,
            entry__accounting_date__lte=as_of,
        )
        .exclude(entry__source__in={"cage", "cage_alloc", "cage_close", "class9"})
        .select_related("account", "entry")
    )
    for line in qs:
        code = line.account.code
        if not _is_monetary(code):
            continue
        ccy = (line.currency_code or "").upper()
        if not ccy or ccy == functional:
            continue
        key = (str(line.account_id), ccy)
        pos = positions[key]
        pos["account"] = line.account
        pos["currency"] = ccy
        pos["book_net"] += line.debit - line.credit
        pos["foreign_net"] += _signed_foreign(line)

    errors: list[str] = []
    warnings: list[str] = []
    lines: list[dict] = []
    gain = ZERO
    loss = ZERO
    acc478 = resolve_account(company, "478")
    acc479 = resolve_account(company, "479")
    if not acc478 or not acc479:
        errors.append("Comptes 478 / 479 introuvables. Synchronisez le PCGO.")

    for pos in positions.values():
        account = pos["account"]
        if account is None:
            continue
        if pos["foreign_net"] == 0 and pos["book_net"] == 0:
            continue
        try:
            rate = get_rate(company, pos["currency"], as_of)
        except HttpError as exc:
            errors.append(getattr(exc, "message", str(exc)))
            continue
        target = convert_amount(pos["foreign_net"], rate, functional)
        difference = quantize_amount(target - pos["book_net"], functional)
        if difference == 0:
            continue
        if difference > 0:
            kind = "gain"
            debit_account = account
            credit_account = acc479
            gain += difference
        else:
            kind = "loss"
            debit_account = acc478
            credit_account = account
            loss += abs(difference)
        lines.append(
            {
                "account_id": str(account.id),
                "account_code": account.code,
                "account_label": account.label,
                "currency_code": pos["currency"],
                "foreign_net": format(pos["foreign_net"], "f"),
                "book_net": format(pos["book_net"], "f"),
                "closing_rate": format(rate, "f"),
                "target": format(target, "f"),
                "difference": format(difference, "f"),
                "kind": kind,
                "debit_account_id": str(debit_account.id) if debit_account else "",
                "debit_account_code": debit_account.code if debit_account else "",
                "credit_account_id": str(credit_account.id) if credit_account else "",
                "credit_account_code": credit_account.code if credit_account else "",
            }
        )

    existing = Entry.objects.filter(
        company=company, source=SOURCE, accounting_date=as_of, status=EntryStatus.POSTED
    ).first()
    if existing:
        warnings.append(
            f"Une réévaluation est déjà validée ({existing.number_display}). Contrepasser pour reprendre."
        )

    unique_errors = list(dict.fromkeys(errors))
    return {
        "as_of": as_of.isoformat(),
        "functional": functional,
        "ok": not unique_errors,
        "posted": bool(existing),
        "entry_id": str(existing.id) if existing else None,
        "entry_number": existing.number_display if existing else "",
        "lines": lines,
        "gain": format(gain, "f"),
        "loss": format(loss, "f"),
        "warnings": warnings,
        "errors": unique_errors,
    }


@transaction.atomic
def post_revalue(company: Company, as_of: date, user) -> dict:
    payload = compute_revalue(company, as_of)
    if not payload["ok"]:
        raise HttpError(400, payload["errors"][0] if payload["errors"] else "Réévaluation impossible.")
    if payload["posted"]:
        raise HttpError(
            409,
            payload["warnings"][0] if payload["warnings"] else "Réévaluation déjà validée à cette date.",
        )
    if not payload["lines"]:
        raise HttpError(400, "Aucun écart de conversion à constater.")

    journal = Journal.objects.filter(company=company, type=JournalType.OD).first()
    if not journal:
        raise HttpError(400, "Journal OD introuvable.")

    functional = functional_currency(company)

    def _line_ccy(account_code: str, item_ccy: str) -> str:
        if _is_monetary(account_code):
            return item_ccy
        return functional

    raw_lines: list[dict] = []
    for item in payload["lines"]:
        amount = abs(Decimal(item["difference"]))
        label = (
            f"Écart {item['currency_code']} {item['account_code']} "
            f"({'gain' if item['kind'] == 'gain' else 'perte'})"
        )
        raw_lines.append(
            {
                "account_id": item["debit_account_id"],
                "debit": str(amount),
                "credit": "0",
                "label": label,
                "currency_code": _line_ccy(item["debit_account_code"], item["currency_code"]),
                "amounts_functional": True,
            }
        )
        raw_lines.append(
            {
                "account_id": item["credit_account_id"],
                "debit": "0",
                "credit": str(amount),
                "label": label,
                "currency_code": _line_ccy(item["credit_account_code"], item["currency_code"]),
                "amounts_functional": True,
            }
        )

    from apps.ledger.services.posting import create_draft, post_entry

    key = hashlib.sha256(f"fx_reval:{company.id}:{as_of.isoformat()}".encode()).hexdigest()
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=as_of,
        value_date=as_of,
        description=f"Réévaluation des devises au {as_of.isoformat()}",
        document_ref=f"FX-{as_of.isoformat()}",
        raw_lines=raw_lines,
        source=SOURCE,
        idempotency_key=key,
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    payload["posted"] = True
    payload["entry_id"] = str(entry.id)
    payload["entry_number"] = entry.number_display
    payload["warnings"] = []
    return payload
