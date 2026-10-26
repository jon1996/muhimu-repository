from datetime import date
from decimal import Decimal

from ninja.errors import HttpError

from apps.ledger.models import AccountingPeriod, Entry, EntryLine, Exercise, Journal, JournalType
from apps.ledger.services.fx import compute_revalue, get_rate, post_revalue, upsert_rate
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase


class FxEngineTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
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
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.acc478 = self.make_account("478", "Écarts de conversion - actif")
        self.acc479 = self.make_account("479", "Écarts de conversion - passif")
        self.acc701 = self.make_account("701", "Ventes")
        self.acc605 = self.make_account("605", "Achats")

    def _post(self, lines, day=10, **kwargs):
        entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, day),
            value_date=date(2026, 1, day),
            description="FX",
            document_ref="FX-TEST",
            raw_lines=lines,
            **kwargs,
        )
        return post_entry(entry, None)

    def test_latest_rate_on_or_before_date(self):
        upsert_rate(self.company, "EUR", date(2026, 1, 1), "650")
        upsert_rate(self.company, "EUR", date(2026, 1, 15), "655")
        self.assertEqual(get_rate(self.company, "EUR", date(2026, 1, 10)), Decimal("650"))
        self.assertEqual(get_rate(self.company, "EUR", date(2026, 1, 15)), Decimal("655"))
        self.assertEqual(get_rate(self.company, "XOF", date(2026, 1, 15)), Decimal("1"))

    def test_convert_at_post(self):
        upsert_rate(self.company, "EUR", date(2026, 1, 1), "650")
        entry = self._post(
            [
                {
                    "account_id": str(self.acc411.id),
                    "debit": "100",
                    "credit": "0",
                    "currency_code": "EUR",
                },
                {
                    "account_id": str(self.acc701.id),
                    "debit": "0",
                    "credit": "100",
                    "currency_code": "EUR",
                },
            ]
        )
        lines = {line.account.code: line for line in entry.lines.all()}
        self.assertEqual(lines["411"].debit, Decimal("65000"))
        self.assertEqual(lines["411"].foreign_amount, Decimal("100.00"))
        self.assertEqual(lines["411"].currency_code, "EUR")
        self.assertEqual(lines["411"].fx_rate, Decimal("650.00000000"))
        self.assertEqual(lines["701"].credit, Decimal("65000"))

    def test_explicit_rate_overrides_table(self):
        upsert_rate(self.company, "EUR", date(2026, 1, 1), "650")
        entry = self._post(
            [
                {
                    "account_id": str(self.acc411.id),
                    "debit": "100",
                    "credit": "0",
                    "currency_code": "EUR",
                    "fx_rate": "655",
                },
                {
                    "account_id": str(self.acc701.id),
                    "debit": "0",
                    "credit": "100",
                    "currency_code": "EUR",
                    "fx_rate": "655",
                },
            ]
        )
        line = entry.lines.get(account=self.acc411)
        self.assertEqual(line.debit, Decimal("65500"))
        self.assertEqual(line.fx_rate, Decimal("655.00000000"))

    def test_missing_rate_errors(self):
        with self.assertRaises(HttpError) as ctx:
            self._post(
                [
                    {
                        "account_id": str(self.acc411.id),
                        "debit": "100",
                        "credit": "0",
                        "currency_code": "EUR",
                    },
                    {
                        "account_id": str(self.acc701.id),
                        "debit": "0",
                        "credit": "100",
                        "currency_code": "EUR",
                    },
                ]
            )
        self.assertIn("Aucun cours EUR/XOF", ctx.exception.message)

    def test_functional_line_unchanged(self):
        entry = self._post(
            [
                {"account_id": str(self.acc411.id), "debit": "1000", "credit": "0"},
                {"account_id": str(self.acc701.id), "debit": "0", "credit": "1000"},
            ]
        )
        line = entry.lines.get(account=self.acc411)
        self.assertEqual(line.debit, Decimal("1000"))
        self.assertEqual(line.currency_code, "XOF")
        self.assertEqual(line.foreign_amount, Decimal("0"))

    def test_revalue_receivable_gain(self):
        upsert_rate(self.company, "EUR", date(2026, 1, 10), "650")
        self._post(
            [
                {
                    "account_id": str(self.acc411.id),
                    "debit": "100",
                    "credit": "0",
                    "currency_code": "EUR",
                },
                {
                    "account_id": str(self.acc701.id),
                    "debit": "0",
                    "credit": "100",
                    "currency_code": "EUR",
                },
            ]
        )
        upsert_rate(self.company, "EUR", date(2026, 1, 31), "655")
        preview = compute_revalue(self.company, date(2026, 1, 31))
        self.assertTrue(preview["ok"], preview["errors"])
        self.assertEqual(len(preview["lines"]), 1)
        self.assertEqual(preview["lines"][0]["kind"], "gain")
        self.assertEqual(preview["lines"][0]["difference"], "500")
        self.assertEqual(preview["lines"][0]["debit_account_code"], "411")
        self.assertEqual(preview["lines"][0]["credit_account_code"], "479")
        result = post_revalue(self.company, date(2026, 1, 31), None)
        self.assertTrue(result["posted"])
        entry = Entry.objects.get(id=result["entry_id"])
        self.assertEqual(entry.source, "fx_reval")
        booked = {line.account.code: line for line in entry.lines.all()}
        self.assertEqual(booked["411"].debit, Decimal("500"))
        self.assertEqual(booked["411"].currency_code, "EUR")
        self.assertEqual(booked["411"].foreign_amount, Decimal("0"))
        self.assertEqual(booked["479"].credit, Decimal("500"))
        net_411 = sum(
            (line.debit - line.credit for line in EntryLine.objects.filter(account=self.acc411)),
            Decimal("0"),
        )
        self.assertEqual(net_411, Decimal("65500"))
        with self.assertRaises(HttpError):
            post_revalue(self.company, date(2026, 1, 31), None)
        second = compute_revalue(self.company, date(2026, 1, 31))
        self.assertEqual(second["lines"], [])
        self.assertTrue(second["posted"])

    def test_revalue_payable_loss(self):
        upsert_rate(self.company, "EUR", date(2026, 1, 10), "650")
        self._post(
            [
                {
                    "account_id": str(self.acc605.id),
                    "debit": "100",
                    "credit": "0",
                    "currency_code": "EUR",
                },
                {
                    "account_id": str(self.acc401.id),
                    "debit": "0",
                    "credit": "100",
                    "currency_code": "EUR",
                },
            ]
        )
        upsert_rate(self.company, "EUR", date(2026, 1, 31), "655")
        preview = compute_revalue(self.company, date(2026, 1, 31))
        self.assertEqual(preview["lines"][0]["kind"], "loss")
        self.assertEqual(preview["lines"][0]["debit_account_code"], "478")
        self.assertEqual(preview["lines"][0]["credit_account_code"], "401")
        post_revalue(self.company, date(2026, 1, 31), None)
        net_401 = sum(
            (line.debit - line.credit for line in EntryLine.objects.filter(account=self.acc401)),
            Decimal("0"),
        )
        self.assertEqual(net_401, Decimal("-65500"))

    def test_no_fx_position(self):
        preview = compute_revalue(self.company, date(2026, 1, 31))
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["lines"], [])
        with self.assertRaises(HttpError):
            post_revalue(self.company, date(2026, 1, 31), None)
