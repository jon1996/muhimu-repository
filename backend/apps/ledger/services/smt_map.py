"""Système minimal de trésorerie (AUDCIF art. 11–13, Titre X).

Liasse SMT : situation patrimoniale (inventaire de fin d’exercice) + état de
trésorerie (recettes / dépenses constatées sur la classe 5). Le CA HT (poste XB)
est comparé aux seuils 60 / 40 / 30 millions selon l’activité.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from apps.ledger.models import Entry, EntryStatus
from apps.ledger.services.sn_map import (
    Line,
    ZERO,
    _d,
    cr_amounts,
    fmt,
    sum_credit_side,
    sum_debit_side,
    sum_net_credit,
    sum_net_debit,
)

SMT_THRESHOLDS = {
    "trade": Decimal("60000000"),
    "craft": Decimal("40000000"),
    "services": Decimal("30000000"),
}
SMT_THRESHOLD_LABELS = {
    "trade": "60 millions F CFA (négoce)",
    "craft": "40 millions F CFA (artisanat)",
    "services": "30 millions F CFA (services)",
}
CASH_SKIP_SOURCES = frozenset(
    {
        "opening",
        "cage",
        "cage_alloc",
        "cage_close",
        "class9",
        "result_close",
        "depreciation",
        "stock_variation",
        "allocation",
        "fx_reval",
    }
)

_SITUATION_ACTIF = (
    ("IA", "Immobilisations", "detail"),
    ("IB", "Stocks", "detail"),
    ("IC", "Créances et emplois assimilés", "detail"),
    ("ID", "Trésorerie", "detail"),
    ("IE", "Total actif", "total"),
)
_SITUATION_PASSIF = (
    ("PA", "Capitaux propres", "detail"),
    ("PB", "Dettes financières et provisions", "detail"),
    ("PC", "Dettes d’exploitation", "detail"),
    ("PD", "Trésorerie-passif", "detail"),
    ("PE", "Total passif", "total"),
)
_ET_LAYOUT = (
    ("RA", "Encaissements sur ventes et créances clients", "detail"),
    ("RB", "Autres encaissements d’exploitation", "detail"),
    ("RC", "Encaissements financiers", "detail"),
    ("RD", "Encaissements HAO et cessions d’immobilisations", "detail"),
    ("RE", "Apports et emprunts", "detail"),
    ("RF", "Autres recettes", "detail"),
    ("RG", "Total recettes", "total"),
    ("DA", "Paiements fournisseurs et achats", "detail"),
    ("DB", "Charges de personnel", "detail"),
    ("DC", "Impôts et taxes", "detail"),
    ("DD", "Autres décaissements d’exploitation", "detail"),
    ("DE", "Décaissements financiers", "detail"),
    ("DF", "Acquisitions d’immobilisations", "detail"),
    ("DG", "Remboursements d’emprunts et prélèvements", "detail"),
    ("DH", "Autres dépenses", "detail"),
    ("DI", "Total dépenses", "total"),
    ("EA", "Excédent / insuffisance de trésorerie", "total"),
    ("EB", "Trésorerie à l’ouverture", "detail"),
    ("EC", "Trésorerie à la clôture", "total"),
)


def is_treasury(code: str) -> bool:
    return bool(code) and code[0] == "5"


def receipt_post(code: str) -> str:
    if code.startswith(("70", "41")):
        return "RA"
    if code.startswith(("71", "72", "73", "75", "78", "79", "4")):
        return "RB"
    if code.startswith("77"):
        return "RC"
    if code.startswith(("8", "2")):
        return "RD"
    if code.startswith(("10", "11", "12", "16", "17")):
        return "RE"
    return "RF"


def payment_post(code: str) -> str:
    if code.startswith(("60", "40")):
        return "DA"
    if code.startswith(("66", "42", "43")):
        return "DB"
    if code.startswith(("64", "44", "89")):
        return "DC"
    if code.startswith(("61", "62", "63", "65", "68", "69")):
        return "DD"
    if code.startswith("67"):
        return "DE"
    if code.startswith("2"):
        return "DF"
    if code.startswith(("16", "17", "10", "11")):
        return "DG"
    return "DH"


def smt_threshold(activity_kind: str) -> Decimal:
    return SMT_THRESHOLDS.get(activity_kind or "trade", SMT_THRESHOLDS["trade"])


def build_eligibility(company, revenue: Decimal) -> dict:
    kind = getattr(company, "activity_kind", None) or "trade"
    threshold = smt_threshold(kind)
    eligible = revenue <= threshold
    warning = ""
    if getattr(company, "accounting_regime", "") == "smt" and not eligible:
        warning = (
            f"CA HT {fmt(revenue)} supérieur au seuil SMT {SMT_THRESHOLD_LABELS[kind]}. "
            "Le système normal s’impose (art. 13)."
        )
    elif getattr(company, "accounting_regime", "") != "smt" and eligible:
        warning = (
            f"CA HT {fmt(revenue)} sous le seuil {SMT_THRESHOLD_LABELS[kind]} : "
            "le SMT est possible."
        )
    return {
        "regime": getattr(company, "accounting_regime", "normal") or "normal",
        "activity_kind": kind,
        "threshold": fmt(threshold),
        "threshold_label": SMT_THRESHOLD_LABELS.get(kind, SMT_THRESHOLD_LABELS["trade"]),
        "revenue": fmt(revenue),
        "eligible": eligible,
        "warning": warning,
    }


def situation_amounts(rows: list[dict]) -> dict[str, Decimal]:
    values = {
        "IA": sum_net_debit(rows, ("2",)),
        "IB": sum_net_debit(rows, ("3",)),
        "IC": sum_debit_side(rows, ("4",)),
        "ID": sum_debit_side(rows, ("5",)),
        "PA": sum_net_credit(rows, ("10", "11", "12", "13", "14")),
        "PB": sum_net_credit(rows, ("15", "16", "17", "18", "19")),
        "PC": sum_credit_side(rows, ("4",)),
        "PD": sum_credit_side(rows, ("5",)),
    }
    values["IE"] = values["IA"] + values["IB"] + values["IC"] + values["ID"]
    values["PE"] = values["PA"] + values["PB"] + values["PC"] + values["PD"]
    return values


def build_situation(current_rows: list[dict], prior_rows: list[dict]) -> dict:
    current = situation_amounts(current_rows)
    prior = situation_amounts(prior_rows) if prior_rows else {code: ZERO for code in current}

    def lines(layout):
        out = []
        for code, label, kind in layout:
            out.append(
                Line(
                    code=code,
                    label=label,
                    current=current[code],
                    prior=prior.get(code, ZERO),
                    bold=kind == "total",
                    kind=kind,
                ).as_dict()
            )
        return out

    return {
        "actif": lines(_SITUATION_ACTIF),
        "passif": lines(_SITUATION_PASSIF),
        "balanced": current["IE"] == current["PE"],
    }


def treasury_open(rows: list[dict]) -> Decimal:
    total = ZERO
    for row in rows:
        if not is_treasury(row.get("code") or ""):
            continue
        total += _d(row.get("open_debit")) - _d(row.get("open_credit"))
    return total


def treasury_close(rows: list[dict]) -> Decimal:
    total = ZERO
    for row in rows:
        if not is_treasury(row.get("code") or ""):
            continue
        total += _d(row.get("close_debit")) - _d(row.get("close_credit"))
    return total


def _allocate(net: Decimal, parts: list[tuple[str, Decimal]]) -> list[tuple[str, Decimal]]:
    if net == 0:
        return []
    total = sum((amt for _, amt in parts), ZERO)
    if not parts or total == 0:
        return [("", net)]
    allocated = []
    remaining = net
    for index, (code, amt) in enumerate(parts):
        share = remaining if index == len(parts) - 1 else (net * amt / total)
        allocated.append((code, share))
        remaining -= share
    return allocated


def collect_cash_posts(company, starts_on: date, ends_on: date) -> dict[str, Decimal]:
    buckets: dict[str, Decimal] = defaultdict(lambda: ZERO)
    entries = (
        Entry.objects.filter(
            company=company,
            status=EntryStatus.POSTED,
            accounting_date__gte=starts_on,
            accounting_date__lte=ends_on,
        )
        .exclude(source__in=CASH_SKIP_SOURCES)
        .prefetch_related("lines__account")
    )
    for entry in entries:
        cash_dr = ZERO
        cash_cr = ZERO
        others: list[tuple[str, Decimal, Decimal]] = []
        for line in entry.lines.all():
            code = line.account.code if line.account_id else ""
            if not code or code.startswith("9"):
                continue
            if is_treasury(code):
                cash_dr += line.debit
                cash_cr += line.credit
            else:
                others.append((code, line.debit, line.credit))
        net = cash_dr - cash_cr
        if net == 0:
            continue
        if net > 0:
            parts = [(code, credit) for code, _debit, credit in others if credit > 0]
            for code, amount in _allocate(net, parts):
                buckets[receipt_post(code) if code else "RF"] += amount
        else:
            parts = [(code, debit) for code, debit, _credit in others if debit > 0]
            for code, amount in _allocate(-net, parts):
                buckets[payment_post(code) if code else "DH"] += amount
    return buckets


def _et_values(buckets: dict[str, Decimal], open_cash: Decimal, close_cash: Decimal) -> dict[str, Decimal]:
    values = {code: buckets.get(code, ZERO) for code, _label, _kind in _ET_LAYOUT}
    values["RG"] = values["RA"] + values["RB"] + values["RC"] + values["RD"] + values["RE"] + values["RF"]
    values["DI"] = (
        values["DA"]
        + values["DB"]
        + values["DC"]
        + values["DD"]
        + values["DE"]
        + values["DF"]
        + values["DG"]
        + values["DH"]
    )
    values["EA"] = values["RG"] - values["DI"]
    values["EB"] = open_cash
    values["EC"] = values["EB"] + values["EA"]
    gap = close_cash - values["EC"]
    if gap:
        values["ED"] = gap
    return values


def build_etat_tresorerie(
    company,
    *,
    starts_on: date,
    ends_on: date,
    open_cash: Decimal,
    close_cash: Decimal,
    prior_starts: date | None = None,
    prior_ends: date | None = None,
    prior_open: Decimal | None = None,
    prior_close: Decimal | None = None,
) -> dict:
    current_buckets = collect_cash_posts(company, starts_on, ends_on)
    current = _et_values(current_buckets, open_cash, close_cash)
    if prior_starts and prior_ends:
        prior_buckets = collect_cash_posts(company, prior_starts, prior_ends)
        prior = _et_values(prior_buckets, prior_open or ZERO, prior_close or ZERO)
    else:
        prior = {code: ZERO for code in current}

    lines = []
    for code, label, kind in _ET_LAYOUT:
        lines.append(
            Line(
                code=code,
                label=label,
                current=current[code],
                prior=prior.get(code, ZERO),
                bold=kind == "total",
                kind=kind,
            ).as_dict()
        )
    if current.get("ED"):
        lines.append(
            Line(
                code="ED",
                label="Écart de contrôle (trésorerie bilan − flux)",
                current=current["ED"],
                prior=prior.get("ED", ZERO),
                kind="detail",
            ).as_dict()
        )
    return {"lines": lines}


def revenue_ht(rows: list[dict]) -> Decimal:
    return cr_amounts(rows).get("XB", ZERO)


def eligibility_for(company, period) -> dict:
    from apps.ledger.services.balance import trial_balance
    from apps.ledger.services.closing import closing_lines_for, restore_pnl_rows

    rows = trial_balance(company, period)
    pnl = restore_pnl_rows(rows, closing_lines_for(period.exercise) if period.exercise_id else [])
    return build_eligibility(company, revenue_ht(pnl))
