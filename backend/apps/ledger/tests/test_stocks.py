from decimal import Decimal
from unittest import TestCase

from ninja.errors import HttpError

from apps.ledger.services.stocks import (
    account_net,
    family_label,
    infer_stock_code,
    is_stock_account,
    note7_text,
    variation_code,
)


class StockAccountTests(TestCase):
    def test_class_3_except_depreciation(self):
        self.assertTrue(is_stock_account("31"))
        self.assertTrue(is_stock_account("388"))
        self.assertFalse(is_stock_account("39"))
        self.assertFalse(is_stock_account("2181"))
        self.assertFalse(is_stock_account(""))

    def test_variation_codes(self):
        self.assertEqual(variation_code("31"), "6031")
        self.assertEqual(variation_code("311"), "6031")
        self.assertEqual(variation_code("32"), "6032")
        self.assertEqual(variation_code("33"), "6033")
        self.assertEqual(variation_code("38"), "6033")
        self.assertEqual(variation_code("34"), "734")
        self.assertEqual(variation_code("36"), "736")
        self.assertEqual(variation_code("37"), "737")
        with self.assertRaises(HttpError):
            variation_code("218")

    def test_family_label(self):
        self.assertEqual(family_label("311"), "Marchandises")

    def test_infer_code_from_free_text(self):
        self.assertEqual(infer_stock_code("compte 31"), "31")
        self.assertEqual(infer_stock_code("311 marchandises"), "311")
        self.assertIsNone(infer_stock_code("dotation 6813"))
        self.assertIsNone(infer_stock_code("39"))


class StockDeltaMathTests(TestCase):
    def test_book_net_from_trial_balance(self):
        rows = [
            {
                "account_id": "a1",
                "code": "31",
                "close_debit": Decimal("40000"),
                "close_credit": Decimal("0"),
            }
        ]
        self.assertEqual(account_net(rows, "a1"), Decimal("40000"))
        self.assertEqual(account_net(rows, "missing"), Decimal("0"))
        self.assertEqual(Decimal("50000") - account_net(rows, "a1"), Decimal("10000"))


class Note7Tests(TestCase):
    def test_clients_and_accrued_income(self):
        rows = [
            {"code": "411", "close_debit": Decimal("120000"), "close_credit": Decimal("0")},
            {"code": "416", "close_debit": Decimal("5000"), "close_credit": Decimal("0")},
            {"code": "418", "close_debit": Decimal("2000"), "close_credit": Decimal("0")},
            {"code": "419", "close_debit": Decimal("0"), "close_credit": Decimal("800")},
        ]
        text = note7_text(rows)
        self.assertIn("Clients 41 : 127000", text)
        self.assertIn("dont douteux 416 : 5000", text)
        self.assertIn("produits à recevoir 418 : 2000", text)
        self.assertNotIn("419", text)

    def test_empty_without_receivables(self):
        self.assertEqual(note7_text([{"code": "521", "close_debit": Decimal("10"), "close_credit": Decimal("0")}]), "")
