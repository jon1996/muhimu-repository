from __future__ import annotations

import secrets
import string

from django.db import transaction

from apps.identity.emails import reject_local_email_in_production
from apps.identity.models import User
from apps.platform.models import DemoGrant
from apps.tenancy.models import Company, CompanyAccess, Membership, Organization, Role

DEMO_PME_SLUG = "demo-pme"
DEMO_CABINET_SLUG = "demo-cabinet"


class DemoSandboxMissing(Exception):
    """Les organisations sandbox n'ont pas encore été créées."""


def generate_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in password)
            and any(c.isupper() for c in password)
            and any(c.isdigit() for c in password)
        ):
            return password


def demo_sandbox() -> tuple[Organization, Organization]:
    sme = Organization.objects.filter(slug=DEMO_PME_SLUG, is_demo=True).first()
    cabinet = Organization.objects.filter(slug=DEMO_CABINET_SLUG, is_demo=True).first()
    if sme is None or cabinet is None:
        raise DemoSandboxMissing("Sandbox démo absente. Lancez bootstrap_demo.")
    return sme, cabinet


def sync_demo_memberships(user: User, *, access_pme: bool, access_cabinet: bool, active: bool) -> None:
    sme, cabinet = demo_sandbox()
    _sync_membership(user, sme, active=active and access_pme)
    _sync_membership(user, cabinet, active=active and access_cabinet)
    companies = list(Company.objects.filter(organization=cabinet, is_active=True))
    if active and access_cabinet:
        for company in companies:
            CompanyAccess.objects.get_or_create(
                organization=cabinet,
                company=company,
                user=user,
            )
    else:
        CompanyAccess.objects.filter(organization=cabinet, user=user).delete()


def _sync_membership(user: User, organization: Organization, *, active: bool) -> None:
    membership, created = Membership.objects.get_or_create(
        organization=organization,
        user=user,
        defaults={"role": Role.ACCOUNTANT, "is_active": active},
    )
    if created:
        return
    membership.is_active = active
    membership.save(update_fields=["is_active"])


@transaction.atomic
def upsert_demo_grant(
    *,
    email: str,
    full_name: str = "",
    access_pme: bool = True,
    access_cabinet: bool = True,
    notes: str = "",
    granted_by: User | None = None,
    send_email: bool = True,
    reset_password: bool = True,
    activate: bool = True,
) -> tuple[DemoGrant, str | None]:
    if not access_pme and not access_cabinet:
        raise ValueError("Choisissez au moins un dossier démo (PME ou cabinet).")

    email = reject_local_email_in_production(email)
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User(email=email, full_name=full_name.strip(), is_active=True)
        created = True
    else:
        created = False
        if user.is_staff:
            raise ValueError("Un compte équipe Muhimu ne peut pas recevoir un accès démo.")
        if full_name.strip():
            user.full_name = full_name.strip()
        user.is_active = True

    password: str | None = None
    if created or reset_password or not user.has_usable_password():
        password = generate_password()
        user.set_password(password)
    user.save()

    grant, _ = DemoGrant.objects.update_or_create(
        user=user,
        defaults={
            "access_pme": access_pme,
            "access_cabinet": access_cabinet,
            "is_active": activate,
            "granted_by": granted_by,
            "notes": notes.strip(),
        },
    )
    sync_demo_memberships(
        user,
        access_pme=access_pme,
        access_cabinet=access_cabinet,
        active=activate,
    )
    return grant, password


@transaction.atomic
def revoke_demo_grant(grant: DemoGrant) -> DemoGrant:
    grant.is_active = False
    grant.save(update_fields=["is_active", "updated_at"])
    sync_demo_memberships(
        grant.user,
        access_pme=False,
        access_cabinet=False,
        active=False,
    )
    return grant
