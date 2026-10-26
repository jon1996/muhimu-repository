from datetime import date
from decimal import Decimal
from unittest import TestCase as UnitTestCase

from ninja.errors import HttpError

from apps.ledger.models import (
    AccountingPeriod,
    BalanceSnapshot,
    Entry,
    Exercise,
    Journal,
    JournalType,
)
from apps.ledger.services.balance import trial_balance
from apps.ledger.services.opening import (
    is_balance_sheet,
    is_pnl,
    parse_opening_text,
    post_opening,
    preview_opening,
)
from apps.ledger.services.statements import build_statements
from apps.ledger.tests.db import LedgerDbTestCase


class OpeningParseTests(UnitTestCase):
    def test_header_and_solde(self):
        rows = parse_opening_text("code;debit;credit\n411;1000;0\n401;0;1000\n")
        self.assertEqual(rows[0]["code"], "411")
        self.assertEqual(rows[1]["credit"], "1000")
        signed = parse_opening_text("compte;solde\n411;500\n401;-500\n")
        self.assertEqual(signed[0]["solde"], "500")
        self.assertEqual(signed[1]["solde"], "-500")

    def test_kind(self):
        self.assertTrue(is_pnl("701"))
        self.assertTrue(is_pnl("605"))
        self.assertTrue(is_pnl("81"))
        self.assertTrue(is_balance_sheet("411"))
        self.assertFalse(is_pnl("411"))
        self.assertFalse(is_balance_sheet("701"))


class OpeningEngineTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        for month in range(1, 13):
            last = 31 if month in {1, 3, 5, 7, 8, 10, 12} else 30 if month != 2 else 28
            AccountingPeriod.objects.create(
                organization=self.org,
                company=self.company,
                exercise=self.exercise,
                year=2026,
                month=month,
                starts_on=date(2026, month, 1),
                ends_on=date(2026, month, last),
            )
        Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.acc131 = self.make_account("131", "Résultat bénéfice")
        self.acc139 = self.make_account("139", "Résultat perte")
        self.acc701 = self.make_account("701", "Ventes")
        self.acc605 = self.make_account("605", "Autres achats")

    def test_preview_after_close_balance(self):
        preview = preview_opening(
            self.company,
            [
                {"code": "411", "debit": "2500", "credit": "0"},
                {"code": "401", "debit": "0", "credit": "2500"},
            ],
        )
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["pnl_count"], 0)
        self.assertEqual(len(preview["an_lines"]), 2)

    def test_preview_adds_131_from_pnl(self):
        preview = preview_opening(
            self.company,
            [
                {"code": "411", "debit": "1500", "credit": "0"},
                {"code": "401", "debit": "0", "credit": "1000"},
                {"code": "701", "debit": "0", "credit": "2000"},
                {"code": "605", "debit": "1500", "credit": "0"},
            ],
        )
        self.assertTrue(preview["ok"], preview["errors"])
        self.assertEqual(preview["pnl_count"], 2)
        codes = {line["code"]: line for line in preview["an_lines"]}
        self.assertEqual(codes["131"]["credit"], "500")
        self.assertEqual(preview["an_debit"], preview["an_credit"])

    def test_rejects_unbalanced(self):
        preview = preview_opening(
            self.company,
            [
                {"code": "411", "debit": "1000", "credit": "0"},
                {"code": "401", "debit": "0", "credit": "800"},
            ],
        )
        self.assertFalse(preview["ok"])

    def test_skips_class_9(self):
        preview = preview_opening(
            self.company,
            [
                {"code": "411", "debit": "100", "credit": "0"},
                {"code": "401", "debit": "0", "credit": "100"},
                {"code": "9062", "debit": "50", "credit": "0"},
            ],
        )
        self.assertTrue(preview["ok"])
        self.assertTrue(any("Classe 9" in item for item in preview["warnings"]))

    def test_post_sets_january_and_prior_december(self):
        result = post_opening(
            self.company,
            self.exercise,
            None,
            [
                {"code": "411", "debit": "2500", "credit": "0"},
                {"code": "401", "debit": "0", "credit": "2500"},
                {"code": "701", "debit": "0", "credit": "4000"},
                {"code": "605", "debit": "4000", "credit": "0"},
            ],
        )
        self.assertTrue(result["posted"])
        entry = Entry.objects.get(id=result["entry_id"])
        self.assertEqual(entry.source, "opening")
        january = self.exercise.periods.get(month=1)
        rows = {row["code"]: row for row in trial_balance(self.company, january)}
        self.assertEqual(rows["411"]["close_debit"], Decimal("2500"))
        self.assertEqual(rows["411"]["open_debit"], Decimal("0"))
        self.assertEqual(rows["411"]["mov_debit"], Decimal("2500"))
        prior = Exercise.objects.get(company=self.company, year=2025)
        december = prior.periods.get(month=12)
        snap411 = BalanceSnapshot.objects.get(period=december, account=self.acc411)
        self.assertEqual(snap411.open_debit, Decimal("2500"))
        self.assertEqual(snap411.mov_debit, Decimal("0"))
        statements = build_statements(self.company, january)
        self.assertEqual(statements["comparative_year"], 2025)
        with self.assertRaises(HttpError):
            post_opening(
                self.company,
                self.exercise,
                None,
                [
                    {"code": "411", "debit": "2500", "credit": "0"},
                    {"code": "401", "debit": "0", "credit": "2500"},
                ],
            )
