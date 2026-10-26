"""Rapprochement bancaire — classe 5, note 11."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from ninja.errors import HttpError

from apps.ledger.models import (
    Account,
    BankStatement,
    BankStatementLine,
    EntryLine,
    EntryStatus,
)
from apps.ledger.services.ofx import parse_ofx

ZERO = Decimal("0")

BANK_PREFIXES = ("52", "53")


def book_net(debit, credit) -> Decimal:
    return (debit or ZERO) - (credit or ZERO)


def statement_as_book(bank_debit, bank_credit) -> Decimal:
    """Crédit relevé = entrée d’argent = débit 52. Débit relevé = sortie = crédit 52."""
    return (bank_credit or ZERO) - (bank_debit or ZERO)


def next_pointage_code(existing: list[str]) -> str:
    highest = 0
    for code in existing:
        if not (code or "").startswith("P-"):
            continue
        try:
            highest = max(highest, int(code.split("-")[-1]))
        except ValueError:
            continue
    return f"P-{highest + 1:04d}"


def is_bank_account(account: Account) -> bool:
    code = (account.code or "").strip()
    return account.is_postable and any(code.startswith(prefix) for prefix in BANK_PREFIXES)


def resolve_bank_account(company, account_id: str | None) -> Account:
    qs = Account.objects.filter(company=company, is_active=True, is_postable=True)
    if account_id:
        account = qs.filter(id=account_id).first()
        if account is None or not is_bank_account(account):
            raise HttpError(400, "Choisissez un compte de banque 52 ou 53.")
        return account
    account = qs.filter(code__startswith="52").order_by("code").first()
    if account is None:
        account = qs.filter(code__startswith="53").order_by("code").first()
    if account is None:
        raise HttpError(400, "Aucun compte 52/53 imputable.")
    return account


def serialize_book_line(line: EntryLine) -> dict:
    return {
        "id": str(line.id),
        "entry_id": str(line.entry_id),
        "entry_number": line.entry.number_display,
        "accounting_date": line.entry.accounting_date.isoformat(),
        "account_id": str(line.account_id),
        "account_code": line.account.code,
        "label": line.label,
        "debit": format(line.debit, "f"),
        "credit": format(line.credit, "f"),
        "pointage": line.bank_pointage,
    }


def serialize_statement_line(line: BankStatementLine) -> dict:
    return {
        "id": str(line.id),
        "statement_id": str(line.statement_id),
        "line_date": line.line_date.isoformat(),
        "label": line.label,
        "bank_debit": format(line.bank_debit, "f"),
        "bank_credit": format(line.bank_credit, "f"),
        "pointage": line.pointage,
    }


def serialize_statement(statement: BankStatement) -> dict:
    return {
        "id": str(statement.id),
        "account_id": str(statement.account_id),
        "account_code": statement.account.code,
        "statement_date": statement.statement_date.isoformat(),
        "bank_balance": format(statement.bank_balance, "f"),
    }


def book_lines(company, account: Account) -> list[EntryLine]:
    lines = (
        EntryLine.objects.filter(
            company=company,
            account=account,
            entry__status=EntryStatus.POSTED,
            bank_pointage="",
        )
        .select_related("account", "entry")
        .order_by("entry__accounting_date", "position")
    )
    return [line for line in lines if book_net(line.debit, line.credit) != 0]


def book_balance(company, account: Account) -> Decimal:
    total = ZERO
    posted = EntryLine.objects.filter(
        company=company, account=account, entry__status=EntryStatus.POSTED
    )
    for line in posted:
        total += book_net(line.debit, line.credit)
    return total


def latest_statement(company, account: Account) -> BankStatement | None:
    return (
        BankStatement.objects.filter(company=company, account=account)
        .select_related("account")
        .order_by("-statement_date", "-created_at")
        .first()
    )


def note11_open_text(company) -> str:
    count = (
        EntryLine.objects.filter(
            company=company,
            entry__status=EntryStatus.POSTED,
            bank_pointage="",
            account__code__startswith="52",
        )
        .exclude(debit=0, credit=0)
        .count()
    )
    if not count:
        return ""
    return f"non rapproché {count} ligne(s) 52"


@transaction.atomic
def upsert_statement(company, payload: dict) -> BankStatement:
    account = resolve_bank_account(company, payload.get("account_id"))
    raw_date = payload.get("statement_date")
    if not raw_date:
        raise HttpError(400, "La date du relevé est requise.")
    if isinstance(raw_date, date):
        statement_date = raw_date
    else:
        try:
            statement_date = date.fromisoformat(str(raw_date)[:10])
        except ValueError as exc:
            raise HttpError(400, "Date de relevé invalide.") from exc
    currency = company.currency_code or "XOF"
    bank_balance = parse_amount(payload.get("bank_balance") or 0, currency)
    statement, _created = BankStatement.objects.update_or_create(
        company=company,
        account=account,
        statement_date=statement_date,
        defaults={
            "organization": company.organization,
            "bank_balance": bank_balance,
        },
    )
    return BankStatement.objects.select_related("account").get(pk=statement.pk)


@transaction.atomic
def add_statement_line(company, statement_id: str, payload: dict) -> BankStatementLine:
    statement = (
        BankStatement.objects.filter(company=company, id=statement_id).select_related("account").first()
    )
    if statement is None:
        raise HttpError(404, "Relevé introuvable.")
    currency = company.currency_code or "XOF"
    label = (payload.get("label") or "").strip()
    if not label:
        raise HttpError(400, "Le libellé de la ligne est requis.")
    raw_date = payload.get("line_date") or statement.statement_date.isoformat()
    try:
        line_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date)[:10])
    except ValueError as exc:
        raise HttpError(400, "Date de ligne invalide.") from exc
    debit = parse_amount(payload.get("bank_debit") or 0, currency)
    credit = parse_amount(payload.get("bank_credit") or 0, currency)
    if debit < 0 or credit < 0:
        raise HttpError(400, "Les montants du relevé ne peuvent pas être négatifs.")
    if debit == 0 and credit == 0:
        raise HttpError(400, "Indiquez un débit banque ou un crédit banque.")
    if debit and credit:
        raise HttpError(400, "Une ligne de relevé est soit un débit, soit un crédit.")
    position = statement.lines.count()
    return BankStatementLine.objects.create(
        organization=company.organization,
        company=company,
        statement=statement,
        line_date=line_date,
        label=label,
        bank_debit=debit,
        bank_credit=credit,
        external_id=(payload.get("external_id") or "").strip()[:64],
        position=position,
    )


@transaction.atomic
def point_selection(company, book_ids: list[str], statement_ids: list[str]) -> str:
    books = list(
        EntryLine.objects.filter(
            company=company, id__in=book_ids, entry__status=EntryStatus.POSTED
        ).select_related("account", "entry")
    )
    statements = list(
        BankStatementLine.objects.filter(company=company, id__in=statement_ids).select_related(
            "statement", "statement__account"
        )
    )
    if len(books) != len(set(book_ids)) or len(statements) != len(set(statement_ids)):
        raise HttpError(404, "Une des lignes est introuvable.")
    if not books or not statements:
        raise HttpError(400, "Cochez au moins une écriture et une ligne de relevé.")
    if any(line.bank_pointage for line in books) or any(line.pointage for line in statements):
        raise HttpError(409, "Une des lignes est déjà pointée.")
    book_accounts = {str(line.account_id) for line in books}
    statement_accounts = {str(line.statement.account_id) for line in statements}
    if len(book_accounts) != 1 or book_accounts != statement_accounts:
        raise HttpError(400, "Le pointage se fait sur un seul compte bancaire.")
    net_books = sum((book_net(line.debit, line.credit) for line in books), ZERO)
    net_bank = sum((statement_as_book(line.bank_debit, line.bank_credit) for line in statements), ZERO)
    if net_books != net_bank:
        raise HttpError(
            400,
            "Les montants ne correspondent pas. Un débit 52 se pointe avec un crédit relevé du même montant.",
        )
    if net_books == 0:
        raise HttpError(400, "Sélection sans montant.")
    existing = list(
        EntryLine.objects.filter(company=company)
        .exclude(bank_pointage="")
        .values_list("bank_pointage", flat=True)
        .distinct()
    )
    existing += list(
        BankStatementLine.objects.filter(company=company)
        .exclude(pointage="")
        .values_list("pointage", flat=True)
        .distinct()
    )
    code = next_pointage_code(existing)
    EntryLine.objects.filter(id__in=[line.id for line in books]).update(bank_pointage=code)
    BankStatementLine.objects.filter(id__in=[line.id for line in statements]).update(pointage=code)
    return code


@transaction.atomic
def unpoint(company, code: str) -> int:
    code = (code or "").strip()
    if not code:
        raise HttpError(400, "Code de pointage requis.")
    books = EntryLine.objects.filter(company=company, bank_pointage=code).update(bank_pointage="")
    statements = BankStatementLine.objects.filter(company=company, pointage=code).update(pointage="")
    if not books and not statements:
        raise HttpError(404, "Pointage introuvable.")
    return books + statements


def reconciliation_payload(company, account_id: str | None = None) -> dict:
    account = resolve_bank_account(company, account_id)
    statement = latest_statement(company, account)
    open_books = book_lines(company, account)
    open_bank = []
    if statement:
        open_bank = list(
            statement.lines.filter(pointage="").select_related("statement", "statement__account")
        )
    books_net = sum((book_net(line.debit, line.credit) for line in open_books), ZERO)
    bank_net = sum((statement_as_book(line.bank_debit, line.bank_credit) for line in open_bank), ZERO)
    book_bal = book_balance(company, account)
    bank_bal = statement.bank_balance if statement else ZERO
    return {
        "account_id": str(account.id),
        "account_code": account.code,
        "account_label": account.label,
        "book_balance": format(book_bal, "f"),
        "bank_balance": format(bank_bal, "f"),
        "unpointed_book_net": format(books_net, "f"),
        "unpointed_statement_net": format(bank_net, "f"),
        "control": format(book_bal - bank_bal - (books_net - bank_net), "f"),
        "statement": serialize_statement(statement) if statement else None,
        "book_lines": [serialize_book_line(line) for line in open_books],
        "statement_lines": [serialize_statement_line(line) for line in open_bank],
    }


@transaction.atomic
def import_ofx(company, content: bytes, account_id: str | None = None) -> dict:
    parsed = parse_ofx(content)
    if not parsed["lines"]:
        raise HttpError(400, "Aucune opération exploitable dans le fichier OFX.")
    if parsed["as_of"] is None:
        raise HttpError(400, "Date de relevé introuvable dans le fichier OFX.")
    account = resolve_bank_account(company, account_id)
    existing = latest_statement(company, account)
    bank_balance = parsed["balance"]
    if bank_balance is None:
        bank_balance = existing.bank_balance if existing and existing.statement_date == parsed["as_of"] else Decimal("0")
    statement = upsert_statement(
        company,
        {
            "account_id": str(account.id),
            "statement_date": parsed["as_of"],
            "bank_balance": bank_balance,
        },
    )
    currency = company.currency_code or "XOF"
    known = set(
        BankStatementLine.objects.filter(company=company, statement__account=account)
        .exclude(external_id="")
        .values_list("external_id", flat=True)
    )
    created = 0
    skipped = 0
    position = statement.lines.count()
    to_create: list[BankStatementLine] = []
    for item in parsed["lines"]:
        external_id = item["external_id"]
        if external_id and external_id in known:
            skipped += 1
            continue
        debit = parse_amount(item["bank_debit"], currency)
        credit = parse_amount(item["bank_credit"], currency)
        if debit == 0 and credit == 0:
            skipped += 1
            continue
        to_create.append(
            BankStatementLine(
                organization=company.organization,
                company=company,
                statement=statement,
                line_date=item["line_date"],
                label=item["label"],
                bank_debit=debit,
                bank_credit=credit,
                external_id=external_id,
                position=position,
            )
        )
        position += 1
        created += 1
        if external_id:
            known.add(external_id)
    if to_create:
        BankStatementLine.objects.bulk_create(to_create)
    return {
        "created": created,
        "skipped": skipped,
        "statement": serialize_statement(statement),
    }
