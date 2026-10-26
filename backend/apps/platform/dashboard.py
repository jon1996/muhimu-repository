"""Indicateurs SaaS pour le tableau de bord console."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.utils import timezone

from apps.identity.emails import visible_users
from apps.ledger.models import Entry, EntryStatus
from apps.platform.models import DemoGrant
from apps.tenancy.liasse import identity_is_complete
from apps.tenancy.models import Company, Organization, OrganizationType
from apps.tenancy.ohada import country_label

WEEKS = 8
MONTHS_FR = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)


def _week_start(moment):
    local = timezone.localtime(moment)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=start.weekday())


def _week_label(start) -> str:
    return f"{start.day} {MONTHS_FR[start.month - 1]}"


def _as_monday(value):
    if value is None:
        return None
    stamp = timezone.localtime(value) if timezone.is_aware(value) else value
    day = stamp.date() if hasattr(stamp, "date") else stamp
    return day - timedelta(days=day.weekday())


def _series(queryset, field: str, start, buckets: list) -> list[dict]:
    counted = {}
    for row in (
        queryset.filter(**{f"{field}__gte": start})
        .annotate(bucket=TruncWeek(field))
        .values("bucket")
        .annotate(value=Count("id"))
    ):
        monday = _as_monday(row["bucket"])
        if monday is not None:
            counted[monday] = row["value"]
    return [
        {"label": _week_label(week), "value": counted.get(week.date(), 0)}
        for week in buckets
    ]


def dashboard_payload() -> dict:
    now = timezone.now()
    week0 = _week_start(now - timedelta(weeks=WEEKS - 1))
    buckets = [week0 + timedelta(weeks=index) for index in range(WEEKS)]
    since_7d = now - timedelta(days=7)

    companies = list(Company.objects.prefetch_related("officers"))
    identity_ok = sum(1 for company in companies if identity_is_complete(company))
    identity_ko = len(companies) - identity_ok
    countries = Counter((company.country_code or "").upper() for company in companies)

    orgs = list(Organization.objects.all())
    demo_count = sum(1 for org in orgs if org.is_demo)
    client_orgs = [org for org in orgs if not org.is_demo]
    incomplete_orgs = []
    for org in client_orgs:
        org_companies = [company for company in companies if company.organization_id == org.id]
        if not org_companies or not all(identity_is_complete(company) for company in org_companies):
            incomplete_orgs.append(org)

    erp_users = visible_users().filter(is_staff=False)
    grants_active = DemoGrant.objects.filter(is_active=True).count()
    grants_revoked = DemoGrant.objects.filter(is_active=False).count()
    posted = Entry.objects.filter(status=EntryStatus.POSTED).count()
    drafts = Entry.objects.filter(status=EntryStatus.DRAFT).count()

    by_country = [
        {"code": code, "label": country_label(code), "value": count}
        for code, count in countries.most_common(8)
        if code
    ]

    watch = []
    for org in sorted(incomplete_orgs, key=lambda item: item.created_at, reverse=True)[:6]:
        org_companies = [company for company in companies if company.organization_id == org.id]
        watch.append(
            {
                "id": str(org.id),
                "name": org.name,
                "slug": org.slug,
                "type_label": "Cabinet" if org.type == OrganizationType.CABINET else "PME",
                "reason": "Identité incomplète" if org_companies else "Aucune société",
            }
        )

    recent = [
        {
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "type_label": "Cabinet" if org.type == OrganizationType.CABINET else "PME",
            "is_demo": bool(org.is_demo),
            "created_at": org.created_at.isoformat() if org.created_at else None,
        }
        for org in sorted(orgs, key=lambda item: item.created_at, reverse=True)[:6]
    ]

    total_orgs = len(orgs)
    return {
        "kpis": {
            "org_count": total_orgs,
            "client_count": len(client_orgs),
            "demo_count": demo_count,
            "company_count": len(companies),
            "user_count": erp_users.count(),
            "grants_active": grants_active,
            "identity_complete": identity_ok,
            "identity_incomplete": identity_ko,
            "identity_rate": round(100 * identity_ok / len(companies)) if companies else 0,
            "users_active_7d": erp_users.filter(last_login__gte=since_7d).count(),
            "users_never": erp_users.filter(last_login__isnull=True).count(),
            "entries_posted": posted,
            "entries_draft": drafts,
        },
        "by_type": [
            {"label": "PME", "value": sum(1 for org in orgs if org.type == OrganizationType.SME)},
            {
                "label": "Cabinets",
                "value": sum(1 for org in orgs if org.type == OrganizationType.CABINET),
            },
        ],
        "by_kind": [
            {"label": "Clients", "value": len(client_orgs)},
            {"label": "Démo", "value": demo_count},
        ],
        "by_identity": [
            {"label": "Complète", "value": identity_ok},
            {"label": "À renseigner", "value": identity_ko},
        ],
        "by_country": by_country,
        "orgs_by_week": _series(Organization.objects.all(), "created_at", week0, buckets),
        "users_by_week": _series(visible_users().filter(is_staff=False), "date_joined", week0, buckets),
        "grants": {"active": grants_active, "revoked": grants_revoked},
        "watch": watch,
        "recent": recent,
    }
