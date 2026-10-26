"""Tiers et lettrage — classe 4, notes 7 et 17."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import re

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import Account, EntryLine, EntryStatus, Exercise, ExerciseStatus, PartyKind, ThirdParty
from apps.ledger.services.assets import resolve_account
from apps.ledger.services.setup import find_parent_account

ZERO = Decimal("0")

KIND_LABELS = {
    PartyKind.CUSTOMER: "Client",
    PartyKind.SUPPLIER: "Fournisseur",
    PartyKind.BOTH: "Client et fournisseur",
}

DEFAULT_ACCOUNT = {
    PartyKind.CUSTOMER: "411",
    PartyKind.SUPPLIER: "401",
    PartyKind.BOTH: "411",
}


def next_reference(company, kind: str) -> str:
    prefix = "FOU" if kind == PartyKind.SUPPLIER else "CLI"
    last = (
        ThirdParty.objects.filter(company=company, reference__startswith=f"{prefix}-")
        .order_by("-reference")
        .values_list("reference", flat=True)
        .first()
    )
    number = 1
    if last:
        try:
            number = int(last.split("-")[-1]) + 1
        except ValueError:
            number = ThirdParty.objects.filter(company=company).count() + 1
    return f"{prefix}-{number:04d}"


def next_letter_code(existing: list[str]) -> str:
    highest = 0
    for code in existing:
        if not (code or "").startswith("L-"):
            continue
        try:
            highest = max(highest, int(code.split("-")[-1]))
        except ValueError:
            continue
    return f"L-{highest + 1:04d}"


def account_root(code: str) -> str:
    """411, 4118 et 411-CLI-0001 se lettrent ensemble (même collectif clients)."""
    code = (code or "").strip()
    if "-" in code:
        code = code.split("-", 1)[0]
    if "_" in code:
        code = code.split("_", 1)[0]
    return code[:3] if len(code) >= 3 else code


def is_subdivision(code: str) -> bool:
    cleaned = (code or "").strip()
    return "-" in cleaned or "_" in cleaned


def auxiliary_code(collective: str, reference: str, existing: set[str]) -> str:
    suffix = re.sub(r"[^A-Z0-9-]", "", (reference or "").upper()).strip("-")
    suffix = (suffix or "T")[:16]
    base = f"{collective}-{suffix}"
    if len(base) > 24:
        base = base[:24].rstrip("-")
    if base not in existing:
        return base
    number = 2
    while True:
        candidate = f"{base}-{number}"
        if len(candidate) > 24:
            candidate = f"{base[: 24 - len(str(number)) - 1]}-{number}"
        if candidate not in existing:
            return candidate
        number += 1


def bind_party_account(account: Account, party: ThirdParty | None) -> Account:
    """Imputer l’auxiliaire du tiers si le compte choisi est le même collectif."""
    if party is None or not party.account_id:
        return account
    aux = party.account
    if account_root(aux.code) == account_root(account.code):
        return aux
    return account


def ensure_party_auxiliary(company, *, kind: str, name: str, reference: str, base: Account) -> Account:
    if is_subdivision(base.code):
        taken = ThirdParty.objects.filter(company=company, account=base).exists()
        if taken:
            raise HttpError(409, f"Le compte {base.code} est déjà attribué à un tiers.")
        return base
    existing = set(Account.objects.filter(company=company).values_list("code", flat=True))
    code = auxiliary_code(base.code, reference, existing)
    parent = find_parent_account(company, code) or base
    account = Account(
        organization=company.organization,
        company=company,
        code=code,
        label=name,
        parent=parent,
        is_postable=True,
        is_syscohada=False,
        notes=f"Auxiliaire tiers {reference}",
    )
    account.save()
    return account


def parse_due_on(raw) -> date | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError) as exc:
        raise HttpError(400, "Échéance invalide.") from exc


def set_line_due(company, line_id: str, due_on) -> EntryLine:
    """Met à jour l’échéance (annotation ACC-02 whitelist) sur écriture validée."""
    line = (
        EntryLine.objects.filter(company=company, id=line_id)
        .select_related("account", "entry", "third_party")
        .first()
    )
    if line is None:
        raise HttpError(404, "Ligne introuvable.")
    parsed = parse_due_on(due_on)
    EntryLine.objects.filter(pk=line.pk).update(due_on=parsed)
    line.due_on = parsed
    return line


def line_net(line) -> Decimal:
    return (line.debit or ZERO) - (line.credit or ZERO)


def reference_date(company) -> date:
    today = date.today()
    exercise = Exercise.objects.filter(company=company, year=today.year).first()
    if exercise and exercise.status == ExerciseStatus.CLOSED:
        return exercise.ends_on
    return today


def classify_due(due: date | None, as_of: date) -> str:
    """Sans échéance saisie = cycle d’exploitation (≤ 1 an)."""
    if due is None:
        return "within_year"
    if due < as_of:
        return "overdue"
    if due <= as_of + timedelta(days=365):
        return "within_year"
    return "beyond_year"


def age_totals(lines, as_of: date) -> dict[str, Decimal]:
    buckets = {"overdue": ZERO, "within_year": ZERO, "beyond_year": ZERO}
    for line in lines:
        if isinstance(line, dict):
            due = line.get("due_on")
            net = abs((line.get("debit") or ZERO) - (line.get("credit") or ZERO))
        else:
            due = line.due_on
            net = abs(line_net(line))
        buckets[classify_due(due, as_of)] += net
    return buckets


def age_text(lines, as_of: date) -> str:
    buckets = age_totals(lines, as_of)
    parts = []
    if buckets["overdue"]:
        parts.append(f"échu {buckets['overdue']}")
    if buckets["within_year"]:
        parts.append(f"≤ 1 an {buckets['within_year']}")
    if buckets["beyond_year"]:
        parts.append(f"> 1 an {buckets['beyond_year']}")
    return " · ".join(parts)


def match_party(parties: list[ThirdParty], text: str) -> ThirdParty | None:
    haystack = (text or "").casefold()
    if not haystack:
        return None
    for party in parties:
        if party.reference and party.reference.casefold() in haystack:
            return party
        if party.name and party.name.casefold() in haystack:
            return party
    return None


def attach_inferred_parties(company, lines: list[EntryLine]) -> None:
    parties = list(ThirdParty.objects.filter(company=company, is_active=True))
    if not parties:
        return
    for line in lines:
        if line.third_party_id:
            continue
        found = match_party(parties, line.label)
        if not found:
            continue
        EntryLine.objects.filter(pk=line.pk).update(third_party_id=found.id)
        line.third_party = found
        line.third_party_id = found.id


def serialize_party(party: ThirdParty) -> dict:
    return {
        "id": str(party.id),
        "kind": party.kind,
        "kind_label": KIND_LABELS.get(party.kind, party.kind),
        "name": party.name,
        "reference": party.reference,
        "tax_id": party.tax_id,
        "account_id": str(party.account_id),
        "account_code": party.account.code,
        "is_active": party.is_active,
    }


def serialize_open_item(line: EntryLine, as_of: date | None = None) -> dict:
    as_of = as_of or reference_date(line.company)
    return {
        "id": str(line.id),
        "entry_id": str(line.entry_id),
        "entry_number": line.entry.number_display,
        "accounting_date": line.entry.accounting_date.isoformat(),
        "account_id": str(line.account_id),
        "account_code": line.account.code,
        "third_party_id": str(line.third_party_id) if line.third_party_id else None,
        "third_party_name": line.third_party.name if line.third_party_id else "",
        "label": line.label,
        "debit": format(line.debit, "f"),
        "credit": format(line.credit, "f"),
        "lettering": line.lettering,
        "due_on": line.due_on.isoformat() if line.due_on else "",
        "bucket": classify_due(line.due_on, as_of),
    }


def create_party(company, payload: dict) -> ThirdParty:
    kind = payload.get("kind") or PartyKind.CUSTOMER
    if kind not in PartyKind.values:
        raise HttpError(400, "Type de tiers invalide (customer, supplier ou both).")
    name = (payload.get("name") or "").strip()
    if not name:
        raise HttpError(400, "Le nom du tiers est requis.")
    account = None
    if payload.get("account_id"):
        account = Account.objects.filter(
            id=payload["account_id"], company=company, is_active=True, is_postable=True
        ).first()
    if account is None:
        account = resolve_account(company, DEFAULT_ACCOUNT[kind])
    if account is None or not str(account.code).startswith("4"):
        raise HttpError(400, "Le compte du tiers doit être un compte de classe 4.")
    reference = (payload.get("reference") or "").strip() or next_reference(company, kind)
    if ThirdParty.objects.filter(company=company, reference=reference).exists():
        raise HttpError(409, f"La référence {reference} existe déjà.")
    account = ensure_party_auxiliary(
        company, kind=kind, name=name, reference=reference, base=account
    )
    return ThirdParty.objects.create(
        organization=company.organization,
        company=company,
        kind=kind,
        name=name,
        reference=reference,
        tax_id=(payload.get("tax_id") or "").strip(),
        account=account,
    )


def open_lines(company, *, party_id: str | None = None, account_id: str | None = None, prefix: str = ""):
    qs = (
        EntryLine.objects.filter(
            company=company,
            entry__status=EntryStatus.POSTED,
            lettering="",
            account__account_class="4",
        )
        .select_related("account", "entry", "third_party")
        .order_by("entry__accounting_date", "position")
    )
    if party_id:
        qs = qs.filter(third_party_id=party_id)
    if account_id:
        qs = qs.filter(account_id=account_id)
    if prefix:
        qs = qs.filter(account__code__startswith=prefix)
    lines = list(qs)
    attach_inferred_parties(company, lines)
    return [line for line in lines if line_net(line) != 0]


def open_total(lines: list) -> Decimal:
    return sum((line_net(line) for line in lines), ZERO)


def note7_open_text(company) -> str:
    lines = open_lines(company, prefix="41")
    if not lines:
        return ""
    as_of = reference_date(company)
    aged = age_text(lines, as_of)
    parts = [f"non lettré {open_total(lines)} ({len(lines)} échéance(s))"]
    if aged:
        parts.append(aged)
    return " · ".join(parts)


def note17_open_text(company) -> str:
    lines = [line for line in open_lines(company, prefix="40") if not line.account.code.startswith("409")]
    if not lines:
        return ""
    as_of = reference_date(company)
    aged = age_text(lines, as_of)
    parts = [f"non lettré {open_total(lines)} ({len(lines)} échéance(s))"]
    if aged:
        parts.append(aged)
    return " · ".join(parts)


def note17_text(rows: list[dict]) -> str:
    suppliers = ZERO
    for row in rows:
        code = row.get("code") or ""
        if code.startswith("409"):
            continue
        if code.startswith("40"):
            suppliers += (row.get("close_credit") or ZERO) - (row.get("close_debit") or ZERO)
    if suppliers == 0:
        return ""
    return f"Fournisseurs 40 : {suppliers}"


@transaction.atomic
def letter_lines(company, line_ids: list[str]) -> str:
    ids = [str(item) for item in line_ids if item]
    if len(ids) < 2:
        raise HttpError(400, "Le lettrage exige au moins deux lignes.")
    lines = list(
        EntryLine.objects.filter(company=company, id__in=ids, entry__status=EntryStatus.POSTED)
        .select_related("account")
    )
    if len(lines) != len(set(ids)):
        raise HttpError(404, "Une des lignes est introuvable ou n’est pas validée.")
    if any(line.lettering for line in lines):
        raise HttpError(409, "Une des lignes est déjà lettrée.")
    attach_inferred_parties(company, lines)
    roots = {account_root(line.account.code) for line in lines}
    if len(roots) != 1:
        codes = ", ".join(sorted({line.account.code for line in lines}))
        raise HttpError(400, f"Comptes incompatibles ({codes}). Lettrez 411 avec 411x, ou 401 avec 401x.")
    parties = {str(line.third_party_id) for line in lines if line.third_party_id}
    if len(parties) > 1:
        raise HttpError(400, "Le lettrage se fait pour un seul tiers.")
    net = sum((line_net(line) for line in lines), ZERO)
    if net != 0:
        raise HttpError(400, "Les échéances à lettrer doivent s’annuler (facture + règlement).")
    if all(line_net(line) == 0 for line in lines):
        raise HttpError(400, "Écriture sans montant.")
    existing = list(
        EntryLine.objects.filter(company=company).exclude(lettering="").values_list("lettering", flat=True).distinct()
    )
    code = next_letter_code(existing)
    EntryLine.objects.filter(id__in=ids).update(lettering=code)
    return code


@transaction.atomic
def unletter(company, code: str) -> int:
    code = (code or "").strip()
    if not code:
        raise HttpError(400, "Code de lettrage requis.")
    updated = EntryLine.objects.filter(company=company, lettering=code).update(lettering="")
    if not updated:
        raise HttpError(404, "Lettrage introuvable.")
    return updated
