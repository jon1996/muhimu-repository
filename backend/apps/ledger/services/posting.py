from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
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
    JournalSequence,
    PeriodStatus,
    ThirdParty,
)
from apps.ledger.money import parse_amount
from apps.ledger.services.balance import apply_posted_lines
from apps.tenancy.models import Company


def _currency(company: Company) -> str:
    return (company.currency_code or "XOF").upper()


def _parse_lines(company: Company, raw_lines: list[dict], on: date | None = None) -> list[dict]:
    currency = _currency(company)
    parsed = []
    for index, raw in enumerate(raw_lines):
        account_id = str(raw.get("account_id") or "")
        account = Account.objects.filter(
            id=account_id, company=company, is_active=True
        ).first()
        if not account:
            raise HttpError(400, f"Compte introuvable (ligne {index + 1}).")
        if not account.is_postable:
            raise HttpError(400, f"Le compte {account.code} n'est pas imputable.")
        line_ccy = (raw.get("currency_code") or currency).strip().upper() or currency
        amounts_functional = bool(raw.get("amounts_functional"))
        if line_ccy != currency and not amounts_functional:
            from apps.ledger.services.fx import convert_amount, get_rate, normalize_currency

            line_ccy = normalize_currency(line_ccy)
            foreign_debit = parse_amount(raw.get("debit") or "0", line_ccy)
            foreign_credit = parse_amount(raw.get("credit") or "0", line_ccy)
            if foreign_debit == 0 and foreign_credit == 0:
                raise HttpError(400, f"Ligne {index + 1} : montant débiteur ou créditeur requis.")
            if foreign_debit != 0 and foreign_credit != 0:
                raise HttpError(400, f"Ligne {index + 1} : une ligne ne peut pas être à la fois débit et crédit.")
            rate = get_rate(company, line_ccy, on or timezone.localdate(), raw.get("fx_rate"))
            debit = convert_amount(foreign_debit, rate, currency)
            credit = convert_amount(foreign_credit, rate, currency)
            if debit == 0 and credit == 0:
                raise HttpError(400, f"Ligne {index + 1} : conversion nulle vers {currency}.")
            foreign_amount = foreign_debit if foreign_debit != 0 else foreign_credit
            fx_rate = rate
        else:
            debit = parse_amount(raw.get("debit") or "0", currency)
            credit = parse_amount(raw.get("credit") or "0", currency)
            if debit == 0 and credit == 0:
                raise HttpError(400, f"Ligne {index + 1} : montant débiteur ou créditeur requis.")
            if debit != 0 and credit != 0:
                raise HttpError(400, f"Ligne {index + 1} : une ligne ne peut pas être à la fois débit et crédit.")
            if line_ccy != currency and amounts_functional:
                from apps.ledger.services.fx import normalize_currency

                line_ccy = normalize_currency(line_ccy)
                foreign_amount = Decimal("0")
                fx_rate = Decimal("1")
            else:
                line_ccy = currency
                foreign_amount = Decimal("0")
                fx_rate = Decimal("1")
        party = None
        party_id = raw.get("third_party_id")
        if party_id:
            party = ThirdParty.objects.filter(id=party_id, company=company, is_active=True).select_related("account").first()
            if not party:
                raise HttpError(400, f"Tiers introuvable (ligne {index + 1}).")
            from apps.ledger.services.lettering import bind_party_account

            account = bind_party_account(account, party)
        due_on = None
        raw_due = raw.get("due_on") or ""
        if raw_due:
            try:
                due_on = date.fromisoformat(str(raw_due)[:10])
            except ValueError as exc:
                raise HttpError(400, f"Échéance invalide (ligne {index + 1}).") from exc
        section = None
        section_id = raw.get("cage_section_id")
        if section_id:
            from apps.ledger.models import CageSection

            section = CageSection.objects.filter(
                id=section_id, company=company, is_active=True
            ).first()
            if not section:
                raise HttpError(400, f"Section CAGE introuvable (ligne {index + 1}).")
        parsed.append(
            {
                "account": account,
                "debit": debit,
                "credit": credit,
                "label": (raw.get("label") or "").strip(),
                "position": index,
                "third_party": party,
                "due_on": due_on,
                "cage_section": section,
                "currency_code": line_ccy,
                "foreign_amount": foreign_amount,
                "fx_rate": fx_rate,
            }
        )
    return parsed


def assert_double_entry(lines: list[dict]) -> None:
    if len(lines) < 2:
        raise HttpError(400, "La partie double exige au moins deux lignes (art. 17-2).")
    total_debit = sum((line["debit"] for line in lines), Decimal("0"))
    total_credit = sum((line["credit"] for line in lines), Decimal("0"))
    if total_debit != total_credit:
        raise HttpError(400, "Totaux débit et crédit différents (partie double, art. 17-2).")
    if total_debit == 0:
        raise HttpError(400, "Écriture sans montant.")
    classes = {str(line["account"].code)[:1] for line in lines if line.get("account")}
    if "9" in classes and classes != {"9"}:
        raise HttpError(
            400,
            "Une écriture de classe 9 (hors bilan / CAGE) ne se mélange pas aux classes 1 à 8.",
        )


def resolve_period(company: Company, accounting_date: date, value_date: date) -> tuple[date, AccountingPeriod, Exercise]:
    exercise = (
        Exercise.objects.filter(
            company=company,
            starts_on__lte=accounting_date,
            ends_on__gte=accounting_date,
        )
        .exclude(status=ExerciseStatus.CLOSED)
        .first()
    )
    if not exercise:
        raise HttpError(400, "Aucun exercice ouvert pour cette date comptable.")

    period = AccountingPeriod.objects.filter(
        exercise=exercise,
        starts_on__lte=accounting_date,
        ends_on__gte=accounting_date,
    ).first()
    if not period:
        raise HttpError(400, "Période introuvable pour cette date.")

    # Art. 22-4 : période déjà clôturée → 1er jour de la prochaine période ouverte.
    if period.status != PeriodStatus.OPEN:
        nxt = (
            AccountingPeriod.objects.filter(exercise=exercise, status=PeriodStatus.OPEN)
            .filter(starts_on__gt=period.starts_on)
            .order_by("starts_on")
            .first()
        )
        if not nxt:
            raise HttpError(400, "Période clôturée et aucune période ouverte suivante.")
        return nxt.starts_on, nxt, exercise
    return accounting_date, period, exercise


def _replace_lines(entry: Entry, lines: list[dict]) -> None:
    if entry.status == EntryStatus.POSTED:
        raise HttpError(409, "Impossible de remplacer les lignes d'une écriture validée.")
    EntryLine.objects.filter(entry=entry).delete()
    EntryLine.objects.bulk_create(
        [
            EntryLine(
                organization=entry.organization,
                company=entry.company,
                entry=entry,
                account=line["account"],
                third_party=line.get("third_party"),
                due_on=line.get("due_on"),
                cage_section=line.get("cage_section"),
                label=line["label"] or entry.description,
                debit=line["debit"],
                credit=line["credit"],
                currency_code=line.get("currency_code") or "",
                foreign_amount=line.get("foreign_amount") or Decimal("0"),
                fx_rate=line.get("fx_rate") or Decimal("1"),
                position=line["position"],
            )
            for line in lines
        ]
    )


@transaction.atomic
def create_draft(
    *,
    company: Company,
    journal: Journal,
    accounting_date: date,
    value_date: date | None,
    description: str,
    document_ref: str,
    raw_lines: list[dict],
    idempotency_key: str = "",
    source: str = "manual",
) -> Entry:
    if journal.company_id != company.id:
        raise HttpError(400, "Journal d'une autre société.")
    if idempotency_key:
        existing = Entry.objects.filter(company=company, idempotency_key=idempotency_key).first()
        if existing:
            return existing
    value_date = value_date or accounting_date
    lines = _parse_lines(company, raw_lines, value_date)
    assert_double_entry(lines)
    posting_date, period, exercise = resolve_period(company, accounting_date, value_date)
    entry = Entry.objects.create(
        organization=company.organization,
        company=company,
        exercise=exercise,
        period=period,
        journal=journal,
        accounting_date=posting_date,
        value_date=value_date,
        description=description.strip(),
        document_ref=document_ref.strip(),
        status=EntryStatus.DRAFT,
        source=source,
        idempotency_key=idempotency_key.strip(),
    )
    _replace_lines(entry, lines)
    return entry


@transaction.atomic
def update_draft(
    entry: Entry,
    *,
    journal: Journal | None = None,
    accounting_date: date | None = None,
    value_date: date | None = None,
    description: str | None = None,
    document_ref: str | None = None,
    raw_lines: list[dict] | None = None,
) -> Entry:
    if entry.status != EntryStatus.DRAFT:
        raise HttpError(409, "Seuls les brouillons sont modifiables.")
    if journal is not None:
        if journal.company_id != entry.company_id:
            raise HttpError(400, "Journal d'une autre société.")
        entry.journal = journal
    if description is not None:
        entry.description = description.strip()
    if document_ref is not None:
        entry.document_ref = document_ref.strip()
    acc_date = accounting_date or entry.accounting_date
    val_date = value_date or entry.value_date
    posting_date, period, exercise = resolve_period(entry.company, acc_date, val_date)
    entry.accounting_date = posting_date
    entry.value_date = val_date
    entry.period = period
    entry.exercise = exercise
    entry.save()
    if raw_lines is not None:
        lines = _parse_lines(entry.company, raw_lines, val_date)
        assert_double_entry(lines)
        _replace_lines(entry, lines)
    return entry


@transaction.atomic
def post_entry(entry: Entry, user) -> Entry:
    if entry.status == EntryStatus.POSTED:
        return entry
    lines = list(entry.lines.select_related("account").all())
    parsed = [
        {"debit": line.debit, "credit": line.credit, "account": line.account, "label": line.label, "position": line.position}
        for line in lines
    ]
    assert_double_entry(parsed)
    posting_date, period, exercise = resolve_period(entry.company, entry.accounting_date, entry.value_date)
    if period.status != PeriodStatus.OPEN:
        raise HttpError(400, "Impossible de valider dans une période non ouverte.")
    if exercise.status == ExerciseStatus.CLOSED:
        raise HttpError(400, "Exercice clôturé.")

    seq, _ = JournalSequence.objects.select_for_update().get_or_create(
        journal=entry.journal,
        exercise=exercise,
        defaults={
            "organization": entry.organization,
            "company": entry.company,
            "last_number": 0,
        },
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number"])

    entry.period = period
    entry.exercise = exercise
    entry.accounting_date = posting_date
    entry.number = seq.last_number
    entry.number_display = f"{entry.journal.code}-{exercise.year}-{seq.last_number:05d}"
    entry.status = EntryStatus.POSTED
    entry.posted_at = timezone.now()
    entry.posted_by = user
    entry.save(allow_posted_write=True)

    apply_posted_lines(entry)
    from apps.ledger.services.cage import reflect_after_post

    reflect_after_post(entry, user)
    return entry


@transaction.atomic
def reverse_entry(entry: Entry, user, description: str = "") -> Entry:
    """Contrepassation en négatif (art. 20) — l'écriture d'origine reste intacte."""
    if entry.status != EntryStatus.POSTED:
        raise HttpError(400, "Seule une écriture validée peut être contrepassée.")
    if entry.reversals.exists():
        raise HttpError(409, "Cette écriture a déjà une contrepassation.")

    today = timezone.localdate()
    posting_date, period, exercise = resolve_period(entry.company, today, entry.value_date)
    reversal = Entry.objects.create(
        organization=entry.organization,
        company=entry.company,
        exercise=exercise,
        period=period,
        journal=entry.journal,
        accounting_date=posting_date,
        value_date=entry.value_date,
        description=description.strip() or f"Contrepassation {entry.number_display}",
        document_ref=entry.document_ref,
        status=EntryStatus.DRAFT,
        source="reversal",
        reversed_entry=entry,
    )
    EntryLine.objects.bulk_create(
        [
            EntryLine(
                organization=entry.organization,
                company=entry.company,
                entry=reversal,
                account=line.account,
                third_party=line.third_party,
                cage_section=line.cage_section,
                label=line.label,
                debit=-line.debit,
                credit=-line.credit,
                currency_code=line.currency_code,
                foreign_amount=-line.foreign_amount,
                fx_rate=line.fx_rate,
                position=line.position,
            )
            for line in entry.lines.all()
        ]
    )
    return post_entry(reversal, user)


def month_end(year: int, month: int) -> date:
    return date(year, month, monthrange(year, month)[1])
