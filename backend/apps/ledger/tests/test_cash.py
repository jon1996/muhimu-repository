from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.cash import (
    contra_code,
    is_cash_account,
    note11_cash_from_items,
    posting_lines,
    variance_amount,
    variance_kind,
)


class CashAccountTests(TestCase):
    def test_class_57_only(self):
        self.assertTrue(is_cash_account("57"))
        self.assertTrue(is_cash_account("571"))
        self.assertTrue(is_cash_account("5711"))
        self.assertFalse(is_cash_account("52"))
        self.assertFalse(is_cash_account("521"))
        self.assertFalse(is_cash_account("591"))
        self.assertFalse(is_cash_account(""))


class VarianceTests(TestCase):
    def test_shortage_overage_balanced(self):
        self.assertEqual(variance_amount(Decimal("80"), Decimal("100")), Decimal("-20"))
        self.assertEqual(variance_kind(Decimal("-20")), "shortage")
        self.assertEqual(contra_code("shortage"), "6588")
        self.assertEqual(variance_kind(Decimal("15")), "overage")
        self.assertEqual(contra_code("overage"), "7588")
        self.assertEqual(variance_kind(Decimal("0")), "balanced")

    def test_shortage_credits_cash(self):
        lines = posting_lines("shortage", "cash", "charge", Decimal("20"), "Manquant")
        self.assertEqual(lines[0]["account_id"], "charge")
        self.assertEqual(lines[0]["debit"], "20")
        self.assertEqual(lines[1]["account_id"], "cash")
        self.assertEqual(lines[1]["credit"], "20")

    def test_overage_debits_cash(self):
        lines = posting_lines("overage", "cash", "income", Decimal("15"), "Surplus")
        self.assertEqual(lines[0]["account_id"], "cash")
        self.assertEqual(lines[0]["debit"], "15")
        self.assertEqual(lines[1]["account_id"], "income")
        self.assertEqual(lines[1]["credit"], "15")


class Note11CashTests(TestCase):
    def test_latest_count_text(self):
        text = note11_cash_from_items(
            [
                {
                    "account_code": "571",
                    "counted_on": "2026-09-04",
                    "physical_amount": Decimal("25000"),
                    "book_amount": Decimal("24800"),
                }
            ]
        )
        self.assertIn("contrôle 571 au 2026-09-04", text)
        self.assertIn("espèces 25000", text)
        self.assertIn("livre 24800", text)
        self.assertIn("surplus 200", text)

    def test_shortage_and_empty(self):
        text = note11_cash_from_items(
            [
                {
                    "account_code": "571",
                    "counted_on": "2026-08-31",
                    "physical_amount": Decimal("90"),
                    "book_amount": Decimal("100"),
                }
            ]
        )
        self.assertIn("manquant 10", text)
        self.assertEqual(note11_cash_from_items([]), "")
