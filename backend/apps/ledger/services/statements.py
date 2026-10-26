"""États financiers SYSCOHADA — Système Normal (Titre IX)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from apps.ledger.models import AccountingPeriod, Exercise
from apps.tenancy.liasse import identity_payload, note36_text
from apps.ledger.services.balance import trial_balance
from apps.ledger.services.assets import note3_movements, tft_investment_from_register
from apps.ledger.services.closing import closing_lines_for, note31_text, restore_pnl_rows, tft_dividends_paid
from apps.ledger.services.stocks import note6_text, note7_text
from apps.ledger.services.lettering import note7_open_text, note17_open_text, note17_text
from apps.ledger.services.bank_rec import note11_open_text
from apps.ledger.services.cash import note11_cash_text
from apps.ledger.services.commitments import note1_text
from apps.ledger.services.esg import note35_text, payroll_from_rows
from apps.ledger.services.notes_balance import computed_balance_notes, computed_cr_notes
from apps.ledger.services.notes_sn import parse_notes
from apps.ledger.services.sn_map import (
    build_bilan,
    build_compte_resultat,
    build_tft,
    cafg,
    financial_analysis,
)
from apps.ledger.services.smt_map import (
    build_eligibility,
    build_etat_tresorerie,
    build_situation,
    revenue_ht,
    treasury_close,
    treasury_open,
)

_ACTIVITY = {
    "trade": "Commerce",
    "craft": "Artisanat",
    "services": "Services",
}
_REGIME = {
    "normal": "Système Normal",
    "smt": "Système minimal de trésorerie",
}


def _period_for(company, exercise: Exercise | None) -> AccountingPeriod | None:
    if not exercise:
        return None
    today = date.today()
    current = exercise.periods.filter(starts_on__lte=today, ends_on__gte=today).first()
    if current:
        return current
    return exercise.periods.order_by("-starts_on").first()


def _duration_months(starts_on: date, ends_on: date) -> int:
    days = (ends_on - starts_on).days + 1
    return max(1, round(days / 30.4375))


def build_statements(company, period: AccountingPeriod | None = None) -> dict:
    exercise = period.exercise if period else Exercise.objects.filter(
        company=company, year=date.today().year
    ).first()
    period = period or _period_for(company, exercise)
    if not period:
        raise ValueError("Aucune période pour établir les états.")

    current_rows = trial_balance(company, period)
    prior_exercise = Exercise.objects.filter(company=company, year=period.year - 1).first()
    prior_period = None
    if prior_exercise:
        last_day = date(prior_exercise.year, 12, monthrange(prior_exercise.year, 12)[1])
        prior_period = (
            prior_exercise.periods.filter(ends_on__lte=last_day).order_by("-ends_on").first()
            or prior_exercise.periods.order_by("-starts_on").first()
        )
    prior_rows = trial_balance(company, prior_period) if prior_period else []
    pnl_rows = restore_pnl_rows(current_rows, closing_lines_for(exercise) if exercise else [])
    prior_pnl = restore_pnl_rows(prior_rows, closing_lines_for(prior_exercise) if prior_exercise else [])

    bilan, bilan_n, bilan_p = build_bilan(current_rows, prior_rows)
    result, cr_n, cr_p = build_compte_resultat(pnl_rows, prior_pnl)
    eligibility = build_eligibility(company, revenue_ht(pnl_rows))
    smt = company.accounting_regime == "smt"
    if smt:
        first = exercise.periods.order_by("starts_on").first() if exercise else period
        opening_rows = trial_balance(company, first) if first else current_rows
        prior_first = (
            prior_exercise.periods.order_by("starts_on").first() if prior_exercise else None
        )
        prior_opening = trial_balance(company, prior_first) if prior_first else []
        bilan = build_situation(current_rows, prior_rows)
        tft = build_etat_tresorerie(
            company,
            starts_on=exercise.starts_on if exercise else period.starts_on,
            ends_on=period.ends_on,
            open_cash=treasury_open(opening_rows),
            close_cash=treasury_close(current_rows),
            prior_starts=prior_exercise.starts_on if prior_exercise else None,
            prior_ends=prior_period.ends_on if prior_period else None,
            prior_open=treasury_open(prior_opening) if prior_opening else Decimal("0"),
            prior_close=treasury_close(prior_rows) if prior_rows else Decimal("0"),
        )
        result = {"lines": [], "net": result["net"]}
        analysis = None
    else:
        investment = tft_investment_from_register(company, period)
        dividends = tft_dividends_paid(company, period)
        tft = build_tft(
            current_rows, prior_rows, cr_n, cr_p, bilan_n, bilan_p, investment=investment, dividends=dividends
        )
        analysis = financial_analysis(bilan_n, bilan_p)
        analysis["cafg"] = {
            "current": format(cafg(cr_n, pnl_rows), "f"),
            "prior": format(cafg(cr_p, prior_pnl) if prior_pnl else Decimal("0"), "f"),
        }
        analysis["ebe"] = {"current": format(cr_n["XD"], "f"), "prior": format(cr_p["XD"], "f")}
        analysis["net"] = {"current": format(cr_n["XI"], "f"), "prior": format(cr_p["XI"], "f")}

    notes = parse_notes(exercise.notes_annexes if exercise else "")
    from_balance = computed_balance_notes(current_rows)
    from_cr = computed_cr_notes(pnl_rows)
    for item in notes:
        extra = from_balance.get(item["number"]) or from_cr.get(item["number"])
        if extra:
            item["computed"] = extra
            item["status"] = "A"
        if item["number"] == 1:
            note1 = note1_text(company)
            if note1:
                item["computed"] = note1
                item["status"] = "A"
        if item["number"] == 34:
            if smt:
                item["computed"] = (
                    f"SMT · CA HT {eligibility['revenue']} · seuil {eligibility['threshold_label']}"
                )
            else:
                item["computed"] = (
                    f"FR {analysis['fr']['current']} · BFE {analysis['bfe']['current']} · "
                    f"BF.HAO {analysis['bf_hao']['current']} · TN {analysis['tn']['current']} · "
                    f"CAFG {analysis['cafg']['current']} · EBE {analysis['ebe']['current']}"
                )
        if item["number"] == 3 and exercise:
            note3 = note3_movements(company, exercise)
            if note3:
                item["computed"] = note3
        if item["number"] == 31 and exercise:
            note31 = note31_text(company, exercise)
            if note31:
                item["computed"] = note31
                item["status"] = "A"
        if item["number"] == 6 and exercise:
            note6 = note6_text(company, exercise)
            if note6:
                item["computed"] = note6
                item["status"] = "A"
        if item["number"] == 7:
            parts = [note7_text(current_rows), note7_open_text(company)]
            note7 = " · ".join(part for part in parts if part)
            if note7:
                item["computed"] = note7
                item["status"] = "A"
        if item["number"] == 17:
            parts = [note17_text(current_rows), note17_open_text(company)]
            note17 = " · ".join(part for part in parts if part)
            if note17:
                item["computed"] = note17
                item["status"] = "A"
        if item["number"] == 11:
            parts = [item.get("computed") or "", note11_open_text(company), note11_cash_text(company)]
            note11 = " · ".join(part for part in parts if part)
            if note11:
                item["computed"] = note11
                item["status"] = "A"
        if item["number"] == 36:
            note36 = note36_text(company)
            if note36:
                item["computed"] = note36
                item["status"] = "A"
        if item["number"] == 35:
            year = exercise.year if exercise else period.year
            note35 = note35_text(company, year, payroll=payroll_from_rows(pnl_rows))
            if note35:
                item["computed"] = note35
                item["status"] = "A"

    starts_on = exercise.starts_on if exercise else period.starts_on
    ends_on = exercise.ends_on if exercise else period.ends_on
    due_close = ends_on
    return {
        "regime": company.accounting_regime,
        "exercise_year": period.year,
        "period_id": str(period.id),
        "period_label": f"{period.year}-{period.month:02d}",
        "comparative_year": period.year - 1 if prior_rows else None,
        "going_concern": company.going_concern,
        "closed_on": exercise.closed_on.isoformat() if exercise and exercise.closed_on else None,
        "approved_on": exercise.approved_on.isoformat() if exercise and exercise.approved_on else None,
        "arrete_due_on": _add_months(due_close, 4).isoformat(),
        "ago_due_on": _add_months(due_close, 6).isoformat(),
        "notes_annexes": exercise.notes_annexes if exercise else "",
        "entity": {
            "name": company.name,
            "legal_name": company.legal_name or company.name,
            "country_code": company.country_code,
            "currency_code": company.currency_code,
            "regime": company.accounting_regime,
            "regime_label": _REGIME.get(company.accounting_regime, company.accounting_regime),
            "activity_kind": company.activity_kind,
            "activity_label": _ACTIVITY.get(company.activity_kind, company.activity_kind),
            "starts_on": starts_on.isoformat(),
            "ends_on": ends_on.isoformat(),
            "duration_months": _duration_months(starts_on, ends_on),
            **identity_payload(company),
        },
        "analysis": analysis,
        "notes": notes,
        "bilan": bilan,
        "result": result,
        "tft": tft,
        "smt": eligibility,
    }


def _add_months(origin: date, months: int) -> date:
    year = origin.year + (origin.month - 1 + months) // 12
    month = (origin.month - 1 + months) % 12 + 1
    day = min(origin.day, monthrange(year, month)[1])
    return date(year, month, day)
