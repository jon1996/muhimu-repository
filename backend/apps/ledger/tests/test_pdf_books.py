from datetime import date
from decimal import Decimal

from apps.ledger.models import AccountingPeriod, Exercise, InventoryCampaign, InventoryStatus, Journal, JournalType
from apps.ledger.services.pdf_books import BOOK_KINDS, books_filename, render_books_pdf
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase


class BooksPdfTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.period = AccountingPeriod.objects.create(
            organization=self.org,
            company=self.company,
            exercise=self.exercise,
            year=2026,
            month=1,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        self.journal = Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.acc701 = self.make_account("701", "Ventes")

    def _post(self):
        entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 12),
            value_date=date(2026, 1, 12),
            description="Vente demo",
            document_ref="F-1",
            raw_lines=[
                {"account_id": str(self.acc411.id), "debit": "25000", "credit": "0", "label": "Client"},
                {"account_id": str(self.acc701.id), "debit": "0", "credit": "25000", "label": "Vente"},
            ],
        )
        return post_entry(entry, None)

    def test_filename(self):
        self.assertEqual(books_filename(self.period, "journal"), "livre-journal-2026-01.pdf")
        self.assertEqual(books_filename(self.period, "all"), "livres-legaux-2026-01.pdf")

    def test_journal_contains_posted_lines(self):
        self._post()
        pdf = render_books_pdf(self.company, self.period, "journal")
        self.assertTrue(pdf.startswith(b"%PDF"))
        text = pdf.decode("latin-1", errors="ignore")
        self.assertIn("Livre-journal", text)
        self.assertIn("411", text)
        self.assertIn("701", text)
        self.assertIn("25 000", text)
        self.assertIn("SARL Test", text)

    def test_ledger_and_balance(self):
        self._post()
        ledger = render_books_pdf(self.company, self.period, "ledger")
        balance = render_books_pdf(self.company, self.period, "balance")
        self.assertIn(b"Grand-livre", ledger)
        self.assertIn(b"411", ledger)
        self.assertIn(b"Balance des comptes", balance)
        self.assertIn(b"25 000", balance)

    def test_inventory_includes_closed_campaign(self):
        campaign = InventoryCampaign.objects.create(
            organization=self.org,
            company=self.company,
            exercise=self.exercise,
            inventoried_on=date(2026, 1, 31),
            status=InventoryStatus.CLOSED,
        )
        campaign.lines.create(
            organization=self.org,
            company=self.company,
            description="Stock marchandises",
            quantity=Decimal("10"),
            unit="u",
            unit_value=Decimal("1000"),
            amount=Decimal("10000"),
        )
        pdf = render_books_pdf(self.company, self.period, "inventory")
        text = pdf.decode("latin-1", errors="ignore")
        self.assertIn("Livre d'inventaire", text)
        self.assertIn("Stock marchandises", text)
        self.assertIn("10 000", text)

    def test_bundle_and_unknown_kind(self):
        self._post()
        bundle = render_books_pdf(self.company, self.period, "all")
        text = bundle.decode("latin-1", errors="ignore")
        self.assertIn("Livre-journal", text)
        self.assertIn("Grand-livre", text)
        self.assertIn("Balance des comptes", text)
        self.assertGreater(len(bundle), len(render_books_pdf(self.company, self.period, "journal")))
        with self.assertRaises(ValueError):
            render_books_pdf(self.company, self.period, "unknown")
        self.assertEqual(len(BOOK_KINDS), 5)
