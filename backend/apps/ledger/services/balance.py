from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Sum

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    BalanceSnapshot,
    Entry,
    EntryLine,
    EntryStatus,
)


def apply_posted_lines(entry: Entry) -> None:
    """Met à jour les snapshots de la période (pas de SUM sur tout l'historique).

    Concurrence (ACC-01) :
    - verrouille la période (`select_for_update`) pour sérialiser création/maj ;
    - agrège les lignes par compte (ordre déterministe d'account_id) ;
    - crée le snapshot si besoin (IntegrityError → relecture verrouillée) ;
    - incrémente ``mov_*`` via ``F()`` (pas de read-modify-write Python).
    """
    period = AccountingPeriod.objects.select_for_update().get(pk=entry.period_id)

    deltas: dict[str, dict] = {}
    lines = entry.lines.select_related("account").order_by("account_id", "position")
    for line in lines:
        key = str(line.account_id)
        bucket = deltas.get(key)
        if bucket is None:
            deltas[key] = {
                "account": line.account,
                "debit": line.debit,
                "credit": line.credit,
            }
        else:
            bucket["debit"] += line.debit
            bucket["credit"] += line.credit

    for key in sorted(deltas.keys()):
        bucket = deltas[key]
        _apply_delta(period, bucket["account"], bucket["debit"], bucket["credit"])


def _apply_delta(period: AccountingPeriod, account: Account, debit: Decimal, credit: Decimal) -> None:
    if debit == 0 and credit == 0:
        return
    snapshot = _lock_or_create_snapshot(period, account)
    updated = BalanceSnapshot.objects.filter(
        pk=snapshot.pk,
        company_id=period.company_id,
        organization_id=period.organization_id,
    ).update(
        mov_debit=F("mov_debit") + debit,
        mov_credit=F("mov_credit") + credit,
    )
    if updated != 1:
        raise RuntimeError(
            f"Mise à jour atomique du snapshot impossible (period={period.pk}, account={account.pk})."
        )


def _lock_or_create_snapshot(period: AccountingPeriod, account: Account) -> BalanceSnapshot:
    existing = (
        BalanceSnapshot.objects.select_for_update()
        .filter(period_id=period.pk, account_id=account.pk)
        .first()
    )
    if existing:
        return existing

    open_debit, open_credit = _opening_balances(period, account)
    try:
        # Savepoint : IntegrityError ne casse pas la transaction externe (post_entry).
        with transaction.atomic():
            return BalanceSnapshot.objects.create(
                organization_id=period.organization_id,
                company_id=period.company_id,
                period_id=period.pk,
                account_id=account.pk,
                open_debit=open_debit,
                open_credit=open_credit,
                mov_debit=Decimal("0"),
                mov_credit=Decimal("0"),
            )
    except IntegrityError:
        return (
            BalanceSnapshot.objects.select_for_update()
            .get(period_id=period.pk, account_id=account.pk)
        )


def _opening_balances(period: AccountingPeriod, account: Account) -> tuple[Decimal, Decimal]:
    previous = (
        BalanceSnapshot.objects.filter(
            company_id=period.company_id,
            account_id=account.pk,
            period__starts_on__lt=period.starts_on,
        )
        .order_by("-period__starts_on")
        .first()
    )
    if not previous:
        return Decimal("0"), Decimal("0")
    return (
        previous.open_debit + previous.mov_debit,
        previous.open_credit + previous.mov_credit,
    )


def posted_movement_totals(company, period: AccountingPeriod, account: Account) -> tuple[Decimal, Decimal]:
    """Agrégat vérité terrain : SUM des lignes validées de la période (contrôle ACC-01)."""
    aggregates = EntryLine.objects.filter(
        company=company,
        account=account,
        entry__status=EntryStatus.POSTED,
        entry__period=period,
    ).aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return (
        aggregates["debit"] or Decimal("0"),
        aggregates["credit"] or Decimal("0"),
    )


def trial_balance(company, period: AccountingPeriod) -> list[dict]:
    snapshots = (
        BalanceSnapshot.objects.filter(company=company, period=period)
        .select_related("account")
        .order_by("account__code")
    )
    rows = []
    for snap in snapshots:
        close_debit = snap.open_debit + snap.mov_debit
        close_credit = snap.open_credit + snap.mov_credit
        if close_debit == 0 and close_credit == 0 and snap.mov_debit == 0 and snap.mov_credit == 0:
            continue
        rows.append(
            {
                "account_id": str(snap.account_id),
                "code": snap.account.code,
                "label": snap.account.label,
                "open_debit": snap.open_debit,
                "open_credit": snap.open_credit,
                "mov_debit": snap.mov_debit,
                "mov_credit": snap.mov_credit,
                "close_debit": close_debit,
                "close_credit": close_credit,
            }
        )
    return rows


def trial_balance_ytd(company, exercise) -> list[dict]:
    """Balance cumulée de l'exercice (tous les mois), pour clôture / preview.

    CLOSE-01 : ``trial_balance(décembre)`` ne voit que les snapshots de décembre.
    Les mouvements des mois antérieurs (ex. janvier) n'y figurent pas tant qu'aucune
    écriture n'a créé le snapshot de décembre. L'arrêté 6/7/8 → 13 doit s'appuyer
    sur le cumul annuel.
    """
    period_ids = list(exercise.periods.values_list("id", flat=True))
    if not period_ids:
        return []

    mov_rows = (
        BalanceSnapshot.objects.filter(company=company, period_id__in=period_ids)
        .values("account_id")
        .annotate(mov_debit=Sum("mov_debit"), mov_credit=Sum("mov_credit"))
    )
    mov_by_account = {
        str(row["account_id"]): (
            row["mov_debit"] or Decimal("0"),
            row["mov_credit"] or Decimal("0"),
        )
        for row in mov_rows
    }
    if not mov_by_account:
        return []

    first_period = exercise.periods.order_by("starts_on").first()
    open_by_account: dict[str, tuple[Decimal, Decimal]] = {}
    if first_period:
        for snap in BalanceSnapshot.objects.filter(
            company=company, period=first_period, account_id__in=mov_by_account.keys()
        ):
            open_by_account[str(snap.account_id)] = (snap.open_debit, snap.open_credit)

    # Comptes apparus en cours d'année : ouverture = open du premier snapshot du compte.
    missing = set(mov_by_account) - set(open_by_account)
    if missing:
        earliest = (
            BalanceSnapshot.objects.filter(
                company=company,
                period_id__in=period_ids,
                account_id__in=missing,
            )
            .select_related("account", "period")
            .order_by("account_id", "period__starts_on")
        )
        seen: set[str] = set()
        for snap in earliest:
            key = str(snap.account_id)
            if key in seen:
                continue
            seen.add(key)
            open_by_account[key] = (snap.open_debit, snap.open_credit)

    accounts = {
        str(account.id): account
        for account in Account.objects.filter(
            company=company, id__in=mov_by_account.keys()
        )
    }
    rows = []
    for account_id in sorted(mov_by_account.keys(), key=lambda pk: accounts[pk].code):
        account = accounts[account_id]
        open_debit, open_credit = open_by_account.get(
            account_id, (Decimal("0"), Decimal("0"))
        )
        mov_debit, mov_credit = mov_by_account[account_id]
        close_debit = open_debit + mov_debit
        close_credit = open_credit + mov_credit
        if close_debit == 0 and close_credit == 0 and mov_debit == 0 and mov_credit == 0:
            continue
        rows.append(
            {
                "account_id": account_id,
                "code": account.code,
                "label": account.label,
                "open_debit": open_debit,
                "open_credit": open_credit,
                "mov_debit": mov_debit,
                "mov_credit": mov_credit,
                "close_debit": close_debit,
                "close_credit": close_credit,
            }
        )
    return rows


def general_ledger(company, account: Account, period: AccountingPeriod) -> dict:
    snapshot = BalanceSnapshot.objects.filter(
        company=company, period=period, account=account
    ).first()
    open_debit = snapshot.open_debit if snapshot else Decimal("0")
    open_credit = snapshot.open_credit if snapshot else Decimal("0")
    running = open_debit - open_credit
    lines = (
        EntryLine.objects.filter(
            company=company,
            account=account,
            entry__status=EntryStatus.POSTED,
            entry__period=period,
        )
        .select_related("entry", "entry__journal")
        .order_by("entry__accounting_date", "entry__number", "position")
    )
    out_lines = []
    for line in lines:
        running += line.debit - line.credit
        out_lines.append(
            {
                "id": str(line.id),
                "entry_id": str(line.entry_id),
                "number_display": line.entry.number_display,
                "journal_code": line.entry.journal.code,
                "accounting_date": line.entry.accounting_date.isoformat(),
                "label": line.label or line.entry.description,
                "debit": line.debit,
                "credit": line.credit,
                "balance": running,
            }
        )
    return {
        "account_id": str(account.id),
        "code": account.code,
        "label": account.label,
        "open_debit": open_debit,
        "open_credit": open_credit,
        "lines": out_lines,
        "close_balance": running,
    }
