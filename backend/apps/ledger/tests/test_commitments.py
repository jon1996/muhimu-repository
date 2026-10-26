from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.commitments import note1_from_items


class Note1Tests(TestCase):
    def test_groups_given_and_received(self):
        text = note1_from_items(
            [
                {"kind": "mortgage", "side": "given", "amount": Decimal("5000000")},
                {"kind": "guarantee", "side": "given", "amount": Decimal("200000")},
                {"kind": "pledge", "side": "received", "amount": Decimal("1000000")},
            ]
        )
        self.assertIn("Donnés :", text)
        self.assertIn("Hypothèque 5000000", text)
        self.assertIn("Caution / aval 200000", text)
        self.assertIn("Reçus :", text)
        self.assertIn("Nantissement 1000000", text)

    def test_empty(self):
        self.assertEqual(note1_from_items([]), "")
        self.assertEqual(note1_from_items([{"kind": "other", "side": "given", "amount": Decimal("0")}]), "")
