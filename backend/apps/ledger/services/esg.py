"""Note 35 — informations sociales, environnementales et sociétales (Titre IX)."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from ninja.errors import HttpError

from apps.ledger.models import EsgReport

ZERO = Decimal("0")

# Titre IX (catalogue des notes). Le ch. 30 de l’acte cite 500.
NOTE35_HEADCOUNT = 250
CHAPTER30_HEADCOUNT = 500

SOCIAL_TEXT = (
    ("social_dialogue", "dialogue social"),
    ("health", "santé"),
    ("training", "formation"),
    ("equality", "égalité"),
)
ENV_TEXT = (
    ("env_policy", "politique environnementale"),
    ("waste", "déchets"),
    ("water", "eau"),
    ("energy", "énergie"),
    ("ghg", "GES"),
    ("biodiversity", "biodiversité"),
)
SOCIETAL_TEXT = (
    ("territory", "territoire"),
    ("neighbors", "riverains"),
    ("patronage", "mécénat"),
    ("purchases", "achats"),
)

TEXT_FIELDS = tuple(key for key, _ in (*SOCIAL_TEXT, *ENV_TEXT, *SOCIETAL_TEXT))


def note35_required(headcount: int) -> bool:
    return int(headcount or 0) > NOTE35_HEADCOUNT


def payroll_from_rows(rows: list[dict]) -> Decimal:
    total = ZERO
    for row in rows:
        code = row.get("code") or ""
        if str(code).startswith("66"):
            total += (row.get("close_debit") or ZERO) - (row.get("close_credit") or ZERO)
    return total


def _int(raw, name: str) -> int:
    if raw in (None, ""):
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise HttpError(400, f"{name} invalide.") from exc
    if value < 0:
        raise HttpError(400, f"{name} ne peut pas être négatif.")
    return value


def empty_payload(year: int, payroll: Decimal | None = None) -> dict:
    data = {
        "id": "",
        "year": year,
        "headcount": 0,
        "hires": 0,
        "dismissals": 0,
        "disabled_count": 0,
    }
    for key in TEXT_FIELDS:
        data[key] = ""
    return serialize_payload(data, payroll=payroll)


def serialize_payload(item: dict, payroll: Decimal | None = None) -> dict:
    headcount = int(item.get("headcount") or 0)
    return {
        "id": str(item.get("id") or ""),
        "year": int(item.get("year") or 0),
        "headcount": headcount,
        "hires": int(item.get("hires") or 0),
        "dismissals": int(item.get("dismissals") or 0),
        "disabled_count": int(item.get("disabled_count") or 0),
        **{key: item.get(key) or "" for key in TEXT_FIELDS},
        "required": note35_required(headcount),
        "threshold": NOTE35_HEADCOUNT,
        "chapter30_threshold": CHAPTER30_HEADCOUNT,
        "payroll": format(payroll, "f") if payroll else "",
        "note_preview": note35_from_item(item, payroll=payroll),
    }


def serialize_report(report: EsgReport, payroll: Decimal | None = None) -> dict:
    return serialize_payload(
        {
            "id": str(report.id),
            "year": report.year,
            "headcount": report.headcount,
            "hires": report.hires,
            "dismissals": report.dismissals,
            "disabled_count": report.disabled_count,
            **{key: getattr(report, key) for key in TEXT_FIELDS},
        },
        payroll=payroll,
    )


def note35_from_item(item: dict, payroll: Decimal | None = None) -> str:
    parts: list[str] = []
    headcount = int(item.get("headcount") or 0)
    hires = int(item.get("hires") or 0)
    dismissals = int(item.get("dismissals") or 0)
    disabled = int(item.get("disabled_count") or 0)
    filled = False

    social: list[str] = []
    if headcount:
        social.append(f"effectif {headcount}")
        filled = True
    if hires:
        social.append(f"embauches {hires}")
        filled = True
    if dismissals:
        social.append(f"licenciements {dismissals}")
        filled = True
    if disabled:
        social.append(f"handicap {disabled}")
        filled = True
    if payroll:
        social.append(f"masse salariale {payroll}")
        filled = True
    for key, label in SOCIAL_TEXT:
        value = (item.get(key) or "").strip()
        if value:
            social.append(f"{label} : {value}")
            filled = True
    if social:
        parts.append("Social : " + " · ".join(social))

    env = []
    for key, label in ENV_TEXT:
        value = (item.get(key) or "").strip()
        if value:
            env.append(f"{label} : {value}")
            filled = True
    if env:
        parts.append("Environnement : " + " · ".join(env))

    societal = []
    for key, label in SOCIETAL_TEXT:
        value = (item.get(key) or "").strip()
        if value:
            societal.append(f"{label} : {value}")
            filled = True
    if societal:
        parts.append("Sociétal : " + " · ".join(societal))

    if note35_required(headcount):
        prefix = f"Obligatoire (effectif {headcount} > {NOTE35_HEADCOUNT})"
        detail = bool(hires or dismissals or disabled or payroll or env or societal)
        if not detail:
            detail = any((item.get(key) or "").strip() for key, _ in SOCIAL_TEXT)
        if detail:
            return prefix + " · " + " · ".join(parts)
        return prefix + " — fiche à compléter."
    if not filled:
        return ""
    return " · ".join(parts)


def get_report(company, year: int | None = None, payroll: Decimal | None = None) -> dict:
    year = year or timezone.localdate().year
    report = EsgReport.objects.filter(company=company, year=year).first()
    if report:
        return serialize_report(report, payroll=payroll)
    return empty_payload(year, payroll=payroll)


def upsert_report(company, payload: dict) -> EsgReport:
    year = _int(payload.get("year") or timezone.localdate().year, "Exercice")
    if year < 1900 or year > 2100:
        raise HttpError(400, "Exercice invalide.")
    defaults = {
        "organization": company.organization,
        "headcount": _int(payload.get("headcount"), "Effectif"),
        "hires": _int(payload.get("hires"), "Embauches"),
        "dismissals": _int(payload.get("dismissals"), "Licenciements"),
        "disabled_count": _int(payload.get("disabled_count"), "Travailleurs handicapés"),
        **{key: (payload.get(key) or "").strip() for key in TEXT_FIELDS},
    }
    report, _ = EsgReport.objects.update_or_create(
        company=company,
        year=year,
        defaults=defaults,
    )
    return report


def note35_text(company, year: int, payroll: Decimal | None = None) -> str:
    report = EsgReport.objects.filter(company=company, year=year).first()
    if not report:
        return ""
    return note35_from_item(
        {
            "headcount": report.headcount,
            "hires": report.hires,
            "dismissals": report.dismissals,
            "disabled_count": report.disabled_count,
            **{key: getattr(report, key) for key in TEXT_FIELDS},
        },
        payroll=payroll,
    )
