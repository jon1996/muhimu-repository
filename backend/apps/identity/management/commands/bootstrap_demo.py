from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.identity.emails import is_local_dev_email
from apps.identity.models import User
from apps.ledger.services.setup import ensure_company_ledger
from apps.platform.models import DemoGrant
from apps.tenancy.models import (
    Company,
    CompanyAccess,
    CompanyOfficer,
    Membership,
    Organization,
    OrganizationType,
    Role,
)
from apps.tenancy.rls import bypass_rls


def _ensure_local_user(email: str, full_name: str, password: str, *, staff: bool = False) -> User:
    defaults = {"full_name": full_name}
    if staff:
        defaults["is_staff"] = True
        defaults["is_superuser"] = True
    user, created = User.objects.get_or_create(email=email, defaults=defaults)
    dirty = []
    if created or not user.has_usable_password():
        user.full_name = user.full_name or full_name
        if staff:
            user.is_staff = True
            user.is_superuser = True
        user.set_password(password)
        user.save()
        return user
    if staff and not user.is_staff:
        user.is_staff = True
        user.is_superuser = True
        dirty.extend(["is_staff", "is_superuser"])
    if user.full_name in ("", "Utilisateur démo", "Ops Muhimu") and full_name:
        if user.full_name != full_name:
            user.full_name = full_name
            dirty.append("full_name")
    if not user.is_active:
        user.is_active = True
        dirty.append("is_active")
    if dirty:
        user.save(update_fields=dirty)
    return user


def _retire_local_dev_accounts() -> int:
    users = User.objects.filter(email__iendswith="@muhimu.local", is_active=True)
    ids = list(users.values_list("id", flat=True))
    retired = users.update(is_active=False, is_staff=False, is_superuser=False)
    if ids:
        DemoGrant.objects.filter(user_id__in=ids, is_active=True).update(is_active=False)
    return retired


def _ensure_production_staff() -> tuple[User | None, str]:
    email = (settings.STAFF_EMAIL or "").lower().strip()
    if not email:
        return None, "STAFF_EMAIL manquant : aucun compte console production créé."
    if is_local_dev_email(email):
        return None, "STAFF_EMAIL ne peut pas être une adresse @muhimu.local."
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "full_name": settings.STAFF_FULL_NAME or "Muhimu",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    user.full_name = user.full_name or settings.STAFF_FULL_NAME or "Muhimu"
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    note = f"Console production : {email}"
    if created or not user.has_usable_password():
        if not settings.STAFF_PASSWORD:
            user.save()
            return user, f"{note} — définissez STAFF_PASSWORD pour le premier mot de passe."
        user.set_password(settings.STAFF_PASSWORD)
        note = f"{note} (mot de passe initial posé)."
    user.save()
    return user, note


class Command(BaseCommand):
    help = "Sandbox démo SYSCOHADA. Comptes @muhimu.local en local uniquement."

    def handle(self, *args, **options):
        local = bool(settings.BOOTSTRAP_LOCAL_ACCOUNTS)
        with bypass_rls(), transaction.atomic():
            user = None
            if local:
                user = _ensure_local_user(
                    "demo@muhimu.local",
                    "Uwase Bahavu",
                    "Demo1234!",
                )
                if user.full_name in ("", "Utilisateur démo"):
                    user.full_name = "Uwase Bahavu"
                    user.save(update_fields=["full_name"])
                _ensure_local_user(
                    "ops@muhimu.local",
                    "Ops Muhimu",
                    "Ops1234!",
                    staff=True,
                )

            sme, _ = Organization.objects.get_or_create(
                slug="demo-pme",
                defaults={
                    "name": "SARL Horizon",
                    "type": OrganizationType.SME,
                    "is_demo": True,
                },
            )
            cabinet, _ = Organization.objects.get_or_create(
                slug="demo-cabinet",
                defaults={
                    "name": "Cabinet Koffi & Associés",
                    "type": OrganizationType.CABINET,
                    "is_demo": True,
                },
            )
            if sme.name.startswith("Demo"):
                sme.name = "SARL Horizon"
            sme.is_demo = True
            sme.save()
            if cabinet.name.startswith("Demo"):
                cabinet.name = "Cabinet Koffi & Associés"
            cabinet.is_demo = True
            cabinet.save()

            if user is not None:
                Membership.objects.get_or_create(
                    organization=sme, user=user, defaults={"role": Role.OWNER}
                )
                Membership.objects.get_or_create(
                    organization=cabinet, user=user, defaults={"role": Role.OWNER}
                )

            sme_co, _ = Company.objects.get_or_create(
                organization=sme,
                name="SARL Horizon",
                defaults={
                    "legal_name": "SARL Horizon",
                    "country_code": "CI",
                    "currency_code": "XOF",
                },
            )
            if not sme_co.rccm:
                sme_co.legal_form = "sarl"
                sme_co.tax_regime = "reel_normal"
                sme_co.control_kind = "private_national"
                sme_co.rccm = "CI-ABJ-2020-B-12345"
                sme_co.tax_id = "CI0001234567"
                sme_co.social_register = "CNPS-012345"
                sme_co.acronym = "HORIZON"
                sme_co.address = "12 boulevard de la République"
                sme_co.city = "Abidjan"
                sme_co.phone = "+225 27 20 00 00 00"
                sme_co.email = "contact@horizon.demo"
                sme_co.naema_code = "G460000"
                sme_co.auditor_name = "Cabinet Koffi & Associés"
                sme_co.auditor_order_no = "ONECCA-CI-421"
                sme_co.signatory_name = "Uwase Bahavu"
                sme_co.signatory_title = "Gérante"
                sme_co.banks = "NSIA Banque CI, BICICI"
                sme_co.save()
            if sme_co.signatory_name in ("", "Awa Koné"):
                sme_co.signatory_name = "Uwase Bahavu"
                sme_co.signatory_title = sme_co.signatory_title or "Gérante"
                sme_co.save(update_fields=["signatory_name", "signatory_title", "updated_at"])
            sme_co.officers.filter(full_name="Awa Koné").update(full_name="Uwase Bahavu")
            if not sme_co.officers.exists():
                CompanyOfficer.objects.create(
                    organization=sme,
                    company=sme_co,
                    full_name="Uwase Bahavu",
                    role="manager",
                    nationality="Ivoirienne",
                )
            cab_a, _ = Company.objects.get_or_create(
                organization=cabinet,
                name="Société Alpha",
                defaults={
                    "legal_name": "Société Alpha SA",
                    "country_code": "CI",
                    "currency_code": "XOF",
                },
            )
            cab_b, _ = Company.objects.get_or_create(
                organization=cabinet,
                name="Société Beta",
                defaults={
                    "legal_name": "Société Beta SARL",
                    "country_code": "SN",
                    "currency_code": "XOF",
                },
            )

            if user is not None:
                CompanyAccess.objects.get_or_create(
                    organization=cabinet, company=cab_a, user=user
                )
                CompanyAccess.objects.get_or_create(
                    organization=cabinet, company=cab_b, user=user
                )

            for company in (sme_co, cab_a, cab_b):
                ensure_company_ledger(company)

            from apps.ledger.models import (
                ConsolidationGroup,
                ConsolidationKind,
                ConsolidationMember,
                ConsolidationMethod,
            )

            if not ConsolidationGroup.objects.filter(organization=cabinet, year=2026).exists():
                combo = ConsolidationGroup.objects.create(
                    organization=cabinet,
                    name="Groupe Demo Cabinet",
                    kind=ConsolidationKind.COMBINED,
                    year=2026,
                    currency_code="XOF",
                )
                for company in (cab_a, cab_b):
                    ConsolidationMember.objects.create(
                        organization=cabinet,
                        group=combo,
                        company=company,
                        method=ConsolidationMethod.COMBINED,
                        is_parent=False,
                    )

            from apps.ledger.models import Entry
            from apps.platform.services.grants import upsert_demo_grant

            if user is not None:
                DemoGrant.objects.update_or_create(
                    user=user,
                    defaults={
                        "access_pme": True,
                        "access_cabinet": True,
                        "is_active": True,
                        "notes": "Compte démo local",
                    },
                )
                tester_existed = User.objects.filter(email="tester@muhimu.local").exists()
                tester_grant, _ = upsert_demo_grant(
                    email="tester@muhimu.local",
                    full_name="Testeur Muhimu",
                    access_pme=True,
                    access_cabinet=True,
                    notes="Compte testeur local",
                    send_email=False,
                    reset_password=False,
                    activate=True,
                )
                tester = tester_grant.user
                if not tester_existed or not tester.has_usable_password():
                    tester.full_name = tester.full_name or "Testeur Muhimu"
                    tester.set_password("Tester1234!")
                    tester.save()

            for company in (sme_co, cab_a, cab_b):
                if company.setup_data or Entry.objects.filter(company=company).exists():
                    continue
                company.parties.filter(reference__in=["CLI-0001", "FOU-0001"]).delete()

            staff_note = ""
            if not local:
                retired = _retire_local_dev_accounts()
                _, staff_note = _ensure_production_staff()
                if retired:
                    self.stdout.write(f"Comptes @muhimu.local désactivés : {retired}.")

        if local:
            self.stdout.write(self.style.SUCCESS("Comptes locaux prêts."))
            self.stdout.write("  ERP démo : demo@muhimu.local / Demo1234!")
            self.stdout.write("  ERP testeur : tester@muhimu.local / Tester1234!")
            self.stdout.write("  Console  : ops@muhimu.local / Ops1234!")
        else:
            self.stdout.write(self.style.SUCCESS("Sandbox production (sans @muhimu.local)."))
            if staff_note:
                self.stdout.write(f"  {staff_note}")
        self.stdout.write(f"  PME      : {sme.slug} / {sme_co.name}")
        self.stdout.write(f"  Cabinet  : {cabinet.slug} / {cab_a.name}, {cab_b.name}")
