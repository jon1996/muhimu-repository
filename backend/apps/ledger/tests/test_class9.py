from decimal import Decimal
from unittest import TestCase

from ninja.errors import HttpError

from apps.ledger.services.commitments import class9_accounts
from apps.ledger.services.posting import assert_double_entry
from apps.ledger.taxonomy import classify


class DummyAccount:
    def __init__(self, code: str):
        self.code = code


class Class9TaxonomyTests(TestCase):
    def test_family_and_sense(self):
        info = classify("9062")
        self.assertEqual(info["account_class"], "9")
        self.assertEqual(info["family"], "off_balance")
        self.assertEqual(info["sense"], "debit")
        self.assertEqual(info["statement"], "hors_bilan")
        self.assertEqual(classify("916")["sense"], "credit")
        self.assertEqual(classify("95")["family"], "off_balance")

    def test_mapping(self):
        self.assertEqual(class9_accounts("guarantee", "given"), ("9062", "916"))
        self.assertEqual(class9_accounts("mortgage", "received"), ("9023", "912"))
        self.assertEqual(class9_accounts("lease", "given"), ("9071", "916"))


class Class9IsolationTests(TestCase):
    def test_pure_class9_ok(self):
        assert_double_entry(
            [
                {"account": DummyAccount("9062"), "debit": Decimal("100"), "credit": Decimal("0")},
                {"account": DummyAccount("916"), "debit": Decimal("0"), "credit": Decimal("100")},
            ]
        )

    def test_mix_rejected(self):
        with self.assertRaises(HttpError) as ctx:
            assert_double_entry(
                [
                    {"account": DummyAccount("9062"), "debit": Decimal("100"), "credit": Decimal("0")},
                    {"account": DummyAccount("401"), "debit": Decimal("0"), "credit": Decimal("100")},
                ]
            )
        self.assertIn("classe 9", str(ctx.exception))
