from datetime import date
from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.lettering import account_root, age_text, classify_due, next_letter_code, note17_text
from apps.ledger.services.stocks import note7_text


def row(code: str, debit=0, credit=0) -> dict:
    return {
        "code": code,
        "close_debit": Decimal(str(debit)),
        "close_credit": Decimal(str(credit)),
    }


class LetterCodeTests(TestCase):
    def test_first_and_next(self):
        self.assertEqual(next_letter_code([]), "L-0001")
        self.assertEqual(next_letter_code(["L-0001", "A", "L-0007"]), "L-0008")

    def test_411_and_4118_share_root(self):
        self.assertEqual(account_root("411"), "411")
        self.assertEqual(account_root("4118"), "411")
        self.assertEqual(account_root("411-CLI-0001"), "411")
        self.assertNotEqual(account_root("401"), account_root("411"))


class SupplierNoteTests(TestCase):
    def test_note17_excludes_advances(self):
        text = note17_text(
            [
                row("401", credit=80),
                row("4091", debit=12),
                row("408", credit=20),
            ]
        )
        self.assertIn("Fournisseurs 40 : 100", text)
        self.assertNotIn("409", text)

    def test_empty_without_payables(self):
        self.assertEqual(note17_text([row("411", debit=50)]), "")


class ClientNoteStillWorks(TestCase):
    def test_note7_clients(self):
        text = note7_text(
            [
                {"code": "411", "close_debit": Decimal("10"), "close_credit": Decimal("0")},
                {"code": "419", "close_debit": Decimal("0"), "close_credit": Decimal("1")},
            ]
        )
        self.assertIn("Clients 41 : 10", text)


class DueAgingTests(TestCase):
    def test_classify_due(self):
        as_of = date(2026, 9, 1)
        self.assertEqual(classify_due(None, as_of), "within_year")
        self.assertEqual(classify_due(date(2026, 8, 31), as_of), "overdue")
        self.assertEqual(classify_due(date(2026, 9, 1), as_of), "within_year")
        self.assertEqual(classify_due(date(2027, 9, 1), as_of), "within_year")
        self.assertEqual(classify_due(date(2027, 9, 2), as_of), "beyond_year")

    def test_age_text(self):
        text = age_text(
            [
                {"due_on": date(2026, 1, 1), "debit": Decimal("100"), "credit": Decimal("0")},
                {"due_on": None, "debit": Decimal("50"), "credit": Decimal("0")},
                {"due_on": date(2028, 1, 1), "debit": Decimal("0"), "credit": Decimal("20")},
            ],
            date(2026, 9, 1),
        )
        self.assertIn("échu 100", text)
        self.assertIn("≤ 1 an 50", text)
        self.assertIn("> 1 an 20", text)
