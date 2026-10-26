"""Amortissement linéaire SYSCOHADA — prorata temporis dès la mise en service (SN)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.ledger.money import quantize_amount

ZERO = Decimal("0")


def depreciable_base(cost: Decimal, residual: Decimal) -> Decimal:
    base = cost - residual
    return base if base > 0 else ZERO


def service_window(
    in_service_on: date,
    period_start: date,
    period_end: date,
    disposed_on: date | None,
) -> tuple[date, date] | None:
    start = max(in_service_on, period_start)
    end = period_end
    if disposed_on:
        last = disposed_on.toordinal() - 1
        if last < start.toordinal():
            return None
        end = min(end, date.fromordinal(last))
    if start > end:
        return None
    return start, end


def prorata_fraction(
    in_service_on: date,
    period_start: date,
    period_end: date,
    disposed_on: date | None = None,
) -> Decimal:
    window = service_window(in_service_on, period_start, period_end, disposed_on)
    if window is None:
        return ZERO
    start, end = window
    days_used = (end - start).days + 1
    days_period = (period_end - period_start).days + 1
    if days_period <= 0:
        return ZERO
    return Decimal(days_used) / Decimal(days_period)


def linear_charge(
    *,
    cost: Decimal,
    residual: Decimal,
    useful_life_months: int,
    in_service_on: date,
    period_start: date,
    period_end: date,
    already_charged: Decimal,
    currency: str = "XOF",
    disposed_on: date | None = None,
) -> Decimal:
    """Dotation de la période : (coût − résidu) / durée × prorata, plafonnée au reliquat."""
    if useful_life_months <= 0:
        return ZERO
    base = depreciable_base(cost, residual)
    remaining = base - already_charged
    if remaining <= 0:
        return ZERO
    fraction = prorata_fraction(in_service_on, period_start, period_end, disposed_on)
    if fraction <= 0:
        return ZERO
    monthly = base / Decimal(useful_life_months)
    charge = quantize_amount(monthly * fraction, currency)
    if charge > remaining:
        return quantize_amount(remaining, currency)
    return charge
