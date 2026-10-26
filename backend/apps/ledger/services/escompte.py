"""Escompte d’effets — 415, 564/565, 6745, engagement note 1."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    Commitment,
    CommitmentKind,
    CommitmentSide,
    EntryStatus,
    Journal,
    JournalType,
)
from apps.ledger.money import parse_amount
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.commitments import create_commitment

ZERO = Decimal("0")


def discount_net(nominal: Decimal, agios: Decimal) -> Decimal:
    if nominal <= 0:
        raise HttpError(400, "Le nominal de l’effet doit être positif.")
    if agios < 0:
        raise HttpError(400, "Les agios ne peuvent pas être négatifs.")
    if agios > nominal:
        raise HttpError(400, "Les agios ne peuvent pas dépasser le nominal.")
    return nominal - agios


def liability_code(campaign: bool) -> str:
    return "564" if campaign else "565"


def _pick(company, *codes: str) -> Account | None:
    for code in codes:
        account = resolve_account(company, code)
        if account:
            return account
    qs = Account.objects.filter(company=company, is_active=True, is_postable=True)
    for code in codes:
        account = qs.filter(code__startswith=code).order_by("code").first()
        if account:
            return account
    return None


def _must(company, *codes: str, label: str) -> Account:
    account = _pick(company, *codes)
    if account is None:
        raise HttpError(400, f"Compte {label} ({'/'.join(codes)}) introuvable. Synchronisez le PCGO.")
    return account


def preview_discount(company, payload: dict) -> dict:
    currency = company.currency_code or "XOF"
    nominal = parse_amount(payload.get("nominal") or "0", currency)
    agios = parse_amount(payload.get("agios") or "0", currency)
    net = discount_net(nominal, agios)
    due_raw = (payload.get("due_on") or "").strip()
    due_on = ""
    if due_raw:
        try:
            due_on = date.fromisoformat(due_raw[:10]).isoformat()
        except ValueError as exc:
            raise HttpError(400, "Échéance de l’effet invalide.") from exc
    campaign = bool(payload.get("campaign"))
    party_id = payload.get("third_party_id") or None
    label = (payload.get("label") or "Escompte d’effet").strip() or "Escompte d’effet"

    billed = None
    if payload.get("source_account_id"):
        billed = Account.objects.filter(
            company=company, id=payload["source_account_id"], is_active=True, is_postable=True
        ).first()
        if billed is None:
            raise HttpError(400, "Compte d’origine (411/412) introuvable.")
    else:
        billed = _must(company, "412", "411", label="effets à recevoir")

    held = _must(company, "415", label="415 effets escomptés")
    bank = None
    if payload.get("bank_account_id"):
        bank = Account.objects.filter(
            company=company, id=payload["bank_account_id"], is_active=True, is_postable=True
        ).first()
        if bank is None:
            raise HttpError(400, "Compte banque introuvable.")
    else:
        bank = _must(company, "52", "53", label="banque")
    charge = _must(company, "6745", "67", label="6745 agios")
    liability = _must(company, liability_code(campaign), "56", label="crédit d’escompte")

    def line(account: Account, debit="0", credit="0", due="") -> dict:
        return {
            "account_id": str(account.id),
            "account_code": account.code,
            "account_label": account.label,
            "debit": debit,
            "credit": credit,
            "label": label,
            "third_party_id": party_id,
            "due_on": due,
        }

    nom = format(nominal, "f")
    agi = format(agios, "f")
    rec = format(net, "f")
    lines = [
        line(held, debit=nom, due=due_on),
        line(billed, credit=nom),
        line(bank, debit=rec),
        line(liability, credit=nom),
    ]
    if agios:
        lines.insert(3, line(charge, debit=agi))

    journal = Journal.objects.filter(company=company, type=JournalType.BANK).first()
    if journal is None:
        journal = Journal.objects.filter(company=company, code="BQ").first()
    return {
        "journal_id": str(journal.id) if journal else "",
        "journal_code": journal.code if journal else "BQ",
        "description": label,
        "nominal": nom,
        "agios": agi,
        "net": rec,
        "liability_code": liability.code,
        "lines": lines,
    }


def discount_nominal_from_entry(entry) -> tuple[Decimal, date | None, str]:
    nominal = ZERO
    due_on = None
    counterparty = ""
    for line in entry.lines.select_related("account", "third_party"):
        code = (line.account.code or "").strip()
        if code.startswith("564") or code.startswith("565"):
            nominal += (line.credit or ZERO) - (line.debit or ZERO)
        if code.startswith("415") and not due_on and line.due_on:
            due_on = line.due_on
        if line.third_party_id and not counterparty:
            counterparty = line.third_party.name
    if nominal <= 0:
        for line in entry.lines.select_related("account"):
            code = (line.account.code or "").strip()
            if code.startswith("415"):
                nominal += (line.debit or ZERO) - (line.credit or ZERO)
    return nominal, due_on, counterparty


def sync_discount_commitment(entry) -> Commitment | None:
    if entry.status != EntryStatus.POSTED:
        return None
    existing = Commitment.objects.filter(origin_entry=entry).first()
    if existing:
        return existing
    nominal, due_on, counterparty = discount_nominal_from_entry(entry)
    if nominal <= 0:
        return None
    item = create_commitment(
        entry.company,
        {
            "kind": CommitmentKind.DISCOUNT,
            "side": CommitmentSide.GIVEN,
            "label": entry.description or f"Effets escomptés {entry.number_display}",
            "counterparty": counterparty,
            "amount": format(nominal, "f"),
            "starts_on": entry.accounting_date.isoformat(),
            "ends_on": due_on.isoformat() if due_on else "",
        },
    )
    item.origin_entry = entry
    item.save(update_fields=["origin_entry"])
    return item


def close_discount_for_entry(entry, user=None) -> int:
    from apps.ledger.services.commitments import deactivate_commitment

    count = 0
    for item in Commitment.objects.filter(origin_entry=entry, is_active=True):
        deactivate_commitment(entry.company, str(item.id), user)
        count += 1
    return count
