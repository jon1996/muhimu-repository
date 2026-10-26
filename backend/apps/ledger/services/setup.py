from calendar import monthrange
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.ledger.models import Account, AccountingPeriod, Exercise, ExerciseStatus, Journal
from apps.ledger.pcgo import DEFAULT_JOURNALS, PCGO_ACCOUNTS
from apps.ledger.taxonomy import infer_parent_code
from apps.tenancy.models import Company


def relink_account_parents(company: Company) -> None:
    accounts = {account.code: account for account in Account.objects.filter(company=company)}
    updates = []
    for account in accounts.values():
        parent_code = infer_parent_code(account.code)
        parent = None
        while parent_code:
            parent = accounts.get(parent_code)
            if parent:
                break
            parent_code = infer_parent_code(parent_code)
        parent_id = parent.pk if parent else None
        if account.parent_id != parent_id:
            account.parent = parent
            updates.append(account)
    if updates:
        Account.objects.bulk_update(updates, ["parent"])


def find_parent_account(company: Company, code: str) -> Account | None:
    parent_code = infer_parent_code(code)
    while parent_code:
        parent = Account.objects.filter(company=company, code=parent_code).first()
        if parent:
            return parent
        parent_code = infer_parent_code(parent_code)
    return None


def sync_official_accounts(company: Company) -> tuple[int, int]:
    """Fusionne le PCGO officiel. Ne touche pas aux comptes personnalisés."""
    existing = {account.code: account for account in Account.objects.filter(company=company)}
    to_create: list[Account] = []
    to_update: list[Account] = []
    for code, label, is_postable in PCGO_ACCOUNTS:
        account = existing.get(code)
        if account is None:
            account = Account(
                organization=company.organization,
                company=company,
                code=code,
                label=label,
                is_postable=is_postable,
                is_syscohada=True,
            )
            account.apply_taxonomy()
            account.is_postable = is_postable and account.level != "class"
            to_create.append(account)
            continue
        if not account.is_syscohada:
            continue
        account.label = label
        account.apply_taxonomy()
        account.is_postable = is_postable and account.level != "class"
        account.is_syscohada = True
        to_update.append(account)
    if to_create:
        Account.objects.bulk_create(to_create, batch_size=400)
    if to_update:
        Account.objects.bulk_update(
            to_update,
            [
                "label",
                "account_class",
                "level",
                "family",
                "sense",
                "is_postable",
                "is_collective",
                "is_syscohada",
            ],
            batch_size=400,
        )
    relink_account_parents(company)
    return len(to_create), len(to_update)


@transaction.atomic
def ensure_company_ledger(company: Company, year: int | None = None) -> Exercise:
    """Copie le PCGO, crée les journaux et ouvre l'exercice civil (art. 8)."""
    org = company.organization
    year = year or timezone.localdate().year
    sync_official_accounts(company)

    for code, name, journal_type in DEFAULT_JOURNALS:
        Journal.objects.get_or_create(
            company=company,
            code=code,
            defaults={"organization": org, "name": name, "type": journal_type},
        )

    exercise, created = Exercise.objects.get_or_create(
        company=company,
        year=year,
        defaults={
            "organization": org,
            "starts_on": date(year, 1, 1),
            "ends_on": date(year, 12, 31),
            "status": ExerciseStatus.OPEN,
        },
    )
    if created or not exercise.periods.exists():
        periods = []
        for month in range(1, 13):
            last = monthrange(year, month)[1]
            periods.append(
                AccountingPeriod(
                    organization=org,
                    company=company,
                    exercise=exercise,
                    year=year,
                    month=month,
                    starts_on=date(year, month, 1),
                    ends_on=date(year, month, last),
                )
            )
        AccountingPeriod.objects.bulk_create(periods)
    return exercise
