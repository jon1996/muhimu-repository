from datetime import date
from decimal import Decimal
from unittest import TestCase as UnitTestCase

from apps.ledger.models import AccountingPeriod, Exercise, Journal, JournalType
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.services.smt_map import (
    SMT_THRESHOLDS,
    build_eligibility,
    build_situation,
    payment_post,
    receipt_post,
    situation_amounts,
)
from apps.ledger.services.statements import build_statements
from apps.ledger.tests.db import LedgerDbTestCase
from apps.ledger.tests.test_sn_map import row
from apps.tenancy.models import AccountingRegime, ActivityKind


class SmtMapUnitTests(UnitTestCase):
    def test_receipt_and_payment_posts(self):
        self.assertEqual(receipt_post("701"), "RA")
        self.assertEqual(receipt_post("411"), "RA")
        self.assertEqual(receipt_post("164"), "RE")
        self.assertEqual(payment_post("601"), "DA")
        self.assertEqual(payment_post("401"), "DA")
        self.assertEqual(payment_post("218"), "DF")
        self.assertEqual(payment_post("661"), "DB")

    def test_situation_totals(self):
        amounts = situation_amounts(
            [
                row("218", debit=80),
                row("31", debit=20),
                row("411", debit=15),
                row("571", debit=25),
                row("101", credit=90),
                row("401", credit=50),
            ]
        )
        self.assertEqual(amounts["IE"], Decimal("140"))
        self.assertEqual(amounts["PE"], Decimal("140"))
        situation = build_situation(
            [
                row("218", debit=80),
                row("571", debit=20),
                row("101", credit=100),
            ],
            [],
        )
        self.assertTrue(situation["balanced"])
        self.assertEqual(situation["actif"][0]["code"], "IA")

    def test_thresholds(self):
        class Co:
            accounting_regime = AccountingRegime.SMT
            activity_kind = ActivityKind.SERVICES

        over = build_eligibility(Co(), Decimal("30000001"))
        self.assertFalse(over["eligible"])
        self.assertIn("art. 13", over["warning"])
        under = build_eligibility(Co(), Decimal("1000000"))
        self.assertTrue(under["eligible"])
        self.assertEqual(under["threshold"], format(SMT_THRESHOLDS["services"], "f"))


class SmtEngineTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.company.accounting_regime = AccountingRegime.SMT
        self.company.activity_kind = ActivityKind.TRADE
        self.company.save(update_fields=["accounting_regime", "activity_kind"])
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
            code="BQ",
            name="Banque",
            type=JournalType.BANK,
        )
        self.acc571 = self.make_account("571", "Caisse")
        self.acc701 = self.make_account("701", "Ventes")
        self.acc601 = self.make_account("601", "Achats")
        self.acc101 = self.make_account("101", "Capital")

    def _post(self, lines, day=10):
        entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, day),
            value_date=date(2026, 1, day),
            description="SMT",
            document_ref="SMT-TEST",
            raw_lines=lines,
        )
        return post_entry(entry, None)

    def test_etat_tresorerie_from_cash(self):
        self._post(
            [
                {"account_id": str(self.acc571.id), "debit": "100000", "credit": "0"},
                {"account_id": str(self.acc701.id), "debit": "0", "credit": "100000"},
            ],
            day=5,
        )
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "40000", "credit": "0"},
                {"account_id": str(self.acc571.id), "debit": "0", "credit": "40000"},
            ],
            day=12,
        )
        payload = build_statements(self.company, self.period)
        self.assertEqual(payload["regime"], "smt")
        self.assertEqual(payload["bilan"]["actif"][0]["code"], "IA")
        posts = {line["code"]: line for line in payload["tft"]["lines"]}
        self.assertEqual(Decimal(posts["RA"]["current"]), Decimal("100000"))
        self.assertEqual(Decimal(posts["DA"]["current"]), Decimal("40000"))
        self.assertEqual(Decimal(posts["RG"]["current"]), Decimal("100000"))
        self.assertEqual(Decimal(posts["DI"]["current"]), Decimal("40000"))
        self.assertEqual(Decimal(posts["EA"]["current"]), Decimal("60000"))
        self.assertEqual(Decimal(posts["EC"]["current"]), Decimal("60000"))
        self.assertTrue(payload["smt"]["eligible"])
        self.assertEqual(payload["result"]["lines"], [])

    def test_sn_company_keeps_official_codes(self):
        self.company.accounting_regime = AccountingRegime.NORMAL
        self.company.save(update_fields=["accounting_regime"])
        self._post(
            [
                {"account_id": str(self.acc571.id), "debit": "10", "credit": "0"},
                {"account_id": str(self.acc101.id), "debit": "0", "credit": "10"},
            ]
        )
        payload = build_statements(self.company, self.period)
        self.assertEqual(payload["bilan"]["actif"][0]["code"], "AD")
        self.assertTrue(any(line["code"] == "XI" for line in payload["result"]["lines"]))
        self.assertIsNotNone(payload["analysis"])
