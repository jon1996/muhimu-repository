"""CAGE SYSCOHADA — réfléchissement facultatif des classes 6/7 vers 92–99.

Jamais mélangé aux classes 1–8. Réfléchissement 921/927 sur 95, imputations
93/94 (stocks), 96 (écarts), 97 (incorporation), clôture 95 → 981.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    CageReflection,
    CageSection,
    Entry,
    EntryLine,
    EntryStatus,
    Journal,
    JournalType,
)
from apps.ledger.money import parse_amount
from apps.ledger.services.setup import find_parent_account

ZERO = Decimal("0")
CHARGE_CODE = "921"
PRODUCT_CODE = "927"
STOCK_COST_CODE = "931"
STOCK_CODE = "941"
VARIANCE_CODE = "961"
CHARGE_NI_CODE = "971"
PRODUCT_NI_CODE = "972"
SUPPLETIVE_CODE = "973"
RESULT_CODE = "981"
SKIP_SOURCES = frozenset(
    {
        "cage",
        "cage_alloc",
        "cage_close",
        "class9",
        "result_close",
        "allocation",
        "dividend_payment",
        "opening",
        "fx_reval",
    }
)
CAGE_FRAMES = (
    ("9", "Comptes des engagements hors bilan et de la CAGE", False),
    ("92", "Comptes de réfléchissement (CAGE)", False),
    ("93", "Coûts des stocks (CAGE)", False),
    ("94", "Stocks et en-cours analytiques (CAGE)", False),
    ("95", "Sections analytiques (CAGE)", False),
    ("96", "Écarts sur coûts préétablis (CAGE)", False),
    ("97", "Différences d’incorporation (CAGE)", False),
    ("98", "Résultats de la CAGE", False),
    ("99", "Liaisons internes CAGE", False),
)
CAGE_POSTABLE = (
    (CHARGE_CODE, "Réfléchissement des charges"),
    (PRODUCT_CODE, "Réfléchissement des produits"),
    (STOCK_COST_CODE, "Coût des stocks"),
    (STOCK_CODE, "Stocks et en-cours analytiques"),
    (VARIANCE_CODE, "Écarts sur coûts préétablis"),
    (CHARGE_NI_CODE, "Charges non incorporables"),
    (PRODUCT_NI_CODE, "Produits non incorporables"),
    (SUPPLETIVE_CODE, "Charges supplétives"),
    (RESULT_CODE, "Résultat analytique"),
    ("991", "Liaisons internes"),
)
ALLOCATE_KINDS = (
    "stock_in",
    "stock_out",
    "variance",
    "charge_ni",
    "product_ni",
    "suppletive",
)


def format_amount(amount: Decimal) -> str:
    return format(amount, "f")


def section_code(raw: str) -> str:
    code = re.sub(r"[^A-Z0-9]", "", (raw or "").upper())
    if not code:
        raise HttpError(400, "Code de section invalide (lettres et chiffres).")
    return code[:12]


def reflection_kind(account_code: str) -> str:
    root = str(account_code or "").strip()[:1]
    if root == "6":
        return "charge"
    if root == "7":
        return "product"
    return ""


def net_to_reflect(kind: str, debit: Decimal, credit: Decimal) -> Decimal:
    debit = debit or ZERO
    credit = credit or ZERO
    if kind == "charge":
        return debit - credit
    if kind == "product":
        return credit - debit
    return ZERO


def reflection_pairs(
    kind: str,
    amount: Decimal,
    section_account_id: str,
    mirror_account_id: str,
    *,
    label: str = "",
    cage_section_id: str | None = None,
) -> list[dict]:
    """Charges : Dr 95 / Cr 921. Produits : Dr 927 / Cr 95. Montant négatif = inversion."""
    if not kind or amount == 0:
        return []
    formatted = format_amount(abs(amount))
    invert = amount < 0
    section_line = {
        "account_id": section_account_id,
        "label": label,
        "cage_section_id": cage_section_id,
    }
    mirror_line = {
        "account_id": mirror_account_id,
        "label": label,
        "cage_section_id": None,
    }
    if kind == "charge":
        if invert:
            return [
                {**mirror_line, "debit": formatted, "credit": "0"},
                {**section_line, "debit": "0", "credit": formatted},
            ]
        return [
            {**section_line, "debit": formatted, "credit": "0"},
            {**mirror_line, "debit": "0", "credit": formatted},
        ]
    if invert:
        return [
            {**section_line, "debit": formatted, "credit": "0"},
            {**mirror_line, "debit": "0", "credit": formatted},
        ]
    return [
        {**mirror_line, "debit": formatted, "credit": "0"},
        {**section_line, "debit": "0", "credit": formatted},
    ]


def should_reflect(entry: Entry) -> bool:
    if entry.status != EntryStatus.POSTED:
        return False
    return entry.source not in SKIP_SOURCES


def _ensure_account(company, code: str, label: str, is_postable: bool) -> Account:
    account = Account.objects.filter(company=company, code=code).first()
    if account:
        if is_postable and not account.is_postable:
            account.is_postable = True
            account.save(update_fields=["is_postable"])
        return account
    account = Account(
        organization=company.organization,
        company=company,
        code=code,
        label=label,
        parent=find_parent_account(company, code),
        is_postable=is_postable,
        is_syscohada=True,
    )
    account.save()
    return account


def ensure_cage_accounts(company) -> dict[str, Account]:
    for code, label, postable in CAGE_FRAMES:
        _ensure_account(company, code, label, postable)
    found = {}
    for code, label in CAGE_POSTABLE:
        found[code] = _ensure_account(company, code, label, True)
    return found


def ensure_cage_journal(company) -> Journal:
    journal, _ = Journal.objects.get_or_create(
        company=company,
        code="CG",
        defaults={
            "organization": company.organization,
            "name": "CAGE",
            "type": JournalType.OD,
        },
    )
    return journal


def _unset_defaults(company, keep_id=None) -> None:
    qs = CageSection.objects.filter(company=company, is_default=True)
    if keep_id:
        qs = qs.exclude(pk=keep_id)
    qs.update(is_default=False)


def serialize_section(section: CageSection) -> dict:
    return {
        "id": str(section.id),
        "code": section.code,
        "label": section.label,
        "account_id": str(section.account_id),
        "account_code": section.account.code,
        "is_default": section.is_default,
        "is_active": section.is_active,
    }


@transaction.atomic
def create_section(company, payload: dict) -> CageSection:
    code = section_code(payload.get("code") or "")
    label = (payload.get("label") or "").strip()
    if not label:
        raise HttpError(400, "Intitulé de section requis.")
    if CageSection.objects.filter(company=company, code=code).exists():
        raise HttpError(409, f"La section {code} existe déjà.")
    ensure_cage_accounts(company)
    account_code = f"95-{code}"
    account = Account.objects.filter(company=company, code=account_code).first()
    if account is None:
        parent = find_parent_account(company, account_code) or Account.objects.filter(
            company=company, code="95"
        ).first()
        account = Account(
            organization=company.organization,
            company=company,
            code=account_code,
            label=label,
            parent=parent,
            is_postable=True,
            is_syscohada=False,
            notes=f"Section CAGE {code}",
        )
        account.save()
    elif CageSection.objects.filter(account=account).exists():
        raise HttpError(409, f"Le compte {account_code} est déjà une section CAGE.")
    is_default = bool(payload.get("is_default"))
    if not CageSection.objects.filter(company=company, is_active=True).exists():
        is_default = True
    if is_default:
        _unset_defaults(company)
    return CageSection.objects.create(
        organization=company.organization,
        company=company,
        code=code,
        label=label,
        account=account,
        is_default=is_default,
        is_active=True,
    )


@transaction.atomic
def update_section(company, section_id: str, payload: dict) -> CageSection:
    section = (
        CageSection.objects.filter(company=company, id=section_id)
        .select_related("account")
        .first()
    )
    if section is None:
        raise HttpError(404, "Section CAGE introuvable.")
    fields = []
    if "label" in payload and payload["label"] is not None:
        label = str(payload["label"]).strip()
        if not label:
            raise HttpError(400, "Intitulé de section requis.")
        section.label = label
        fields.append("label")
        if not section.account.is_syscohada:
            section.account.label = label
            section.account.save(update_fields=["label"])
    if "is_active" in payload and payload["is_active"] is not None:
        section.is_active = bool(payload["is_active"])
        fields.append("is_active")
        if not section.is_active and section.is_default:
            section.is_default = False
            fields.append("is_default")
    if "is_default" in payload and payload["is_default"] is not None:
        want_default = bool(payload["is_default"])
        if want_default and not section.is_active:
            raise HttpError(400, "Impossible de mettre une section inactive par défaut.")
        section.is_default = want_default
        if "is_default" not in fields:
            fields.append("is_default")
        if want_default:
            _unset_defaults(company, keep_id=section.pk)
    if fields:
        section.save(update_fields=fields)
    return CageSection.objects.select_related("account").get(pk=section.pk)


def _default_section(company) -> CageSection | None:
    return (
        CageSection.objects.filter(company=company, is_active=True, is_default=True)
        .select_related("account")
        .first()
        or CageSection.objects.filter(company=company, is_active=True)
        .select_related("account")
        .order_by("code")
        .first()
    )


def _resolve_line_section(line: EntryLine, default: CageSection | None) -> CageSection | None:
    section = getattr(line, "cage_section", None)
    if section is not None and section.is_active:
        return section
    return default


def _build_reflection_lines(entry: Entry, default: CageSection | None) -> list[dict]:
    accounts = ensure_cage_accounts(entry.company)
    charge_id = str(accounts[CHARGE_CODE].id)
    product_id = str(accounts[PRODUCT_CODE].id)
    grouped: dict[str, dict] = defaultdict(
        lambda: {"charge": ZERO, "product": ZERO, "section": None, "labels": []}
    )
    for line in entry.lines.select_related("account", "cage_section"):
        kind = reflection_kind(line.account.code)
        net = net_to_reflect(kind, line.debit, line.credit)
        if not kind or net == 0:
            continue
        section = _resolve_line_section(line, default)
        if section is None:
            continue
        bucket = grouped[str(section.id)]
        bucket["section"] = section
        bucket[kind] += net
        if line.label:
            bucket["labels"].append(line.label)
    raw: list[dict] = []
    for bucket in grouped.values():
        section = bucket["section"]
        label = bucket["labels"][0] if bucket["labels"] else entry.description
        raw.extend(
            reflection_pairs(
                "charge",
                bucket["charge"],
                str(section.account_id),
                charge_id,
                label=label,
                cage_section_id=str(section.id),
            )
        )
        raw.extend(
            reflection_pairs(
                "product",
                bucket["product"],
                str(section.account_id),
                product_id,
                label=label,
                cage_section_id=str(section.id),
            )
        )
    return raw


@transaction.atomic
def reflect_entry(entry: Entry, user) -> CageReflection | None:
    if not should_reflect(entry):
        return None
    existing = (
        CageReflection.objects.filter(source_entry=entry)
        .select_related("cage_entry")
        .first()
    )
    if existing:
        return existing
    default = _default_section(entry.company)
    raw_lines = _build_reflection_lines(entry, default)
    if not raw_lines:
        return None
    journal = ensure_cage_journal(entry.company)
    from apps.ledger.services.posting import create_draft, post_entry

    key = hashlib.sha256(f"cage:{entry.id}".encode()).hexdigest()
    cage_entry = create_draft(
        company=entry.company,
        journal=journal,
        accounting_date=entry.accounting_date,
        value_date=entry.value_date,
        description=f"CAGE {entry.number_display or entry.description}".strip(),
        document_ref=entry.document_ref or entry.number_display,
        raw_lines=raw_lines,
        idempotency_key=key,
        source="cage",
    )
    cage_entry = post_entry(cage_entry, user)
    return CageReflection.objects.create(
        organization=entry.organization,
        company=entry.company,
        source_entry=entry,
        cage_entry=cage_entry,
    )


def reflect_after_post(entry: Entry, user) -> CageReflection | None:
    if not should_reflect(entry):
        return None
    if not CageSection.objects.filter(company=entry.company, is_active=True).exists():
        return None
    return reflect_entry(entry, user)


def pending_entries(company, period):
    reflected = CageReflection.objects.filter(company=company).values("source_entry_id")
    return (
        Entry.objects.filter(
            company=company,
            period=period,
            status=EntryStatus.POSTED,
        )
        .exclude(source__in=SKIP_SOURCES)
        .exclude(id__in=reflected)
        .filter(Q(lines__account__code__startswith="6") | Q(lines__account__code__startswith="7"))
        .distinct()
    )


@transaction.atomic
def reflect_period(company, period, user) -> dict:
    created = 0
    skipped = 0
    for entry in pending_entries(company, period).select_related("journal"):
        result = reflect_entry(entry, user)
        if result is None:
            skipped += 1
        else:
            created += 1
    panel = cage_panel(company, period)
    panel["created"] = created
    panel["skipped"] = skipped
    return panel


def _section_result(company, period, section: CageSection) -> dict:
    agg = EntryLine.objects.filter(
        company=company,
        account=section.account,
        entry__status=EntryStatus.POSTED,
        entry__period=period,
    ).exclude(entry__source="cage_close").aggregate(debit=Sum("debit"), credit=Sum("credit"))
    charges = agg["debit"] or ZERO
    products = agg["credit"] or ZERO
    return {
        "section_id": str(section.id),
        "code": section.code,
        "label": section.label,
        "charges": format_amount(charges),
        "products": format_amount(products),
        "result": format_amount(products - charges),
    }


def _open_close_entry(company, period):
    return (
        Entry.objects.filter(
            company=company,
            period=period,
            source="cage_close",
            status=EntryStatus.POSTED,
        )
        .annotate(rev_count=Count("reversals"))
        .filter(rev_count=0)
        .order_by("-posted_at", "-created_at")
        .first()
    )


def _cage_date(period):
    today = timezone.localdate()
    if period.starts_on <= today <= period.ends_on:
        return today
    return period.ends_on


def _resolve_active_section(company, section_id: str) -> CageSection:
    section = (
        CageSection.objects.filter(company=company, id=section_id)
        .select_related("account")
        .first()
    )
    if section is None:
        raise HttpError(404, "Section CAGE introuvable.")
    if not section.is_active:
        raise HttpError(400, "Section CAGE inactive.")
    return section


def _post_cage_lines(company, period, user, *, source: str, description: str, raw_lines: list[dict], key: str):
    journal = ensure_cage_journal(company)
    from apps.ledger.services.posting import create_draft, post_entry

    on = _cage_date(period)
    entry = create_draft(
        company=company,
        journal=journal,
        accounting_date=on,
        value_date=on,
        description=description,
        document_ref=period.ends_on.isoformat(),
        raw_lines=raw_lines,
        idempotency_key=key,
        source=source,
    )
    if entry.status != EntryStatus.POSTED:
        entry = post_entry(entry, user)
    return entry


def _dc(account_id: str, debit: Decimal, credit: Decimal, *, label: str, section_id: str | None) -> dict:
    return {
        "account_id": account_id,
        "debit": format_amount(debit),
        "credit": format_amount(credit),
        "label": label,
        "cage_section_id": section_id,
    }


@transaction.atomic
def allocate_cage(company, period, user, payload: dict) -> dict:
    kind = str(payload.get("kind") or "").strip()
    if kind not in ALLOCATE_KINDS:
        raise HttpError(400, "Imputation CAGE inconnue (stock_in, stock_out, variance, charge_ni, product_ni, suppletive).")
    if _open_close_entry(company, period):
        raise HttpError(409, "CAGE déjà clôturée sur cette période. Contrepasser l’écriture 981 pour reprendre.")
    section = _resolve_active_section(company, str(payload.get("section_id") or ""))
    amount = parse_amount(payload.get("amount") or "0", company.currency_code or "XOF")
    if kind == "variance":
        if amount == 0:
            raise HttpError(400, "Montant d’écart requis (positif = défavorable).")
    elif amount <= 0:
        raise HttpError(400, "Montant strictement positif requis.")
    accounts = ensure_cage_accounts(company)
    section_id = str(section.account_id)
    sid = str(section.id)
    abs_amt = abs(amount)
    labels = {
        "stock_in": f"Stock CAGE {section.code}",
        "stock_out": f"Sortie stock CAGE {section.code}",
        "variance": f"Écart coûts CAGE {section.code}",
        "charge_ni": f"Charge non incorporable {section.code}",
        "product_ni": f"Produit non incorporable {section.code}",
        "suppletive": f"Charge supplétive {section.code}",
    }
    label = labels[kind]
    if kind == "stock_in":
        raw = [
            _dc(str(accounts[STOCK_COST_CODE].id), abs_amt, ZERO, label=label, section_id=sid),
            _dc(section_id, ZERO, abs_amt, label=label, section_id=sid),
            _dc(str(accounts[STOCK_CODE].id), abs_amt, ZERO, label=label, section_id=sid),
            _dc(str(accounts[STOCK_COST_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
        ]
    elif kind == "stock_out":
        raw = [
            _dc(str(accounts[STOCK_COST_CODE].id), abs_amt, ZERO, label=label, section_id=sid),
            _dc(str(accounts[STOCK_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
            _dc(section_id, abs_amt, ZERO, label=label, section_id=sid),
            _dc(str(accounts[STOCK_COST_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
        ]
    elif kind == "variance":
        if amount > 0:
            raw = [
                _dc(str(accounts[VARIANCE_CODE].id), abs_amt, ZERO, label=label, section_id=sid),
                _dc(section_id, ZERO, abs_amt, label=label, section_id=sid),
            ]
        else:
            raw = [
                _dc(section_id, abs_amt, ZERO, label=label, section_id=sid),
                _dc(str(accounts[VARIANCE_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
            ]
    elif kind == "charge_ni":
        raw = [
            _dc(str(accounts[CHARGE_NI_CODE].id), abs_amt, ZERO, label=label, section_id=sid),
            _dc(section_id, ZERO, abs_amt, label=label, section_id=sid),
        ]
    elif kind == "product_ni":
        raw = [
            _dc(section_id, abs_amt, ZERO, label=label, section_id=sid),
            _dc(str(accounts[PRODUCT_NI_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
        ]
    else:
        raw = [
            _dc(section_id, abs_amt, ZERO, label=label, section_id=sid),
            _dc(str(accounts[SUPPLETIVE_CODE].id), ZERO, abs_amt, label=label, section_id=sid),
        ]
    n = Entry.objects.filter(company=company, period=period, source="cage_alloc").count()
    key = hashlib.sha256(f"cage_alloc:{period.id}:{kind}:{section.id}:{amount}:{n}".encode()).hexdigest()
    _post_cage_lines(
        company,
        period,
        user,
        source="cage_alloc",
        description=label,
        raw_lines=raw,
        key=key,
    )
    return cage_panel(company, period)


@transaction.atomic
def close_cage(company, period, user) -> dict:
    existing = _open_close_entry(company, period)
    if existing:
        return cage_panel(company, period)
    pending = pending_entries(company, period).count()
    if pending:
        raise HttpError(400, f"{pending} écriture(s) 6/7 encore à réfléchir avant la clôture CAGE.")
    ensure_cage_accounts(company)
    result_account = Account.objects.filter(company=company, code=RESULT_CODE).first()
    if result_account is None:
        raise HttpError(400, "Compte 981 introuvable. Réinitialisez le plan classe 9.")
    sections = list(
        CageSection.objects.filter(company=company, is_active=True).select_related("account")
    )
    raw: list[dict] = []
    net_result = ZERO
    for section in sections:
        row = _section_result(company, period, section)
        result = parse_amount(row["result"], company.currency_code or "XOF")
        if result == 0:
            continue
        sid = str(section.id)
        label = f"Clôture CAGE {section.code}"
        if result > 0:
            raw.append(_dc(str(section.account_id), result, ZERO, label=label, section_id=sid))
            net_result += result
        else:
            raw.append(_dc(str(section.account_id), ZERO, abs(result), label=label, section_id=sid))
            net_result += result
    if not raw:
        raise HttpError(400, "Aucun solde de section à virer au 981.")
    if net_result > 0:
        raw.append(_dc(str(result_account.id), ZERO, net_result, label="Résultat analytique", section_id=None))
    else:
        raw.append(
            _dc(str(result_account.id), abs(net_result), ZERO, label="Résultat analytique", section_id=None)
        )
    n = Entry.objects.filter(company=company, period=period, source="cage_close").count()
    key = hashlib.sha256(f"cage_close:{period.id}:{n}".encode()).hexdigest()
    _post_cage_lines(
        company,
        period,
        user,
        source="cage_close",
        description=f"Clôture CAGE {period.year}-{period.month:02d}",
        raw_lines=raw,
        key=key,
    )
    return cage_panel(company, period)


def cage_panel(company, period) -> dict:
    ensure_cage_accounts(company)
    sections = list(
        CageSection.objects.filter(company=company).select_related("account")
    )
    results = [
        _section_result(company, period, section)
        for section in sections
        if section.is_active
    ]
    pending = pending_entries(company, period).count()
    reflected = CageReflection.objects.filter(
        company=company, source_entry__period=period
    ).count()
    last = (
        Entry.objects.filter(
            company=company,
            source__in={"cage", "cage_alloc", "cage_close"},
            status=EntryStatus.POSTED,
        )
        .order_by("-posted_at", "-created_at")
        .first()
    )
    close = _open_close_entry(company, period)
    result_agg = EntryLine.objects.filter(
        company=company,
        account__code=RESULT_CODE,
        entry__status=EntryStatus.POSTED,
        entry__period=period,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    analytical = (result_agg["credit"] or ZERO) - (result_agg["debit"] or ZERO)
    return {
        "sections": [serialize_section(section) for section in sections],
        "results": results,
        "pending": pending,
        "reflected": reflected,
        "last_entry_id": str(last.id) if last else None,
        "last_entry_number": last.number_display if last else "",
        "created": 0,
        "skipped": 0,
        "closed": close is not None,
        "close_entry_id": str(close.id) if close else None,
        "close_entry_number": close.number_display if close else "",
        "analytical_result": format_amount(analytical),
    }
