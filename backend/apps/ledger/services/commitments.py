"""Sûretés et engagements hors bilan — note 1 (Titre IX ch. 6, VIII.30)."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from django.utils import timezone
from ninja.errors import HttpError

from apps.ledger.models import Commitment, CommitmentKind, CommitmentSide, EntryStatus, Journal
from apps.ledger.money import parse_amount
from apps.ledger.services.assets import resolve_account

KIND_LABELS = dict(CommitmentKind.choices)
SIDE_LABELS = dict(CommitmentSide.choices)

# Accordés = 906x / 916 ; obtenus = 902x / 912 (Titre VIII ch. 30).
GIVEN_ACCOUNTS = {
    CommitmentKind.MORTGAGE: "9063",
    CommitmentKind.PLEDGE: "9068",
    CommitmentKind.GAGE: "9068",
    CommitmentKind.GUARANTEE: "9062",
    CommitmentKind.DISCOUNT: "9064",
    CommitmentKind.ASSIGNED: "9068",
    CommitmentKind.LEASE: "9071",
    CommitmentKind.OTHER: "9068",
}
RECEIVED_ACCOUNTS = {
    CommitmentKind.MORTGAGE: "9023",
    CommitmentKind.PLEDGE: "9028",
    CommitmentKind.GAGE: "9028",
    CommitmentKind.GUARANTEE: "9022",
    CommitmentKind.DISCOUNT: "9024",
    CommitmentKind.ASSIGNED: "9028",
    CommitmentKind.LEASE: "9031",
    CommitmentKind.OTHER: "9028",
}


def class9_accounts(kind: str, side: str) -> tuple[str, str]:
    if side == CommitmentSide.RECEIVED:
        return RECEIVED_ACCOUNTS.get(kind, "9028"), "912"
    return GIVEN_ACCOUNTS.get(kind, "9068"), "916"


def serialize_commitment(item: Commitment) -> dict:
    debit_code, credit_code = class9_accounts(item.kind, item.side)
    entry = item.entry if item.entry_id else None
    return {
        "id": str(item.id),
        "kind": item.kind,
        "kind_label": KIND_LABELS.get(item.kind, item.kind),
        "side": item.side,
        "side_label": SIDE_LABELS.get(item.side, item.side),
        "label": item.label,
        "counterparty": item.counterparty,
        "amount": format(item.amount, "f"),
        "starts_on": item.starts_on.isoformat() if item.starts_on else "",
        "ends_on": item.ends_on.isoformat() if item.ends_on else "",
        "is_active": item.is_active,
        "entry_id": str(entry.id) if entry else None,
        "entry_number": entry.number_display if entry and entry.number_display else "",
        "origin_entry_id": str(item.origin_entry_id) if item.origin_entry_id else None,
        "class9_debit": debit_code,
        "class9_credit": credit_code,
    }


def _parse_optional_date(raw) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise HttpError(400, "Date invalide.") from exc


def create_commitment(company, payload: dict) -> Commitment:
    kind = payload.get("kind") or CommitmentKind.OTHER
    if kind not in CommitmentKind.values:
        raise HttpError(400, "Type d’engagement invalide.")
    side = payload.get("side") or CommitmentSide.GIVEN
    if side not in CommitmentSide.values:
        raise HttpError(400, "Sens invalide (given ou received).")
    label = (payload.get("label") or "").strip()
    if not label:
        raise HttpError(400, "Le libellé est requis.")
    currency = company.currency_code or "XOF"
    amount = parse_amount(payload.get("amount") or 0, currency)
    if amount <= 0:
        raise HttpError(400, "Le montant doit être positif.")
    return Commitment.objects.create(
        organization=company.organization,
        company=company,
        kind=kind,
        side=side,
        label=label,
        counterparty=(payload.get("counterparty") or "").strip(),
        amount=amount,
        starts_on=_parse_optional_date(payload.get("starts_on")),
        ends_on=_parse_optional_date(payload.get("ends_on")),
    )


def deactivate_commitment(company, commitment_id: str, user=None) -> None:
    item = (
        Commitment.objects.filter(company=company, id=commitment_id, is_active=True)
        .select_related("entry")
        .first()
    )
    if not item:
        raise HttpError(404, "Engagement introuvable.")
    if item.entry_id and user and item.entry and item.entry.status == EntryStatus.POSTED:
        if not item.entry.reversals.exists():
            from apps.ledger.services.posting import reverse_entry

            reverse_entry(item.entry, user, f"Retrait engagement {item.label}")
    item.is_active = False
    item.save(update_fields=["is_active"])


def post_commitment_class9(company, commitment_id: str, user) -> Commitment:
    from apps.ledger.services.posting import create_draft, post_entry

    item = (
        Commitment.objects.filter(company=company, id=commitment_id, is_active=True)
        .select_related("entry")
        .first()
    )
    if not item:
        raise HttpError(404, "Engagement introuvable.")
    if item.entry_id and item.entry and item.entry.status == EntryStatus.POSTED:
        raise HttpError(409, "Cet engagement est déjà comptabilisé en classe 9.")
    debit_code, credit_code = class9_accounts(item.kind, item.side)
    debit = resolve_account(company, debit_code)
    credit = resolve_account(company, credit_code)
    if debit is None or credit is None:
        raise HttpError(400, f"Comptes {debit_code} / {credit_code} introuvables. Synchronisez le PCGO.")
    journal = Journal.objects.filter(company=company, code="OD").first()
    if journal is None:
        raise HttpError(400, "Journal OD introuvable.")
    today = timezone.localdate()
    key = hashlib.sha256(f"class9:{item.id}".encode()).hexdigest()
    amount = format(item.amount, "f")
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=item.starts_on or today,
        value_date=item.starts_on or today,
        description=f"Engagement hors bilan — {item.label}",
        document_ref=item.counterparty,
        raw_lines=[
            {"account_id": str(debit.id), "debit": amount, "credit": "0", "label": item.label},
            {"account_id": str(credit.id), "debit": "0", "credit": amount, "label": item.label},
        ],
        idempotency_key=key,
        source="class9",
    )
    entry = post_entry(entry, user)
    item.entry = entry
    item.save(update_fields=["entry"])
    return item


def note1_from_items(items: list[dict]) -> str:
    given: dict[str, Decimal] = {}
    received: dict[str, Decimal] = {}
    for item in items:
        kind = item.get("kind") or "other"
        amount = item.get("amount") or Decimal("0")
        if not amount:
            continue
        bucket = given if item.get("side") == "given" else received
        bucket[kind] = bucket.get(kind, Decimal("0")) + amount
    parts = []
    if given:
        bits = [f"{KIND_LABELS.get(kind, kind)} {total}" for kind, total in given.items()]
        parts.append("Donnés : " + " · ".join(bits))
    if received:
        bits = [f"{KIND_LABELS.get(kind, kind)} {total}" for kind, total in received.items()]
        parts.append("Reçus : " + " · ".join(bits))
    return " · ".join(parts)


def note1_text(company) -> str:
    items = list(Commitment.objects.filter(company=company, is_active=True).values("kind", "side", "amount"))
    return note1_from_items(items)
