import hashlib

from django.utils import timezone
from ninja.errors import HttpError

from apps.ledger.models import AccountingPeriod, Entry, EntryStatus, PeriodStatus


def validate_period(period: AccountingPeriod) -> AccountingPeriod:
    if period.status == PeriodStatus.IT_CLOSED:
        raise HttpError(409, "Cette période a déjà une clôture informatique.")
    if period.status == PeriodStatus.VALIDATED:
        return period
    drafts = Entry.objects.filter(period=period, status=EntryStatus.DRAFT).count()
    if drafts:
        raise HttpError(409, f"{drafts} brouillon(s) encore ouvert(s) sur cette période.")
    period.status = PeriodStatus.VALIDATED
    period.validated_at = timezone.now()
    period.save(update_fields=["status", "validated_at"])
    return period


def it_close_period(period: AccountingPeriod) -> AccountingPeriod:
    if period.status == PeriodStatus.OPEN:
        raise HttpError(409, "Validez d’abord la période (art. 22-2).")
    if period.status == PeriodStatus.IT_CLOSED:
        return period
    posted = (
        Entry.objects.filter(period=period, status=EntryStatus.POSTED)
        .order_by("accounting_date", "number")
        .values_list("id", "number_display", "accounting_date")
    )
    raw = "|".join(f"{row[0]}:{row[1]}:{row[2]}" for row in posted)
    period.seal = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    period.status = PeriodStatus.IT_CLOSED
    period.it_closed_at = timezone.now()
    period.save(update_fields=["status", "seal", "it_closed_at"])
    return period
