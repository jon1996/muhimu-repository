from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.bank_rec import (
    book_net,
    next_pointage_code,
    statement_as_book,
)


class SignTests(TestCase):
    def test_inflow_matches_book_debit(self):
        self.assertEqual(statement_as_book(Decimal("0"), Decimal("12000")), Decimal("12000"))
        self.assertEqual(book_net(Decimal("12000"), Decimal("0")), Decimal("12000"))

    def test_outflow_matches_book_credit(self):
        self.assertEqual(statement_as_book(Decimal("5000"), Decimal("0")), Decimal("-5000"))
        self.assertEqual(book_net(Decimal("0"), Decimal("5000")), Decimal("-5000"))

    def test_wrong_side_does_not_match(self):
        self.assertNotEqual(statement_as_book(Decimal("12000"), Decimal("0")), book_net(Decimal("12000"), Decimal("0")))


class PointageCodeTests(TestCase):
    def test_first_and_next(self):
        self.assertEqual(next_pointage_code([]), "P-0001")
        self.assertEqual(next_pointage_code(["P-0001", "L-0003", "P-0009"]), "P-0010")
