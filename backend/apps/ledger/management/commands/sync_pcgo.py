from django.core.management.base import BaseCommand

from apps.ledger.models import Account
from apps.ledger.services.setup import ensure_company_ledger, sync_official_accounts
from apps.tenancy.models import Company
from apps.tenancy.rls import bypass_rls


class Command(BaseCommand):
    help = "Fusionne le PCGO officiel (classes 1–9, divisionnaires) dans chaque société."

    def handle(self, *args, **options):
        with bypass_rls():
            companies = list(Company.objects.select_related("organization"))
            if not companies:
                self.stdout.write("Aucune société.")
                return
            for company in companies:
                created, updated = sync_official_accounts(company)
                ensure_company_ledger(company)
                total = Account.objects.filter(company=company, is_syscohada=True).count()
                self.stdout.write(
                    f"{company.name}: +{created} nouveaux, {updated} alignés, {total} officiels."
                )
