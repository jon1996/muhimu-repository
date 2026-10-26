from django.test import TestCase

from apps.ledger.models import Account
from apps.tenancy.models import Company, Organization, OrganizationType


class LedgerDbTestCase(TestCase):
    """PostgreSQL + RLS : les tests Django se connectent en ``muhimu`` (BYPASSRLS)."""

    def setUp(self):
        super().setUp()
        # A1′ : plus de GUC bypass ; le rôle de test est déjà privilégié.
        self.org = Organization.objects.create(
            name="Org test",
            slug="",
            type=OrganizationType.SME,
        )
        self.company = Company.objects.create(
            organization=self.org,
            name="SARL Test",
            currency_code="XOF",
        )
        self.acc411 = self.make_account("411", "Clients")
        self.acc401 = self.make_account("401", "Fournisseurs")

    def make_account(self, code: str, label: str, **kwargs) -> Account:
        account = Account(
            organization=self.org,
            company=self.company,
            code=code,
            label=label,
            is_postable=kwargs.get("is_postable", True),
            is_syscohada=kwargs.get("is_syscohada", True),
            parent=kwargs.get("parent"),
        )
        account.save()
        return account
