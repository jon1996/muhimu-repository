"""Parseur OFX / QFX — relevés bancaires (SGML 1.x et XML 2.x)."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ninja.errors import HttpError

DEBIT_TYPES = {
    "DEBIT",
    "CHECK",
    "ATM",
    "POS",
    "FEE",
    "SRVCHG",
    "PAYMENT",
    "DIRECTDEBIT",
    "CASH",
    "WITHDRAWAL",
}
CREDIT_TYPES = {
    "CREDIT",
    "DEP",
    "DEPOSIT",
    "DIRECTDEP",
    "DIRECTDEPOSIT",
    "INT",
    "DIV",
    "INTEREST",
}

TAG_RE = re.compile(r"<([A-Z][A-Z0-9.]*)>([^<]*)", re.IGNORECASE)
STMTTRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.IGNORECASE | re.DOTALL)
LEDGER_RE = re.compile(r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|<AVAILBAL>)", re.IGNORECASE | re.DOTALL)
DTEND_RE = re.compile(r"<DTEND>([^<\s]+)", re.IGNORECASE)
DTASOF_RE = re.compile(r"<DTASOF>([^<\s]+)", re.IGNORECASE)


def decode_ofx(content: bytes) -> str:
    if not content:
        raise HttpError(400, "Fichier OFX vide.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="replace")


def parse_ofx_date(raw: str) -> date | None:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if len(digits) < 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def parse_ofx_amount(raw: str) -> Decimal:
    text = (raw or "").strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return Decimal("0")
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise HttpError(400, f"Montant OFX invalide ({raw}).") from exc


def _tags(block: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, value in TAG_RE.findall(block):
        out[name.upper()] = value.strip()
    return out


def _side(amount: Decimal, trntype: str, signed_file: bool) -> tuple[Decimal, Decimal]:
    kind = (trntype or "").upper()
    if amount < 0:
        return abs(amount), Decimal("0")
    if amount == 0:
        return Decimal("0"), Decimal("0")
    if not signed_file and kind in DEBIT_TYPES and kind not in CREDIT_TYPES:
        return amount, Decimal("0")
    return Decimal("0"), amount


def parse_ofx(content: bytes) -> dict:
    text = decode_ofx(content)
    if "<STMTTRN" not in text.upper() and "<stmttrn" not in text.lower():
        raise HttpError(400, "Fichier OFX sans opérations (STMTTRN).")
    blocks = STMTTRN_RE.findall(text)
    if not blocks:
        parts = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)
        blocks = parts[1:] if len(parts) > 1 else []
    parsed_txns = [_tags(block) for block in blocks]
    signed_file = any(parse_ofx_amount(item.get("TRNAMT") or "0") < 0 for item in parsed_txns)

    lines = []
    for item in parsed_txns:
        amount = parse_ofx_amount(item.get("TRNAMT") or "0")
        debit, credit = _side(amount, item.get("TRNTYPE") or "", signed_file)
        if debit == 0 and credit == 0:
            continue
        line_date = parse_ofx_date(item.get("DTPOSTED") or item.get("DTUSER") or "")
        if line_date is None:
            continue
        name = (item.get("NAME") or "").strip()
        memo = (item.get("MEMO") or "").strip()
        label = " — ".join(part for part in (name, memo) if part) or "Mouvement OFX"
        fitid = (item.get("FITID") or "").strip()[:64]
        if not fitid:
            fitid = hashlib.sha1(
                f"{line_date.isoformat()}|{label}|{debit}|{credit}".encode()
            ).hexdigest()[:16]
        lines.append(
            {
                "line_date": line_date,
                "label": label[:255],
                "bank_debit": debit,
                "bank_credit": credit,
                "external_id": fitid,
            }
        )

    ledger = LEDGER_RE.search(text)
    ledger_tags = _tags(ledger.group(1)) if ledger else {}
    balance_raw = ledger_tags.get("BALAMT")
    as_of = parse_ofx_date(ledger_tags.get("DTASOF") or "")
    if as_of is None:
        match = DTASOF_RE.search(text) or DTEND_RE.search(text)
        as_of = parse_ofx_date(match.group(1)) if match else None
    if as_of is None and lines:
        as_of = max(line["line_date"] for line in lines)
    return {
        "as_of": as_of,
        "balance": parse_ofx_amount(balance_raw) if balance_raw not in (None, "") else None,
        "lines": lines,
    }
