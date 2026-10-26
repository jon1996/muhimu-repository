"""États consolidés / combinés SYSCOHADA (AUDCIF art. 5).

Agrège les liasses SN des sociétés du périmètre, applique le pourcentage
d’intérêt, les intérêts minoritaires (intégration globale) et les
éliminations manuelles sur les postes officiels. La mise en équivalence
reste hors agrégation v1 (avertissement).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from ninja.errors import HttpError

from apps.ledger.models import (
    AccountingPeriod,
    ConsolidationElimination,
    ConsolidationGroup,
    ConsolidationKind,
    ConsolidationMember,
    ConsolidationMethod,
    EliminationKind,
    Exercise,
)
from apps.ledger.money import parse_amount, quantize_amount
from apps.ledger.services.fx import get_rate, normalize_currency
from apps.ledger.services.pdf_statements import pdf_filename, render_statements_pdf
from apps.ledger.services.sn_map import _ACTIF_LAYOUT, _CR_LAYOUT, _PASSIF_LAYOUT
from apps.ledger.services.statements import _add_months, build_statements
from apps.tenancy.middleware import companies_queryset_for, user_can_access_company
from apps.tenancy.models import Company, Membership

ZERO = Decimal("0")
HUNDRED = Decimal("100")
EQUITY_CODES = frozenset({"CA", "CB", "CD", "CE", "CF", "CG", "CH", "CJ", "CL", "CM"})
BILAN_TOTALS = frozenset({"AD", "AI", "AQ", "AZ", "BG", "BK", "BT", "BZ", "CP", "DD", "DF", "DP", "DT", "DZ"})
CR_TOTALS = frozenset({"XA", "XB", "XC", "XD", "XE", "XF", "XG", "XH", "XI"})
TFT_TOTALS = frozenset({"ZB", "ZC", "ZD", "ZE", "ZF", "ZG", "ZH"})
METHODS = {choice.value for choice in ConsolidationMethod}
KINDS = {choice.value for choice in ConsolidationKind}
ELIM_KINDS = {choice.value for choice in EliminationKind}


def _d(value) -> Decimal:
    if value in (None, ""):
        return ZERO
    return Decimal(str(value))


def _fmt(value: Decimal, currency: str) -> str:
    return format(quantize_amount(value, currency), "f")


def _line(value: dict, key: str) -> Decimal:
    return _d(value.get(key))


def _set_amount(line: dict, key: str, value: Decimal, currency: str) -> None:
    line[key] = _fmt(value, currency)


def _add_amounts(target: dict, source: dict, currency: str) -> None:
    for key in ("current", "prior", "gross", "amort"):
        if source.get(key) is None and target.get(key) is None:
            continue
        target[key] = _fmt(_line(target, key) + _line(source, key), currency)


def _scale_line(line: dict, factor: Decimal, currency: str) -> dict:
    out = dict(line)
    for key in ("current", "prior", "gross", "amort"):
        if line.get(key) is None:
            continue
        out[key] = _fmt(_line(line, key) * factor, currency)
    return out


def _index_lines(lines: list[dict]) -> dict[str, dict]:
    return {str(line.get("code") or ""): dict(line) for line in lines if line.get("code")}


def _ordered(layout: tuple, bucket: dict[str, dict], currency: str) -> list[dict]:
    out = []
    for code, label, kind in layout:
        line = bucket.get(code) or {
            "code": code,
            "label": label,
            "current": _fmt(ZERO, currency),
            "prior": _fmt(ZERO, currency),
            "bold": kind in {"heading", "total", "sig"},
            "kind": kind,
        }
        line["label"] = line.get("label") or label
        line["kind"] = line.get("kind") or kind
        line["bold"] = kind in {"heading", "total", "sig"}
        if kind in {"heading", "total"} and line.get("gross") is None and code in {
            "AD",
            "AI",
            "AQ",
            "AZ",
            "BG",
            "BK",
            "BT",
            "BZ",
        }:
            line["gross"] = line.get("gross") or _fmt(ZERO, currency)
            line["amort"] = line.get("amort") or _fmt(ZERO, currency)
        out.append(line)
    return out


def _sum_codes(bucket: dict[str, dict], codes: tuple[str, ...], key: str = "current") -> Decimal:
    return sum((_line(bucket.get(code) or {}, key) for code in codes), ZERO)


def _recompute_bilan(actif: dict[str, dict], passif: dict[str, dict], currency: str) -> None:
    def put(bucket: dict[str, dict], code: str, parts: tuple[str, ...]) -> None:
        line = bucket.get(code)
        if not line:
            return
        _set_amount(line, "current", _sum_codes(bucket, parts), currency)
        _set_amount(line, "prior", _sum_codes(bucket, parts, "prior"), currency)
        if line.get("gross") is not None:
            _set_amount(line, "gross", _sum_codes(bucket, parts, "gross"), currency)
            _set_amount(line, "amort", _sum_codes(bucket, parts, "amort"), currency)

    put(actif, "AD", ("AE", "AF", "AG", "AH"))
    put(actif, "AI", ("AJ", "AK", "AL", "AM", "AN", "AP"))
    put(actif, "AQ", ("AR", "AS"))
    put(actif, "AZ", ("AD", "AI", "AQ"))
    put(actif, "BG", ("BH", "BI", "BJ"))
    put(actif, "BK", ("BA", "BB", "BG"))
    put(actif, "BT", ("BQ", "BR", "BS"))
    put(actif, "BZ", ("AZ", "BK", "BT", "BU"))
    put(passif, "CP", ("CA", "CB", "CD", "CE", "CF", "CG", "CH", "CJ", "CL", "CM"))
    put(passif, "DD", ("DA", "DB", "DC"))
    df = _sum_codes(passif, ("CP", "CN", "DD")) if "CN" in passif else _sum_codes(passif, ("CP", "DD"))
    if passif.get("DF"):
        _set_amount(passif["DF"], "current", df, currency)
        prior_df = (
            _sum_codes(passif, ("CP", "CN", "DD"), "prior")
            if "CN" in passif
            else _sum_codes(passif, ("CP", "DD"), "prior")
        )
        _set_amount(passif["DF"], "prior", prior_df, currency)
    put(passif, "DP", ("DH", "DI", "DJ", "DK", "DM", "DN"))
    put(passif, "DT", ("DQ", "DR"))
    put(passif, "DZ", ("DF", "DP", "DT", "DV"))


def _recompute_cr(bucket: dict[str, dict], currency: str) -> None:
    def set_total(code: str, value: Decimal, prior: Decimal) -> None:
        line = bucket.get(code)
        if not line:
            return
        _set_amount(line, "current", value, currency)
        _set_amount(line, "prior", prior, currency)

    ta, ra, rb = _line(bucket.get("TA") or {}, "current"), _line(bucket.get("RA") or {}, "current"), _line(
        bucket.get("RB") or {}, "current"
    )
    set_total("XA", ta + ra + rb, _sum_codes(bucket, ("TA", "RA", "RB"), "prior"))
    xb = _sum_codes(bucket, ("TA", "TB", "TC", "TD"))
    set_total("XB", xb, _sum_codes(bucket, ("TA", "TB", "TC", "TD"), "prior"))
    xc_parts = ("XB", "RA", "RB", "TE", "TF", "TG", "TH", "TI", "RC", "RD", "RE", "RF", "RG", "RH", "RI", "RJ")
    set_total("XC", _sum_codes(bucket, xc_parts), _sum_codes(bucket, xc_parts, "prior"))
    set_total("XD", _sum_codes(bucket, ("XC", "RK")), _sum_codes(bucket, ("XC", "RK"), "prior"))
    set_total("XE", _sum_codes(bucket, ("XD", "TJ", "RL")), _sum_codes(bucket, ("XD", "TJ", "RL"), "prior"))
    xf_parts = ("TK", "TL", "TM", "RM", "RN")
    set_total("XF", _sum_codes(bucket, xf_parts), _sum_codes(bucket, xf_parts, "prior"))
    set_total("XG", _sum_codes(bucket, ("XE", "XF")), _sum_codes(bucket, ("XE", "XF"), "prior"))
    set_total("XH", _sum_codes(bucket, ("TN", "TO", "RO", "RP")), _sum_codes(bucket, ("TN", "TO", "RO", "RP"), "prior"))
    set_total("XI", _sum_codes(bucket, ("XG", "XH", "RQ", "RS")), _sum_codes(bucket, ("XG", "XH", "RQ", "RS"), "prior"))
    xd = bucket.get("XD")
    if xd and _line(xd, "current") < 0:
        xd["label"] = "Insuffisance brute d’exploitation"
    elif xd:
        xd["label"] = "Excédent brut d’exploitation"


def _recompute_tft(bucket: dict[str, dict], currency: str) -> None:
    def set_total(code: str, parts: tuple[str, ...]) -> None:
        line = bucket.get(code)
        if not line:
            return
        _set_amount(line, "current", _sum_codes(bucket, parts), currency)
        _set_amount(line, "prior", _sum_codes(bucket, parts, "prior"), currency)

    set_total("ZB", ("FA", "FB", "FC", "FD", "FE"))
    set_total("ZC", ("FF", "FG", "FH", "FI", "FJ"))
    set_total("ZD", ("FK", "FL", "FM", "FN"))
    set_total("ZE", ("FO", "FP", "FQ"))
    set_total("ZF", ("ZD", "ZE"))
    set_total("ZG", ("ZB", "ZC", "ZF"))
    set_total("ZH", ("ZG", "ZA"))


def _pct(raw) -> Decimal:
    try:
        value = Decimal(str(raw if raw not in (None, "") else "100").replace(",", ".").strip())
    except Exception as exc:
        raise HttpError(400, "Pourcentage d’intérêt invalide.") from exc
    if value < ZERO or value > HUNDRED:
        raise HttpError(400, "Pourcentage d’intérêt entre 0 et 100.")
    return value.quantize(Decimal("0.0001"))


def _ensure_layout(bucket: dict[str, dict], layout: tuple, currency: str, *, with_gross: bool = False) -> None:
    for code, label, kind in layout:
        if code in bucket:
            continue
        line = {
            "code": code,
            "label": label,
            "current": _fmt(ZERO, currency),
            "prior": _fmt(ZERO, currency),
            "bold": kind in {"heading", "total", "sig"},
            "kind": kind,
        }
        if with_gross:
            line["gross"] = _fmt(ZERO, currency)
            line["amort"] = _fmt(ZERO, currency)
        bucket[code] = line


def _factor(member: ConsolidationMember, code: str) -> Decimal:
    pct = member.ownership_pct or HUNDRED
    if pct < ZERO or pct > HUNDRED:
        raise HttpError(400, "Pourcentage d’intérêt entre 0 et 100.")
    share = pct / HUNDRED
    if member.method == ConsolidationMethod.PROPORTIONAL:
        return share
    if member.method == ConsolidationMethod.FULL and not member.is_parent and code in EQUITY_CODES:
        return share
    return Decimal("1")


def _period_for_year(company: Company, year: int) -> AccountingPeriod | None:
    exercise = Exercise.objects.filter(company=company, year=year).first()
    if not exercise:
        return None
    last_day = date(year, 12, monthrange(year, 12)[1])
    return (
        exercise.periods.filter(ends_on__lte=last_day).order_by("-ends_on").first()
        or exercise.periods.order_by("-starts_on").first()
    )


def _rate_company(group: ConsolidationGroup) -> Company | None:
    if group.parent_id:
        return group.parent
    member = group.members.filter(is_active=True).select_related("company").first()
    return member.company if member else None


def _fx_factor(group: ConsolidationGroup, company: Company, on: date) -> Decimal:
    target = normalize_currency(group.currency_code)
    source = normalize_currency(company.currency_code)
    if source == target:
        return Decimal("1")
    host = _rate_company(group)
    if not host:
        raise HttpError(400, f"Cours {source}/{target} : aucune société de référence.")
    return get_rate(host, source, on)


def _member_payload(member: ConsolidationMember, year: int, group: ConsolidationGroup) -> tuple[dict | None, str]:
    if member.method == ConsolidationMethod.EQUITY:
        return None, "Mise en équivalence hors agrégation v1."
    company = member.company
    if company.accounting_regime == "smt":
        return None, "Régime SMT exclu du consolidé SN."
    period = _period_for_year(company, year)
    if not period:
        return None, f"Exercice {year} introuvable."
    try:
        payload = build_statements(company, period)
    except ValueError as exc:
        return None, str(exc)
    on = period.ends_on
    try:
        rate = _fx_factor(group, company, on)
    except HttpError as exc:
        return None, str(exc)
    if rate != 1:
        for block in (payload["bilan"]["actif"], payload["bilan"]["passif"], payload["result"]["lines"], payload["tft"]["lines"]):
            for line in block:
                scaled = _scale_line(line, rate, group.currency_code)
                line.update(scaled)
        payload["result"]["net"] = _fmt(_d(payload["result"]["net"]) * rate, group.currency_code)
    payload["_period"] = period
    payload["_rate"] = rate
    return payload, ""


def _apply_elim(bucket: dict[str, dict], code: str, amount: Decimal, currency: str) -> bool:
    line = bucket.get(code)
    if not line:
        return False
    _set_amount(line, "current", _line(line, "current") - amount, currency)
    return True


def _statements_from_buckets(
    group: ConsolidationGroup,
    actif: dict[str, dict],
    passif: dict[str, dict],
    result: dict[str, dict],
    tft: dict[str, dict],
    notes: list[dict],
    period_label: str,
    ends_on: date,
) -> dict:
    currency = group.currency_code
    _ensure_layout(actif, _ACTIF_LAYOUT, currency, with_gross=True)
    _ensure_layout(passif, _PASSIF_LAYOUT, currency)
    _ensure_layout(result, _CR_LAYOUT, currency)
    _recompute_bilan(actif, passif, currency)
    _recompute_cr(result, currency)
    _recompute_tft(tft, currency)
    actif_lines = _ordered(_ACTIF_LAYOUT, actif, currency)
    passif_lines = []
    for line in _ordered(_PASSIF_LAYOUT, passif, currency):
        passif_lines.append(line)
        if line["code"] == "CP" and passif.get("CN"):
            passif_lines.append(passif["CN"])
    cr_lines = _ordered(_CR_LAYOUT, result, currency)
    tft_lines = list(tft.values()) if not tft else []
    if tft:
        order = (
            "ZA",
            "FA",
            "FB",
            "FC",
            "FD",
            "FE",
            "ZB",
            "FF",
            "FG",
            "FH",
            "FI",
            "FJ",
            "ZC",
            "FK",
            "FL",
            "FM",
            "FN",
            "ZD",
            "FO",
            "FP",
            "FQ",
            "ZE",
            "ZF",
            "ZG",
            "ZH",
        )
        tft_lines = [tft[code] for code in order if code in tft]
    bz = _line(actif.get("BZ") or {}, "current")
    dz = _line(passif.get("DZ") or {}, "current")
    kind_label = "États consolidés" if group.kind == ConsolidationKind.CONSOLIDATED else "États combinés"
    return {
        "regime": "normal",
        "scope": group.kind,
        "exercise_year": group.year,
        "period_id": "",
        "period_label": period_label,
        "comparative_year": group.year - 1,
        "going_concern": True,
        "closed_on": None,
        "approved_on": None,
        "arrete_due_on": _add_months(ends_on, 4).isoformat(),
        "ago_due_on": _add_months(ends_on, 6).isoformat(),
        "notes_annexes": group.notes,
        "entity": {
            "name": group.name,
            "legal_name": group.name,
            "country_code": group.parent.country_code if group.parent_id else "",
            "currency_code": currency,
            "regime": "normal",
            "regime_label": kind_label,
            "activity_kind": "",
            "activity_label": "",
            "starts_on": date(group.year, 1, 1).isoformat(),
            "ends_on": ends_on.isoformat(),
            "duration_months": 12,
        },
        "analysis": None,
        "notes": notes,
        "bilan": {
            "actif": actif_lines,
            "passif": passif_lines,
            "balanced": bz == dz,
        },
        "result": {"lines": cr_lines, "net": _fmt(_line(result.get("XI") or {}, "current"), currency)},
        "tft": {"lines": tft_lines},
        "smt": None,
    }


def serialize_member(member: ConsolidationMember) -> dict:
    return {
        "id": str(member.id),
        "company_id": str(member.company_id),
        "company_name": member.company.name,
        "currency_code": member.company.currency_code,
        "method": member.method,
        "ownership_pct": format(member.ownership_pct.normalize(), "f"),
        "is_parent": member.is_parent,
        "is_active": member.is_active,
    }


def serialize_elimination(item: ConsolidationElimination) -> dict:
    return {
        "id": str(item.id),
        "code": item.code,
        "label": item.label,
        "amount": format(item.amount, "f"),
        "kind": item.kind,
    }


def serialize_group(group: ConsolidationGroup) -> dict:
    members = list(group.members.select_related("company").all())
    elims = list(group.eliminations.all())
    return {
        "id": str(group.id),
        "name": group.name,
        "kind": group.kind,
        "year": group.year,
        "currency_code": group.currency_code,
        "parent_id": str(group.parent_id) if group.parent_id else None,
        "parent_name": group.parent.name if group.parent_id else "",
        "notes": group.notes,
        "members": [serialize_member(item) for item in members],
        "eliminations": [serialize_elimination(item) for item in elims],
    }


def _notes(group: ConsolidationGroup, summaries: list[dict], minorities: Decimal, warnings: list[str]) -> list[dict]:
    methods = ", ".join(
        f"{row['company_name']} {row['method']} {row['ownership_pct']} %"
        for row in summaries
        if row.get("included")
    )
    body = group.notes.strip()
    computed = (
        f"Périmètre {group.get_kind_display()} {group.year} · {group.currency_code}. "
        f"{methods or 'aucune société agrégée'}."
    )
    if minorities:
        computed += f" Intérêts minoritaires {format(minorities, 'f')}."
    if warnings:
        computed += " " + " ".join(warnings)
    return [
        {
            "number": 1,
            "title": "Périmètre de consolidation / combinaison",
            "status": "A",
            "required": True,
            "body": body,
            "conformity": "",
            "methods": "",
            "derogations": "",
            "extra": "",
            "computed": computed,
        },
        {
            "number": 2,
            "title": "Méthodes et éliminations",
            "status": "A",
            "required": True,
            "body": "",
            "conformity": "",
            "methods": "Intégration globale, proportionnelle ou combinaison. Mise en équivalence hors v1.",
            "derogations": "",
            "extra": "",
            "computed": f"{len(group.eliminations.all())} élimination(s) manuelle(s) sur postes SN.",
        },
    ]


def build_consolidated(group: ConsolidationGroup) -> dict:
    if group.kind == ConsolidationKind.CONSOLIDATED and not group.parent_id:
        raise HttpError(400, "Une société mère est requise pour un périmètre consolidé.")
    members = list(group.members.filter(is_active=True).select_related("company"))
    if not members:
        panel = serialize_group(group)
        panel.update(
            {
                "warnings": ["Ajoutez au moins une société au périmètre."],
                "minorities": _fmt(ZERO, group.currency_code),
                "summaries": [],
                "statements": None,
            }
        )
        return panel
    actif: dict[str, dict] = {}
    passif: dict[str, dict] = {}
    result: dict[str, dict] = {}
    tft: dict[str, dict] = {}
    warnings: list[str] = []
    summaries: list[dict] = []
    minorities = ZERO
    ends_on = date(group.year, 12, 31)
    period_label = str(group.year)
    currency = group.currency_code

    for member in members:
        payload, warning = _member_payload(member, group.year, group)
        row = {
            **serialize_member(member),
            "included": payload is not None,
            "warning": warning,
            "period_label": "",
            "sales": "0",
            "net": "0",
            "total_actif": "0",
        }
        if warning:
            warnings.append(f"{member.company.name} : {warning}")
        if not payload:
            summaries.append(row)
            continue
        period = payload["_period"]
        ends_on = max(ends_on, period.ends_on)
        period_label = f"{period.year}-{period.month:02d}"
        row["period_label"] = period_label
        cr = _index_lines(payload["result"]["lines"])
        act = _index_lines(payload["bilan"]["actif"])
        pas = _index_lines(payload["bilan"]["passif"])
        row["sales"] = cr.get("XB", {}).get("current") or cr.get("TA", {}).get("current") or "0"
        row["net"] = payload["result"]["net"]
        row["total_actif"] = act.get("BZ", {}).get("current") or "0"
        summaries.append(row)

        if (
            group.kind == ConsolidationKind.CONSOLIDATED
            and member.method == ConsolidationMethod.FULL
            and not member.is_parent
        ):
            share = (HUNDRED - (member.ownership_pct or HUNDRED)) / HUNDRED
            minorities += _line(pas.get("CP") or {}, "current") * share

        for source, dest, skip in (
            (act, actif, BILAN_TOTALS),
            (pas, passif, BILAN_TOTALS),
            (cr, result, CR_TOTALS),
            (_index_lines(payload["tft"]["lines"]), tft, TFT_TOTALS),
        ):
            for code, line in source.items():
                if code in skip or not code:
                    continue
                scaled = _scale_line(line, _factor(member, code), currency)
                if code not in dest:
                    dest[code] = scaled
                else:
                    _add_amounts(dest[code], scaled, currency)

    for item in group.eliminations.all():
        applied = (
            _apply_elim(actif, item.code, item.amount, currency)
            or _apply_elim(passif, item.code, item.amount, currency)
            or _apply_elim(result, item.code, item.amount, currency)
            or _apply_elim(tft, item.code, item.amount, currency)
        )
        if not applied:
            warnings.append(f"Élimination {item.code} : poste absent de la liasse.")

    if minorities and group.kind == ConsolidationKind.CONSOLIDATED:
        passif["CN"] = {
            "code": "CN",
            "label": "Intérêts minoritaires",
            "current": _fmt(minorities, currency),
            "prior": _fmt(ZERO, currency),
            "bold": False,
            "kind": "detail",
        }

    notes = _notes(group, summaries, minorities, warnings)
    statements = _statements_from_buckets(
        group, actif, passif, result, tft, notes, period_label, ends_on
    )
    panel = serialize_group(group)
    panel.update(
        {
            "warnings": warnings,
            "minorities": _fmt(minorities, currency),
            "summaries": summaries,
            "statements": statements,
        }
    )
    return panel


def _get_group(organization, group_id: str) -> ConsolidationGroup:
    group = (
        ConsolidationGroup.objects.filter(organization=organization, id=group_id)
        .select_related("parent")
        .prefetch_related("members")
        .first()
    )
    if not group:
        raise HttpError(404, "Périmètre introuvable.")
    return group


def _get_company(organization, company_id: str) -> Company:
    company = Company.objects.filter(organization=organization, id=company_id, is_active=True).first()
    if not company:
        raise HttpError(404, "Société introuvable dans l’organisation.")
    return company


def group_company_ids(group: ConsolidationGroup) -> set:
    ids = {row for row in group.members.values_list("company_id", flat=True)}
    if group.parent_id:
        ids.add(group.parent_id)
    return ids


def accessible_company_ids(user, membership: Membership) -> set:
    return set(companies_queryset_for(user, membership).values_list("id", flat=True))


def user_can_access_group(user, membership: Membership, group: ConsolidationGroup) -> bool:
    """Tous les membres du périmètre doivent être dans le périmètre sociétés autorisé."""
    companies = group_company_ids(group)
    if not companies:
        return True
    return companies <= accessible_company_ids(user, membership)


def assert_group_access(user, membership: Membership, group: ConsolidationGroup) -> None:
    if not user_can_access_group(user, membership, group):
        raise HttpError(
            403,
            "Périmètre consolidé hors de vos sociétés autorisées.",
        )


def assert_company_access(user, membership: Membership, company: Company) -> None:
    if not user_can_access_company(user, membership, company):
        raise HttpError(403, "Société non autorisée pour votre compte.")


def create_group(organization, payload: dict, *, user=None, membership: Membership | None = None) -> dict:
    name = (payload.get("name") or "").strip()
    if not name:
        raise HttpError(400, "Intitulé du périmètre requis.")
    kind = (payload.get("kind") or ConsolidationKind.CONSOLIDATED).strip()
    if kind not in KINDS:
        raise HttpError(400, "Type invalide (consolidated ou combined).")
    year = int(payload.get("year") or date.today().year)
    currency = normalize_currency(payload.get("currency_code") or "XOF")
    parent = None
    parent_id = payload.get("parent_id") or ""
    if parent_id:
        parent = _get_company(organization, parent_id)
        if user is not None and membership is not None:
            assert_company_access(user, membership, parent)
        currency = normalize_currency(parent.currency_code or currency)
    if kind == ConsolidationKind.CONSOLIDATED and not parent:
        raise HttpError(400, "Société mère requise pour un consolidé.")
    if ConsolidationGroup.objects.filter(organization=organization, name=name, year=year).exists():
        raise HttpError(400, "Un périmètre porte déjà ce nom sur l’exercice.")
    group = ConsolidationGroup.objects.create(
        organization=organization,
        name=name,
        kind=kind,
        year=year,
        currency_code=currency,
        parent=parent,
        notes=(payload.get("notes") or "").strip(),
    )
    if parent:
        ConsolidationMember.objects.create(
            organization=organization,
            group=group,
            company=parent,
            method=ConsolidationMethod.FULL,
            ownership_pct=HUNDRED,
            is_parent=True,
        )
    return build_consolidated(group)


def update_group(
    organization,
    group_id: str,
    payload: dict,
    *,
    user=None,
    membership: Membership | None = None,
) -> dict:
    group = _get_group(organization, group_id)
    if user is not None and membership is not None:
        assert_group_access(user, membership, group)
    if payload.get("name"):
        group.name = payload["name"].strip()
    if payload.get("notes") is not None:
        group.notes = payload["notes"].strip()
    if payload.get("currency_code"):
        group.currency_code = normalize_currency(payload["currency_code"])
    if payload.get("kind"):
        kind = payload["kind"].strip()
        if kind not in KINDS:
            raise HttpError(400, "Type invalide (consolidated ou combined).")
        group.kind = kind
    if payload.get("year"):
        group.year = int(payload["year"])
    if "parent_id" in payload:
        parent_id = payload.get("parent_id") or ""
        group.parent = _get_company(organization, parent_id) if parent_id else None
    if group.kind == ConsolidationKind.CONSOLIDATED and not group.parent_id:
        raise HttpError(400, "Société mère requise pour un consolidé.")
    group.save()
    return build_consolidated(group)


def add_member(
    organization,
    group_id: str,
    payload: dict,
    *,
    user=None,
    membership: Membership | None = None,
) -> dict:
    group = _get_group(organization, group_id)
    if user is not None and membership is not None:
        assert_group_access(user, membership, group)
    company = _get_company(organization, payload.get("company_id") or "")
    if user is not None and membership is not None:
        assert_company_access(user, membership, company)
    method = (payload.get("method") or (
        ConsolidationMethod.COMBINED if group.kind == ConsolidationKind.COMBINED else ConsolidationMethod.FULL
    )).strip()
    if method not in METHODS:
        raise HttpError(400, "Méthode invalide.")
    pct = _pct(payload.get("ownership_pct"))
    is_parent = bool(payload.get("is_parent")) or (group.parent_id == company.id)
    if group.members.filter(company=company).exists():
        raise HttpError(400, "Cette société est déjà dans le périmètre.")
    if is_parent:
        group.members.filter(is_parent=True).update(is_parent=False)
        group.parent = company
        group.save(update_fields=["parent"])
    ConsolidationMember.objects.create(
        organization=organization,
        group=group,
        company=company,
        method=method,
        ownership_pct=pct,
        is_parent=is_parent,
        is_active=payload.get("is_active", True),
    )
    return build_consolidated(group)


def update_member(organization, group_id: str, member_id: str, payload: dict) -> dict:
    group = _get_group(organization, group_id)
    member = group.members.filter(id=member_id).first()
    if not member:
        raise HttpError(404, "Société du périmètre introuvable.")
    if payload.get("method"):
        method = payload["method"].strip()
        if method not in METHODS:
            raise HttpError(400, "Méthode invalide.")
        member.method = method
    if payload.get("ownership_pct") is not None:
        member.ownership_pct = _pct(payload["ownership_pct"])
    if payload.get("is_active") is not None:
        member.is_active = bool(payload["is_active"])
    if payload.get("is_parent"):
        group.members.filter(is_parent=True).update(is_parent=False)
        member.is_parent = True
        group.parent = member.company
        group.save(update_fields=["parent"])
    member.save()
    return build_consolidated(group)


def remove_member(organization, group_id: str, member_id: str) -> dict:
    group = _get_group(organization, group_id)
    member = group.members.filter(id=member_id).first()
    if not member:
        raise HttpError(404, "Société du périmètre introuvable.")
    if member.is_parent and group.kind == ConsolidationKind.CONSOLIDATED:
        raise HttpError(400, "Impossible de retirer la société mère d’un consolidé.")
    member.delete()
    return build_consolidated(group)


def add_elimination(organization, group_id: str, payload: dict) -> dict:
    group = _get_group(organization, group_id)
    code = (payload.get("code") or "").strip().upper()
    if not code:
        raise HttpError(400, "Code de poste SN requis (ex. TA, BI, DJ).")
    kind = (payload.get("kind") or EliminationKind.OTHER).strip()
    if kind not in ELIM_KINDS:
        raise HttpError(400, "Nature d’élimination invalide.")
    try:
        amount = parse_amount(payload.get("amount") or "0", group.currency_code)
    except Exception as exc:
        raise HttpError(400, "Montant d’élimination invalide.") from exc
    if amount == ZERO:
        raise HttpError(400, "Montant d’élimination requis.")
    ConsolidationElimination.objects.create(
        organization=organization,
        group=group,
        code=code,
        label=(payload.get("label") or code).strip(),
        amount=amount,
        kind=kind,
    )
    return build_consolidated(group)


def remove_elimination(organization, group_id: str, elimination_id: str) -> dict:
    group = _get_group(organization, group_id)
    item = group.eliminations.filter(id=elimination_id).first()
    if not item:
        raise HttpError(404, "Élimination introuvable.")
    item.delete()
    return build_consolidated(group)


def list_groups(organization, *, user=None, membership: Membership | None = None) -> list[dict]:
    groups = (
        ConsolidationGroup.objects.filter(organization=organization)
        .select_related("parent")
        .prefetch_related("members")
    )
    out = []
    for group in groups:
        if user is not None and membership is not None and not user_can_access_group(user, membership, group):
            continue
        out.append(serialize_group(group))
    return out


def group_panel(organization, group_id: str, *, user=None, membership: Membership | None = None) -> dict:
    group = _get_group(organization, group_id)
    if user is not None and membership is not None:
        assert_group_access(user, membership, group)
    return build_consolidated(group)


def group_pdf(
    organization,
    group_id: str,
    kind: str = "liasse",
    *,
    user=None,
    membership: Membership | None = None,
) -> tuple[bytes, str]:
    panel = group_panel(organization, group_id, user=user, membership=membership)
    payload = panel["statements"]
    if not payload:
        raise HttpError(400, "Aucune liasse à éditer : ajoutez des sociétés au périmètre.")
    pdf = render_statements_pdf(payload, kind)
    name = pdf_filename(payload, kind)
    return pdf, name
