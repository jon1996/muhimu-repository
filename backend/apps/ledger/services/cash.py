"""Contrôle de caisse — compte 57, journal CA, note 11."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import Account, CashCount, EntryLine, EntryStatus, Journal, JournalType
from apps.ledger.money import parse_amount
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.bank_rec import book_balance, serialize_book_line

ZERO = Decimal("0")
CASH_PREFIXES = ("57",)
SHORTAGE_CODE = "6588"
OVERAGE_CODE = "7588"


def is_cash_account(account: Account | str) -> bool:
    code = (account.code if isinstance(account, Account) else account or "").strip()
    return code.startswith("57") and not code.startswith("59")


def variance_amount(physical: Decimal, book: Decimal) -> Decimal:
    return (physical or ZERO) - (book or ZERO)


def variance_kind(delta: Decimal) -> str:
    if delta > 0:
        return "overage"
    if delta < 0:
        return "shortage"
    return "balanced"


def contra_code(kind: str) -> str:
    return OVERAGE_CODE if kind == "overage" else SHORTAGE_CODE


def posting_lines(kind: str, cash_id: str, contra_id: str, amount: Decimal, label: str) -> list[dict]:
    amount = abs(amount)
    formatted = format(amount, "f")
    if kind == "overage":
        return [
            {"account_id": cash_id, "debit": formatted, "credit": "0", "label": label},
            {"account_id": contra_id, "debit": "0", "credit": formatted, "label": label},
        ]
    return [
        {"account_id": contra_id, "debit": formatted, "credit": "0", "label": label},
        {"account_id": cash_id, "debit": "0", "credit": formatted, "label": label},
    ]


def note11_cash_from_items(items: list[dict]) -> str:
    parts = []
    for item in items:
        code = item.get("account_code") or "57"
        counted_on = item.get("counted_on") or ""
        physical = item.get("physical_amount") or ZERO
        book = item.get("book_amount") or ZERO
        delta = variance_amount(physical, book)
        if delta > 0:
            kind = f"surplus {delta}"
        elif delta < 0:
            kind = f"manquant {abs(delta)}"
        else:
            kind = "conforme"
        parts.append(f"contrôle {code} au {counted_on} : espèces {physical} · livre {book} · {kind}")
    return " · ".join(parts)


def resolve_cash_account(company, account_id: str | None) -> Account:
    qs = Account.objects.filter(company=company, is_active=True, is_postable=True)
    if account_id:
        account = qs.filter(id=account_id).first()
        if account is None or not is_cash_account(account):
            raise HttpError(400, "Choisissez un compte de caisse 57.")
        return account
    account = qs.filter(code__startswith="57").order_by("code").first()
    if account is None or not is_cash_account(account):
        raise HttpError(400, "Aucun compte 57 imputable.")
    return account


def serialize_count(item: CashCount) -> dict:
    delta = variance_amount(item.physical_amount, item.book_amount)
    kind = variance_kind(delta)
    entry = item.entry if item.entry_id else None
    return {
        "id": str(item.id),
        "account_id": str(item.account_id),
        "account_code": item.account.code,
        "counted_on": item.counted_on.isoformat(),
        "physical_amount": format(item.physical_amount, "f"),
        "book_amount": format(item.book_amount, "f"),
        "variance": format(delta, "f"),
        "variance_kind": kind,
        "contra_code": contra_code(kind) if kind != "balanced" else "",
        "notes": item.notes,
        "entry_id": str(entry.id) if entry else None,
        "entry_number": entry.number_display if entry and entry.number_display else "",
    }


def cash_book_lines(company, account: Account) -> list[EntryLine]:
    return list(
        EntryLine.objects.filter(
            company=company,
            account=account,
            entry__status=EntryStatus.POSTED,
        )
        .select_related("account", "entry")
        .order_by("-entry__accounting_date", "-position")[:80]
    )


def latest_count(company, account: Account) -> CashCount | None:
    return (
        CashCount.objects.filter(company=company, account=account)
        .select_related("account", "entry")
        .order_by("-counted_on", "-created_at")
        .first()
    )


def cash_payload(company, account_id: str | None = None) -> dict:
    account = resolve_cash_account(company, account_id)
    book = book_balance(company, account)
    count = latest_count(company, account)
    counts = list(
        CashCount.objects.filter(company=company, account=account)
        .select_related("account", "entry")
        .order_by("-counted_on")[:12]
    )
    physical = count.physical_amount if count else ZERO
    delta = variance_amount(physical, book) if count else ZERO
    kind = variance_kind(delta) if count else "balanced"
    return {
        "account_id": str(account.id),
        "account_code": account.code,
        "account_label": account.label,
        "book_balance": format(book, "f"),
        "physical_amount": format(physical, "f") if count else "",
        "variance": format(delta, "f") if count else format(ZERO, "f"),
        "variance_kind": kind if count else "",
        "contra_code": contra_code(kind) if count and kind != "balanced" else "",
        "count": serialize_count(count) if count else None,
        "counts": [serialize_count(item) for item in counts],
        "book_lines": [serialize_book_line(line) for line in cash_book_lines(company, account)],
    }


def _parse_date(raw) -> date:
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError) as exc:
        raise HttpError(400, "Date de contrôle invalide.") from exc


@transaction.atomic
def upsert_count(company, payload: dict) -> CashCount:
    account = resolve_cash_account(company, payload.get("account_id"))
    counted_on = _parse_date(payload.get("counted_on"))
    currency = company.currency_code or "XOF"
    physical = parse_amount(payload.get("physical_amount") or "0", currency)
    if physical < 0:
        raise HttpError(400, "Les espèces en caisse ne peuvent pas être négatives.")
    existing = (
        CashCount.objects.filter(company=company, account=account, counted_on=counted_on)
        .select_related("account", "entry")
        .first()
    )
    if existing and existing.entry_id:
        raise HttpError(409, "Écart déjà comptabilisé — contrepasser l’écriture pour reprendre le contrôle.")
    book = book_balance(company, account)
    notes = (payload.get("notes") or "").strip()[:255]
    if existing:
        existing.physical_amount = physical
        existing.book_amount = book
        existing.notes = notes
        existing.save(update_fields=["physical_amount", "book_amount", "notes"])
        return CashCount.objects.select_related("account", "entry").get(pk=existing.pk)
    return CashCount.objects.create(
        organization=company.organization,
        company=company,
        account=account,
        counted_on=counted_on,
        physical_amount=physical,
        book_amount=book,
        notes=notes,
    )


@transaction.atomic
def post_variance(company, count_id: str, user) -> CashCount:
    item = (
        CashCount.objects.filter(company=company, id=count_id)
        .select_related("account", "entry")
        .first()
    )
    if item is None:
        raise HttpError(404, "Contrôle de caisse introuvable.")
    if item.entry_id:
        return item
    delta = variance_amount(item.physical_amount, item.book_amount)
    kind = variance_kind(delta)
    if kind == "balanced":
        raise HttpError(400, "Aucun écart à comptabiliser.")
    contra = resolve_account(company, contra_code(kind))
    if contra is None:
        raise HttpError(400, f"Compte {contra_code(kind)} introuvable. Synchronisez le PCGO.")
    journal = Journal.objects.filter(company=company, type=JournalType.CASH).first()
    if journal is None:
        journal = Journal.objects.filter(company=company, code="CA").first()
    if journal is None:
        raise HttpError(400, "Journal de caisse (CA) introuvable.")
    from apps.ledger.services.posting import create_draft, post_entry

    amount = abs(delta)
    label = (
        f"Surplus de caisse {item.account.code}"
        if kind == "overage"
        else f"Manquant de caisse {item.account.code}"
    )
    key = hashlib.sha256(f"cash-var:{item.id}".encode()).hexdigest()
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=item.counted_on,
        value_date=item.counted_on,
        description=f"Écart de caisse au {item.counted_on.isoformat()} ({item.account.code})",
        document_ref=f"CAISSE-{item.counted_on.isoformat()}",
        raw_lines=posting_lines(kind, str(item.account_id), str(contra.id), amount, label),
        idempotency_key=key,
        source="cash_count",
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    item.entry = entry
    item.save(update_fields=["entry"])
    return CashCount.objects.select_related("account", "entry").get(pk=item.pk)


def note11_cash_text(company) -> str:
    items = []
    seen: set[str] = set()
    qs = (
        CashCount.objects.filter(company=company)
        .select_related("account")
        .order_by("account__code", "-counted_on")
    )
    for item in qs:
        code = item.account.code
        if code in seen:
            continue
        seen.add(code)
        items.append(
            {
                "account_code": code,
                "counted_on": item.counted_on.isoformat(),
                "physical_amount": item.physical_amount,
                "book_amount": item.book_amount,
            }
        )
    return note11_cash_from_items(items)
