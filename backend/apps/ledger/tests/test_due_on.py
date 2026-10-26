from datetime import date
from decimal import Decimal
from unittest import TestCase as UnitTestCase

from django.core.exceptions import ValidationError
from ninja.errors import HttpError

from apps.ledger.models import (
    AccountingPeriod,
    EntryStatus,
    Exercise,
    Journal,
    JournalType,
)
from apps.ledger.services.lettering import parse_due_on, set_line_due
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase


class ParseDueTests(UnitTestCase):
    def test_iso_and_empty(self):
        self.assertEqual(parse_due_on("2026-10-15"), date(2026, 10, 15))
        self.assertIsNone(parse_due_on(""))
        self.assertIsNone(parse_due_on(None))
        self.assertEqual(parse_due_on(date(2026, 1, 1)), date(2026, 1, 1))

    def test_rejects_garbage(self):
        with self.assertRaises(HttpError):
            parse_due_on("15/10/2026")


class PostedDueTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.acc521 = self.make_account("521", "Banques")
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        AccountingPeriod.objects.create(
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
            code="VT",
            name="Ventes",
            type=JournalType.SALE,
        )
        self.entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Facture test",
            document_ref="FAC-DUE",
            raw_lines=[
                {
                    "account_id": str(self.acc411.id),
                    "debit": "1000",
                    "credit": "0",
                    "label": "Client",
                },
                {
                    "account_id": str(self.acc521.id),
                    "debit": "0",
                    "credit": "1000",
                    "label": "Banque",
                },
            ],
        )
        self.entry = post_entry(self.entry, None)
        self.line = self.entry.lines.get(account=self.acc411)

    def test_save_annotation_due_on_posted_line_allowed(self):
        """ACC-02 : échéance = annotation autorisée via save() si seuls les champs whitelist changent."""
        self.line.due_on = date(2026, 2, 1)
        self.line.save()
        self.line.refresh_from_db()
        self.assertEqual(self.line.due_on, date(2026, 2, 1))

    def test_save_amount_on_posted_line_blocked(self):
        self.line.debit = Decimal("2000")
        with self.assertRaises(ValidationError):
            self.line.save()

    def test_queryset_update_sets_due_on_posted_line(self):
        updated = set_line_due(self.company, str(self.line.id), "2026-03-31")
        self.assertEqual(updated.due_on, date(2026, 3, 31))
        self.line.refresh_from_db()
        self.assertEqual(self.line.due_on, date(2026, 3, 31))

    def test_clear_due_on(self):
        set_line_due(self.company, str(self.line.id), "2026-03-31")
        updated = set_line_due(self.company, str(self.line.id), "")
        self.assertIsNone(updated.due_on)

    def test_unknown_line(self):
        with self.assertRaises(HttpError):
            set_line_due(self.company, "00000000-0000-0000-0000-000000000000", "2026-01-01")

    def test_status_posted_via_queryset_update_blocked(self):
        with self.assertRaises(ValidationError):
            from apps.ledger.models import Entry

            Entry.objects.filter(pk=self.entry.pk).update(status=EntryStatus.DRAFT)
