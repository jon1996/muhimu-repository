"""Soldes d’ouverture — à-nouveaux (journal AN) et colonne N-1.

L’écriture AN est datée du 1er jour de l’exercice (classes 1–5 + 13).
Les classes 6/7/8 du fichier servent au CR N-1 (snapshots de décembre N-1),
jamais dans l’à-nouveaux. On poste AN avant de semer N-1 pour ne pas
doubler l’ouverture de janvier.
"""

from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    BalanceSnapshot,
    Entry,
    EntryStatus,
    Exercise,
    ExerciseStatus,
    Journal,
    JournalType,
    PeriodStatus,
)
from apps.ledger.money import parse_amount
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.setup import ensure_company_ledger
from apps.ledger.services.sn_map import cr_amounts
from apps.ledger.taxonomy import normalize_code

ZERO = Decimal("0")
PNL_CLASSES = "678"
BS_CLASSES = "12345"
OPENING_TEMPLATE = (
    "code;debit;credit\n"
    "1013;0;10000000\n"
    "411;2500000;0\n"
    "521;800000;0\n"
    "401;0;1800000\n"
    "131;0;1500000\n"
    "701;0;8000000\n"
    "605;6500000;0\n"
)
MAX_CSV_BYTES = 1024 * 1024


def format_amount(amount: Decimal) -> str:
    return format(amount, "f")


def is_pnl(code: str) -> bool:
    return bool(code) and code[0] in PNL_CLASSES


def is_balance_sheet(code: str) -> bool:
    return bool(code) and code[0] in BS_CLASSES


def parse_opening_csv(content: bytes) -> list[dict]:
    if len(content) > MAX_CSV_BYTES:
        raise HttpError(400, "Fichier trop volumineux (1 Mo max).")
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HttpError(400, "Encodage du CSV illisible.")
    return parse_opening_text(text)


def parse_opening_text(text: str) -> list[dict]:
    sample = text[:2048]
    delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise HttpError(400, "CSV vide.")
    header = [normalize_code(cell).lower().replace("_", "") for cell in rows[0]]
    aliases = {
        "code": "code",
        "compte": "code",
        "numero": "code",
        "n°": "code",
        "debit": "debit",
        "débit": "debit",
        "credit": "credit",
        "crédit": "credit",
        "solde": "solde",
    }
    index = {}
    for i, name in enumerate(header):
        key = aliases.get(name)
        if key:
            index[key] = i
    has_header = "code" in index
    start = 1 if has_header else 0
    if not has_header:
        index = {"code": 0, "debit": 1, "credit": 2}
    out = []
    for line_no, raw in enumerate(rows[start:], start=start + 1):
        if not raw or not any(cell.strip() for cell in raw):
            continue
        code = (raw[index["code"]] if len(raw) > index["code"] else "").strip()
        if not code:
            continue
        debit = raw[index["debit"]].strip() if "debit" in index and len(raw) > index["debit"] else "0"
        credit = raw[index["credit"]].strip() if "credit" in index and len(raw) > index["credit"] else "0"
        solde = raw[index["solde"]].strip() if "solde" in index and len(raw) > index["solde"] else ""
        out.append({"code": code, "debit": debit, "credit": credit, "solde": solde, "line": line_no})
    return out


def active_opening(exercise: Exercise) -> Entry | None:
    if exercise.opening_entry_id:
        entry = exercise.opening_entry
        if entry and entry.status == EntryStatus.POSTED and not entry.reversals.exists():
            return entry
    for entry in Entry.objects.filter(
        exercise=exercise, source="opening", status=EntryStatus.POSTED
    ).order_by("created_at"):
        if not entry.reversals.exists():
            return entry
    return None


def _net_row(debit: Decimal, credit: Decimal) -> tuple[Decimal, Decimal]:
    net = debit - credit
    if net > 0:
        return net, ZERO
    if net < 0:
        return ZERO, -net
    return ZERO, ZERO


def preview_opening(company, raw_lines: list[dict]) -> dict:
    currency = company.currency_code or "XOF"
    merged: dict[str, dict] = {}
    warnings: list[str] = []
    errors: list[str] = []
    skipped = []
    for raw in raw_lines:
        code = normalize_code(raw.get("code") or "")
        if not code:
            continue
        debit = parse_amount(raw.get("debit") or "0", currency)
        credit = parse_amount(raw.get("credit") or "0", currency)
        solde_raw = raw.get("solde")
        if solde_raw not in (None, ""):
            solde = parse_amount(solde_raw, currency)
            if solde > 0:
                debit, credit = solde, ZERO
            elif solde < 0:
                debit, credit = ZERO, -solde
            else:
                debit, credit = ZERO, ZERO
        if debit == 0 and credit == 0:
            continue
        if debit != 0 and credit != 0:
            debit, credit = _net_row(debit, credit)
        if code[:1] == "9":
            skipped.append(code)
            continue
        account = Account.objects.filter(company=company, code=code, is_active=True).first()
        if account is None:
            errors.append(f"{code} : compte introuvable.")
            continue
        if not account.is_postable:
            errors.append(f"{code} : le compte n’est pas imputable.")
            continue
        bucket = merged.setdefault(
            code,
            {
                "account_id": str(account.id),
                "code": account.code,
                "label": account.label,
                "debit": ZERO,
                "credit": ZERO,
            },
        )
        bucket["debit"] += debit
        bucket["credit"] += credit
    if skipped:
        warnings.append(f"Classe 9 ignorée ({', '.join(skipped[:8])}{'…' if len(skipped) > 8 else ''}).")

    rows = []
    for item in merged.values():
        debit, credit = _net_row(item["debit"], item["credit"])
        if debit == 0 and credit == 0:
            continue
        item["debit"] = debit
        item["credit"] = credit
        rows.append(item)
    rows.sort(key=lambda item: item["code"])

    an_rows = [item for item in rows if is_balance_sheet(item["code"])]
    pnl_rows = [item for item in rows if is_pnl(item["code"])]
    has_result = any(item["code"].startswith("13") and not item["code"].startswith("132") for item in an_rows)

    xi = ZERO
    if pnl_rows:
        xi = cr_amounts(
            [
                {
                    "code": item["code"],
                    "close_debit": item["debit"],
                    "close_credit": item["credit"],
                    "mov_debit": item["debit"],
                    "mov_credit": item["credit"],
                    "open_debit": ZERO,
                    "open_credit": ZERO,
                }
                for item in pnl_rows
            ]
        ).get("XI", ZERO)
        if not has_result and xi != 0:
            result_code = "131" if xi > 0 else "139"
            result = resolve_account(company, result_code)
            if result is None:
                errors.append(f"Compte {result_code} introuvable pour virer le résultat N-1.")
            else:
                amount = abs(xi)
                an_rows.append(
                    {
                        "account_id": str(result.id),
                        "code": result.code,
                        "label": result.label,
                        "debit": ZERO if xi > 0 else amount,
                        "credit": amount if xi > 0 else ZERO,
                    }
                )
                warnings.append(f"Résultat N-1 ({xi}) viré au {result.code} pour l’à-nouveaux.")
                has_result = True

    an_debit = sum((item["debit"] for item in an_rows), ZERO)
    an_credit = sum((item["credit"] for item in an_rows), ZERO)
    if an_rows and an_debit != an_credit:
        errors.append(
            f"À-nouveaux non équilibrés (débit {an_debit} ≠ crédit {an_credit})."
        )
    if not an_rows and not errors:
        errors.append("Aucun compte de bilan (classes 1 à 5) à reprendre.")

    return {
        "rows": [
            {
                **item,
                "kind": "pnl" if is_pnl(item["code"]) else "opening",
                "debit": format_amount(item["debit"]),
                "credit": format_amount(item["credit"]),
            }
            for item in rows
        ],
        "an_lines": [
            {
                "account_id": item["account_id"],
                "code": item["code"],
                "label": item["label"],
                "debit": format_amount(item["debit"]),
                "credit": format_amount(item["credit"]),
            }
            for item in an_rows
        ],
        "pnl_count": len(pnl_rows),
        "an_debit": format_amount(an_debit),
        "an_credit": format_amount(an_credit),
        "net_result_prior": format_amount(xi),
        "warnings": warnings,
        "errors": errors,
        "ok": not errors,
    }


def _journal_an(company) -> Journal:
    journal, _ = Journal.objects.get_or_create(
        company=company,
        code="AN",
        defaults={
            "organization": company.organization,
            "name": "À-nouveaux",
            "type": JournalType.OD,
        },
    )
    return journal


def _seed_prior_snapshots(company, exercise: Exercise, preview: dict) -> int:
    """Écrit les soldes N-1 sur décembre, sans toucher janvier (déjà mouvementé par AN)."""
    prior = ensure_company_ledger(company, exercise.year - 1)
    december = prior.periods.filter(month=12).first()
    if december is None:
        return 0
    if Entry.objects.filter(exercise=prior, status=EntryStatus.POSTED).exclude(source="opening").exists():
        return 0
    seeded = 0
    by_account: dict[str, dict] = {}
    for item in preview["an_lines"]:
        by_account[item["account_id"]] = item
    for item in preview["rows"]:
        if item["kind"] != "pnl":
            continue
        by_account[item["account_id"]] = item
    for item in by_account.values():
        account = Account.objects.filter(id=item["account_id"], company=company).first()
        if account is None:
            continue
        debit = Decimal(item["debit"])
        credit = Decimal(item["credit"])
        snapshot, created = BalanceSnapshot.objects.get_or_create(
            period=december,
            account=account,
            defaults={
                "organization": company.organization,
                "company": company,
                "open_debit": debit,
                "open_credit": credit,
                "mov_debit": ZERO,
                "mov_credit": ZERO,
            },
        )
        if not created:
            snapshot.open_debit = debit
            snapshot.open_credit = credit
            snapshot.mov_debit = ZERO
            snapshot.mov_credit = ZERO
            snapshot.save(update_fields=["open_debit", "open_credit", "mov_debit", "mov_credit"])
        seeded += 1
    if preview["pnl_count"]:
        prior.net_result = Decimal(preview["net_result_prior"])
        prior.save(update_fields=["net_result"])
    return seeded


@transaction.atomic
def post_opening(company, exercise: Exercise, user, raw_lines: list[dict]) -> dict:
    if exercise.status == ExerciseStatus.CLOSED:
        raise HttpError(409, "Exercice clôturé : impossible de passer les à-nouveaux.")
    existing = active_opening(exercise)
    if existing:
        raise HttpError(409, "À-nouveaux déjà validés — contrepasser l’écriture pour reprendre.")
    first = exercise.periods.filter(month=exercise.starts_on.month).order_by("starts_on").first()
    if first and first.status != PeriodStatus.OPEN:
        raise HttpError(400, "La première période de l’exercice doit être ouverte.")
    preview = preview_opening(company, raw_lines)
    if not preview["ok"]:
        raise HttpError(400, preview["errors"][0])
    journal = _journal_an(company)
    from apps.ledger.services.posting import create_draft, post_entry

    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=exercise.starts_on,
        value_date=exercise.starts_on,
        description=f"À-nouveaux {exercise.year}",
        document_ref=f"AN-{exercise.year}",
        raw_lines=[
            {
                "account_id": line["account_id"],
                "debit": line["debit"],
                "credit": line["credit"],
                "label": f"AN {line['code']}",
            }
            for line in preview["an_lines"]
        ],
        source="opening",
    )
    entry = post_entry(entry, user)
    exercise.opening_entry = entry
    exercise.save(update_fields=["opening_entry"])
    prior_seeded = _seed_prior_snapshots(company, exercise, preview)
    preview["entry_id"] = str(entry.id)
    preview["entry_number"] = entry.number_display
    preview["prior_seeded"] = prior_seeded
    preview["posted"] = True
    return preview


def opening_state(company, exercise: Exercise) -> dict:
    entry = active_opening(exercise)
    prior = Exercise.objects.filter(company=company, year=exercise.year - 1).first()
    prior_seeded = 0
    if prior:
        december = prior.periods.filter(month=12).first()
        if december:
            prior_seeded = BalanceSnapshot.objects.filter(period=december).count()
    blockers = []
    if exercise.status == ExerciseStatus.CLOSED:
        blockers.append("Exercice clôturé.")
    if entry:
        blockers.append("À-nouveaux déjà validés.")
    first = exercise.periods.order_by("starts_on").first()
    if first and first.status != PeriodStatus.OPEN and not entry:
        blockers.append("La première période n’est pas ouverte.")
    return {
        "year": exercise.year,
        "prior_year": exercise.year - 1,
        "posted": bool(entry),
        "entry_id": str(entry.id) if entry else None,
        "entry_number": entry.number_display if entry else "",
        "prior_seeded": prior_seeded,
        "can_post": not blockers,
        "blockers": blockers,
        "template": OPENING_TEMPLATE,
    }
