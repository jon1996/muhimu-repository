from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.esg import note35_from_item, note35_required, payroll_from_rows


class Note35Tests(TestCase):
    def test_empty(self):
        self.assertEqual(note35_from_item({}), "")
        self.assertFalse(note35_required(250))
        self.assertTrue(note35_required(251))

    def test_below_threshold(self):
        text = note35_from_item(
            {
                "headcount": 12,
                "hires": 3,
                "training": "2 jours par an",
                "waste": "tri sélectif",
            }
        )
        self.assertIn("Social : effectif 12 · embauches 3 · formation : 2 jours par an", text)
        self.assertIn("Environnement : déchets : tri sélectif", text)
        self.assertNotIn("Obligatoire", text)

    def test_required_incomplete(self):
        text = note35_from_item({"headcount": 260})
        self.assertIn("Obligatoire (effectif 260 > 250)", text)
        self.assertIn("fiche à compléter", text)

    def test_payroll(self):
        text = note35_from_item({"headcount": 10}, payroll=Decimal("8000000"))
        self.assertIn("masse salariale 8000000", text)

    def test_payroll_from_rows(self):
        total = payroll_from_rows(
            [
                {"code": "6611", "close_debit": Decimal("80"), "close_credit": Decimal("0")},
                {"code": "411", "close_debit": Decimal("10"), "close_credit": Decimal("0")},
            ]
        )
        self.assertEqual(total, Decimal("80"))
