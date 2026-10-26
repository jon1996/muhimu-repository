"""Clôture d’exercice SYSCOHADA — arrêté (6/7/8 → 13) et affectation AG (note 31, FN)."""

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
    Entry,
    EntryLine,
    EntryStatus,
    Exercise,
    ExerciseStatus,
    Journal,
    JournalType,
    PeriodStatus,
)
from apps.ledger.money import parse_amount, quantize_amount
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.balance import trial_balance_ytd
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.services.setup import ensure_company_ledger
from apps.ledger.services.sn_map import cr_amounts

ZERO = Decimal("0")
PNL_CLASSES = "678"


def suggest_legal_reserve(
    profit: Decimal, capital: Decimal, current_legal: Decimal, currency: str = "XOF"
) -> Decimal:
    """10 % du bénéfice jusqu’à 20 % du capital (SA / SARL)."""
    if profit <= 0:
        return ZERO
    tenth = quantize_amount(profit * Decimal("0.10"), currency)
    room = quantize_amount(capital * Decimal("0.20"), currency) - current_legal
    if room < 0:
        room = ZERO
    return tenth if tenth <= room else room


def restore_pnl_rows(rows: list[dict], closing_lines: list[dict]) -> list[dict]:
    """Retire l’OD d’arrêté des classes 6/7/8 pour que le CR reste lisible après clôture."""
    by_code: dict[str, dict[str, Decimal]] = {}
    for line in closing_lines:
        code = line["code"]
        if not code or code[0] not in PNL_CLASSES:
            continue
        bucket = by_code.setdefault(code, {"debit": ZERO, "credit": ZERO})
        bucket["debit"] += line["debit"]
        bucket["credit"] += line["credit"]
    if not by_code:
        return rows
    restored = []
    for row in rows:
        adj = by_code.get(row["code"])
        if not adj:
            restored.append(row)
            continue
        clone = dict(row)
        clone["mov_debit"] = row["mov_debit"] - adj["debit"]
        clone["mov_credit"] = row["mov_credit"] - adj["credit"]
        clone["close_debit"] = row["close_debit"] - adj["debit"]
        clone["close_credit"] = row["close_credit"] - adj["credit"]
        restored.append(clone)
    return restored


def closing_lines_for(exercise: Exercise) -> list[dict]:
    entry = exercise.result_entry
    if not entry or entry.status != EntryStatus.POSTED:
        entry = (
            Entry.objects.filter(
                exercise=exercise, source="result_close", status=EntryStatus.POSTED
            )
            .prefetch_related("lines__account")
            .first()
        )
    if not entry:
        return []
    return [
        {"code": line.account.code, "debit": line.debit, "credit": line.credit}
        for line in entry.lines.all()
    ]


def tft_dividends_paid(company, period: AccountingPeriod) -> Decimal:
    """FN = dividendes décaissés (crédit trésorerie) depuis le 1er janvier de l’exercice."""
    total = (
        EntryLine.objects.filter(
            company=company,
            entry__source="dividend_payment",
            entry__status=EntryStatus.POSTED,
            entry__accounting_date__gte=period.exercise.starts_on,
            entry__accounting_date__lte=period.ends_on,
            account__code__startswith="5",
        ).aggregate(total=Sum("credit"))["total"]
        or ZERO
    )
    return -total


def note31_text(company, exercise: Exercise) -> str:
    years = list(
        Exercise.objects.filter(
            company=company, year__gte=exercise.year - 4, year__lte=exercise.year
        ).order_by("year")
    )
    if not any(item.net_result or item.revenue or item.allocation_entry_id for item in years):
        return ""
    parts = []
    for item in years:
        chunk = f"{item.year} : résultat {item.net_result} · CA {item.revenue}"
        if item.allocation_entry_id or item.dividends_amount or item.legal_reserve_amount:
            chunk += (
                f" · légale {item.legal_reserve_amount} · libres {item.free_reserve_amount}"
                f" · RAN {item.retained_amount} · dividendes {item.dividends_amount}"
            )
        parts.append(chunk)
    return " · ".join(parts)


def _net_credit(rows: list[dict], prefixes: tuple[str, ...]) -> Decimal:
    total = ZERO
    for row in rows:
        if any(row["code"].startswith(prefix) for prefix in prefixes):
            total += row["close_credit"] - row["close_debit"]
    return total


def preview_close(company, exercise: Exercise) -> dict:
    last = exercise.periods.order_by("-starts_on").first()
    rows = trial_balance_ytd(company, exercise)
    cr = cr_amounts(rows) if rows else {}
    net = cr.get("XI", ZERO)
    revenue = cr.get("XB", ZERO)
    currency = company.currency_code or "XOF"
    capital = _net_credit(rows, ("101", "102", "103"))
    legal = _net_credit(rows, ("111",))
    suggested = suggest_legal_reserve(net, capital, legal, currency)
    drafts = Entry.objects.filter(exercise=exercise, status=EntryStatus.DRAFT).count()
    blockers: list[str] = []
    if exercise.status == ExerciseStatus.CLOSED:
        blockers.append("Exercice déjà clôturé.")
    if drafts:
        blockers.append(f"{drafts} brouillon(s) encore ouvert(s).")
    if last and last.status != PeriodStatus.OPEN:
        blockers.append(
            "La dernière période doit rester ouverte pour passer l’OD d’arrêté (6/7 → 13)."
        )
    remaining = net - suggested if net > 0 else ZERO
    return {
        "net_result": net,
        "revenue": revenue,
        "suggested_legal_reserve": suggested,
        "suggested_retained": remaining,
        "capital": capital,
        "current_legal_reserve": legal,
        "blockers": blockers,
        "can_close": not blockers,
        "can_allocate": exercise.status == ExerciseStatus.CLOSED and not exercise.allocation_entry_id,
        "last_period_id": str(last.id) if last else None,
    }


def _require_account(company, code: str, label: str) -> Account:
    account = resolve_account(company, code)
    if not account:
        raise HttpError(400, f"Compte {label} ({code}) introuvable.")
    return account


def _journal_od(company) -> Journal:
    journal = Journal.objects.filter(company=company, type=JournalType.OD).first()
    if not journal:
        raise HttpError(400, "Journal OD introuvable.")
    return journal


@transaction.atomic
def close_exercise(company, exercise: Exercise, user, closed_on: date | None = None) -> Exercise:
    # Verrou ligne exercice : évite deux clôtures concurrentes (CLOSE-01).
    exercise = (
        Exercise.objects.select_for_update()
        .filter(pk=exercise.pk, company=company)
        .first()
    )
    if exercise is None:
        raise HttpError(404, "Exercice introuvable pour cette société.")
    preview = preview_close(company, exercise)
    if not preview["can_close"]:
        raise HttpError(409, preview["blockers"][0])
    rows = trial_balance_ytd(company, exercise)
    cr = cr_amounts(rows)
    net = cr["XI"]
    revenue = cr["XB"]
    currency = company.currency_code or "XOF"

    if not exercise.result_entry_id:
        raw_lines: list[dict] = []
        debit_sum = ZERO
        credit_sum = ZERO
        for row in rows:
            code = row["code"]
            if not code or code[0] not in PNL_CLASSES:
                continue
            net_d = row["close_debit"] - row["close_credit"]
            if net_d == 0:
                continue
            if net_d > 0:
                credit_sum += net_d
                raw_lines.append(
                    {
                        "account_id": row["account_id"],
                        "debit": "0",
                        "credit": format(net_d, "f"),
                        "label": "Virement du résultat",
                    }
                )
            else:
                amount = -net_d
                debit_sum += amount
                raw_lines.append(
                    {
                        "account_id": row["account_id"],
                        "debit": format(amount, "f"),
                        "credit": "0",
                        "label": "Virement du résultat",
                    }
                )
        if raw_lines:
            net = debit_sum - credit_sum
            if net > 0:
                result_acc = _require_account(company, "131", "résultat — bénéfice")
                raw_lines.append(
                    {
                        "account_id": str(result_acc.id),
                        "debit": "0",
                        "credit": format(net, "f"),
                        "label": "Résultat net — bénéfice",
                    }
                )
            elif net < 0:
                result_acc = _require_account(company, "139", "résultat — perte")
                raw_lines.append(
                    {
                        "account_id": str(result_acc.id),
                        "debit": format(-net, "f"),
                        "credit": "0",
                        "label": "Résultat net — perte",
                    }
                )
            journal = _journal_od(company)
            key = hashlib.sha256(f"close:{exercise.id}:{net}".encode()).hexdigest()
            entry = create_draft(
                company=company,
                journal=journal,
                accounting_date=exercise.ends_on,
                value_date=exercise.ends_on,
                description=f"Arrêté des comptes {exercise.year}",
                document_ref=f"CLOTURE-{exercise.year}",
                raw_lines=raw_lines,
                source="result_close",
                idempotency_key=key,
            )
            if entry.status != EntryStatus.POSTED:
                entry = post_entry(entry, user)
            exercise.result_entry = entry

    exercise.net_result = quantize_amount(net, currency)
    exercise.revenue = quantize_amount(revenue, currency)
    exercise.closed_on = closed_on or date.today()
    exercise.status = ExerciseStatus.CLOSED
    exercise.save(
        update_fields=["net_result", "revenue", "closed_on", "status", "result_entry"]
    )
    ensure_company_ledger(company, exercise.year + 1)
    return exercise


def _parse_split(payload: dict, currency: str) -> dict[str, Decimal]:
    return {
        "legal": parse_amount(payload.get("legal_reserve") or "0", currency),
        "free": parse_amount(payload.get("free_reserve") or "0", currency),
        "retained": parse_amount(payload.get("retained") or "0", currency),
        "dividends": parse_amount(payload.get("dividends") or "0", currency),
    }


@transaction.atomic
def allocate_result(company, exercise: Exercise, user, payload: dict) -> Exercise:
    if exercise.status != ExerciseStatus.CLOSED:
        raise HttpError(409, "Arrêtez d’abord l’exercice (bilan avant répartition).")
    if exercise.allocation_entry_id:
        raise HttpError(409, "Le résultat de cet exercice est déjà affecté.")
    currency = company.currency_code or "XOF"
    splits = _parse_split(payload, currency)
    net = exercise.net_result
    if any(value < 0 for value in splits.values()):
        raise HttpError(400, "Les affectations ne peuvent pas être négatives.")
    if net > 0:
        total = splits["legal"] + splits["free"] + splits["retained"] + splits["dividends"]
        if total != net:
            raise HttpError(400, f"La répartition ({total}) doit égaler le bénéfice ({net}).")
    elif net < 0:
        if splits["legal"] or splits["free"] or splits["dividends"]:
            raise HttpError(400, "Une perte ne se distribue pas : tout au report à nouveau.")
        if splits["retained"] != -net:
            raise HttpError(400, f"La perte ({net}) doit être portée en report à nouveau.")
    else:
        if any(splits.values()):
            raise HttpError(400, "Résultat nul : aucune affectation.")
        exercise.approved_on = payload["approved_on"]
        exercise.save(update_fields=["approved_on"])
        return exercise

    next_ex = ensure_company_ledger(company, exercise.year + 1)
    approved = payload["approved_on"]
    if approved < next_ex.starts_on:
        posting_date = next_ex.starts_on
    elif approved > next_ex.ends_on:
        posting_date = next_ex.ends_on
    else:
        posting_date = approved

    journal = _journal_od(company)
    raw_lines: list[dict] = []
    if net > 0:
        result_acc = _require_account(company, "131", "résultat — bénéfice")
        raw_lines.append(
            {
                "account_id": str(result_acc.id),
                "debit": format(net, "f"),
                "credit": "0",
                "label": f"Affectation du résultat {exercise.year}",
            }
        )
        targets = [
            ("111", splits["legal"], "Réserve légale"),
            ("118", splits["free"], "Réserves libres"),
            ("121", splits["retained"], "Report à nouveau"),
            ("465", splits["dividends"], "Dividendes à payer"),
        ]
        for code, amount, label in targets:
            if amount <= 0:
                continue
            acc = _require_account(company, code, label)
            raw_lines.append(
                {
                    "account_id": str(acc.id),
                    "debit": "0",
                    "credit": format(amount, "f"),
                    "label": label,
                }
            )
    else:
        result_acc = _require_account(company, "139", "résultat — perte")
        ran = _require_account(company, "129", "report à nouveau débiteur")
        raw_lines.append(
            {
                "account_id": str(ran.id),
                "debit": format(-net, "f"),
                "credit": "0",
                "label": f"Report de la perte {exercise.year}",
            }
        )
        raw_lines.append(
            {
                "account_id": str(result_acc.id),
                "debit": "0",
                "credit": format(-net, "f"),
                "label": f"Affectation de la perte {exercise.year}",
            }
        )

    key = hashlib.sha256(f"alloc:{exercise.id}:{net}:{splits}".encode()).hexdigest()
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=posting_date,
        value_date=posting_date,
        description=f"Affectation du résultat {exercise.year}",
        document_ref=f"AGO-{exercise.year}",
        raw_lines=raw_lines,
        source="allocation",
        idempotency_key=key,
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)

    payment = None
    if net > 0 and splits["dividends"] > 0 and payload.get("pay_dividends"):
        bank_id = payload.get("bank_account_id")
        bank = (
            Account.objects.filter(id=bank_id, company=company, is_postable=True).first()
            if bank_id
            else resolve_account(company, "521")
        )
        if not bank or not bank.code.startswith("5"):
            raise HttpError(400, "Compte de trésorerie requis pour payer les dividendes.")
        payable = _require_account(company, "465", "dividendes à payer")
        pay_key = hashlib.sha256(f"divpay:{exercise.id}:{splits['dividends']}".encode()).hexdigest()
        payment = create_draft(
            company=company,
            journal=journal,
            accounting_date=posting_date,
            value_date=posting_date,
            description=f"Paiement des dividendes {exercise.year}",
            document_ref=f"DIV-{exercise.year}",
            raw_lines=[
                {
                    "account_id": str(payable.id),
                    "debit": format(splits["dividends"], "f"),
                    "credit": "0",
                    "label": "Dividendes versés",
                },
                {
                    "account_id": str(bank.id),
                    "debit": "0",
                    "credit": format(splits["dividends"], "f"),
                    "label": "Dividendes versés",
                },
            ],
            source="dividend_payment",
            idempotency_key=pay_key,
        )
        if payment.status != EntryStatus.POSTED:
            payment = post_entry(payment, user)

    exercise.approved_on = approved
    exercise.legal_reserve_amount = splits["legal"]
    exercise.free_reserve_amount = splits["free"]
    exercise.retained_amount = splits["retained"]
    exercise.dividends_amount = splits["dividends"]
    exercise.allocation_entry = entry
    exercise.payment_entry = payment
    exercise.save(
        update_fields=[
            "approved_on",
            "legal_reserve_amount",
            "free_reserve_amount",
            "retained_amount",
            "dividends_amount",
            "allocation_entry",
            "payment_entry",
        ]
    )
    return exercise
