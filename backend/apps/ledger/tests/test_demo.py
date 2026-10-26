from datetime import date

from ninja.errors import HttpError

from apps.ledger.models import AccountingPeriod, Entry, Exercise, FixedAsset, Journal, JournalType
from apps.ledger.services.demo import initialize_ledger, seed_demo_data
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase


class DemoSeedTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        year = 2026
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=year,
            starts_on=date(year, 1, 1),
            ends_on=date(year, 12, 31),
        )
        for month in range(1, 13):
            last = 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30 if month != 2 else 28
            AccountingPeriod.objects.create(
                organization=self.org,
                company=self.company,
                exercise=self.exercise,
                year=year,
                month=month,
                starts_on=date(year, month, 1),
                ends_on=date(year, month, last),
            )
        for code, name, journal_type in (
            ("OD", "OD", JournalType.OD),
            ("AC", "Achats", JournalType.PURCHASE),
            ("VT", "Ventes", JournalType.SALE),
            ("BQ", "Banque", JournalType.BANK),
            ("CA", "Caisse", JournalType.CASH),
        ):
            Journal.objects.create(
                organization=self.org,
                company=self.company,
                code=code,
                name=name,
                type=journal_type,
            )
        for code, label in (
            ("101", "Capital"),
            ("2441", "Matériel de bureau"),
            ("2844", "Amortissements matériel"),
            ("521", "Banque"),
            ("571", "Caisse"),
            ("601", "Achats"),
            ("622", "Locations"),
            ("6813", "Dotations corporelles"),
            ("701", "Ventes"),
        ):
            self.make_account(code, label)

    def test_empty_choice_does_not_seed(self):
        result = initialize_ledger(self.company, with_demo=False)
        self.company.refresh_from_db()
        self.assertEqual(result["setup_data"], "empty")
        self.assertEqual(self.company.setup_data, "empty")
        self.assertEqual(Entry.objects.filter(company=self.company).count(), 0)
        self.assertEqual(self.company.parties.count(), 0)

    def test_demo_choice_posts_sample_books(self):
        result = initialize_ledger(self.company, with_demo=True)
        self.company.refresh_from_db()
        self.assertEqual(result["setup_data"], "demo")
        self.assertEqual(result["seeded"], 8)
        self.assertEqual(Entry.objects.filter(company=self.company, source="demo").count(), 8)
        self.assertTrue(self.company.parties.filter(reference="CLI-0001").exists())
        self.assertTrue(self.company.parties.filter(reference="FOU-0001").exists())
        self.assertTrue(FixedAsset.objects.filter(company=self.company).exists())
        again = initialize_ledger(self.company, with_demo=True)
        self.assertTrue(again["already"])
        self.assertEqual(Entry.objects.filter(company=self.company, source="demo").count(), 8)

    def test_organization_choice_applies_once(self):
        from apps.ledger.services.demo import initialize_organization

        result = initialize_organization(self.org, with_demo=True)
        self.org.refresh_from_db()
        self.company.refresh_from_db()
        self.assertEqual(result["setup_data"], "demo")
        self.assertEqual(self.org.setup_data, "demo")
        self.assertEqual(self.company.setup_data, "demo")
        self.assertEqual(result["companies"], 1)
        skipped = initialize_organization(self.org, with_demo=False)
        self.assertTrue(skipped["already"])
        self.org.refresh_from_db()
        self.assertEqual(self.org.setup_data, "demo")

    def test_demo_refuses_existing_manual_entries(self):
        journal = Journal.objects.get(company=self.company, code="OD")
        entry = create_draft(
            company=self.company,
            journal=journal,
            accounting_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Pièce manuelle",
            document_ref="MAN-1",
            raw_lines=[
                {"account_id": str(self.make_account("104", "Exploitant").id), "debit": "10", "credit": "0"},
                {"account_id": str(self.acc411.id), "debit": "0", "credit": "10"},
            ],
        )
        post_entry(entry, None)
        with self.assertRaises(HttpError):
            seed_demo_data(self.company)
