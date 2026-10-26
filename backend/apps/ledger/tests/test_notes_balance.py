from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.notes_balance import (
    computed_balance_notes,
    computed_cr_notes,
    note8_text,
    note11_text,
    note12_text,
    note18_text,
    note20_text,
    note21_text,
    note22_text,
    note24_text,
    note27_text,
    note30_text,
    note32_text,
)


def row(code: str, debit=0, credit=0) -> dict:
    return {
        "code": code,
        "close_debit": Decimal(str(debit)),
        "close_credit": Decimal(str(credit)),
    }


class OtherReceivableNoteTests(TestCase):
    def test_note8_debit_balances_only(self):
        text = note8_text(
            [
                row("421", debit=20),
                row("431", credit=15),
                row("444", debit=8),
                row("185", debit=30),
                row("478", debit=8),
            ]
        )
        self.assertIn("Personnel 42 : 20", text)
        self.assertIn("État 44 : 8", text)
        self.assertIn("Comptes de liaison 185 : 30", text)
        self.assertNotIn("sociaux", text)
        self.assertNotIn("478", text)

    def test_note18_credit_balances_only(self):
        text = note18_text(
            [
                row("421", debit=20),
                row("431", credit=15),
                row("443", credit=40),
            ]
        )
        self.assertIn("Organismes sociaux 43 : 15", text)
        self.assertIn("État 44 : 40", text)
        self.assertNotIn("Personnel", text)

    def test_empty_without_class4_other(self):
        self.assertEqual(note8_text([row("411", debit=50)]), "")
        self.assertEqual(note18_text([row("401", credit=70)]), "")


class TreasuryNoteTests(TestCase):
    def test_note11_splits_bank_and_cash(self):
        text = note11_text([row("5211", debit=800), row("571", debit=25)])
        self.assertIn("Banques 52 : 800", text)
        self.assertIn("Caisse 57 : 25", text)

    def test_note20_overdraft_on_52(self):
        text = note20_text([row("521", credit=120), row("564", credit=30)])
        self.assertIn("Crédits d’escompte 564/565 (DQ) : 30", text)
        self.assertIn("Crédits de trésorerie 52/53/561/566 (DR) : 120", text)

    def test_note12_both_sides(self):
        text = note12_text([row("478", debit=8), row("479", credit=5)])
        self.assertIn("478 (BU) : 8", text)
        self.assertIn("479 (DV) : 5", text)


class DispatchTests(TestCase):
    def test_computed_map_skips_empty(self):
        notes = computed_balance_notes(
            [
                row("261", debit=100),
                row("5211", debit=50),
                row("1013", credit=150),
            ]
        )
        self.assertIn(4, notes)
        self.assertIn(11, notes)
        self.assertNotIn(18, notes)
        self.assertIn("Participations 26", notes[4])
        self.assertIn("Banques 52 : 50", notes[11])


class CompteResultatNoteTests(TestCase):
    def test_note21_includes_turnover(self):
        rows = [
            row("701", credit=1000),
            row("702", credit=400),
            row("705", credit=100),
            row("601", debit=300),
        ]
        text = note21_text(rows)
        self.assertIn("Ventes de marchandises (TA) : 1000", text)
        self.assertIn("Chiffre d’affaires (XB) : 1500", text)
        self.assertIn("Achats de marchandises (RA) : -300", note22_text(rows))
        self.assertIn("Production de l’exercice", note32_text(rows))
        notes = computed_cr_notes(rows)
        self.assertIn(21, notes)
        self.assertIn(22, notes)
        self.assertNotIn(27, notes)

    def test_note24_merges_62_and_63(self):
        self.assertIn("Services extérieurs (RH) : -60", note24_text([row("621", debit=50), row("631", debit=10)]))
        self.assertIn("Charges de personnel (RK) : -80", note27_text([row("6611", debit=80)]))
        hao = note30_text([row("821", credit=30), row("811", debit=10), row("891", debit=8)])
        self.assertIn("Résultat HAO (XH) : 20", hao)
        self.assertIn("Impôts sur le résultat (RS) : -8", hao)
