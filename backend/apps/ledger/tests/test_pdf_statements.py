from unittest import TestCase

from apps.ledger.money import format_amount_fr
from apps.ledger.services.notes_sn import DEFAULT_CONFORMITY
from apps.ledger.services.pdf_statements import pdf_filename, render_statements_pdf
from apps.ledger.services.sn_map import build_bilan, build_compte_resultat, build_tft
from apps.ledger.tests.test_sn_map import row


def _payload() -> dict:
    rows = [
        row("211", debit=100),
        row("2811", credit=10),
        row("411", debit=50),
        row("512", debit=20),
        row("101", credit=100),
        row("401", credit=60),
        row("701", credit=200),
        row("605", debit=80),
        row("661", debit=40),
    ]
    prior = [row("411", debit=30), row("101", credit=30), row("701", credit=90)]
    bilan, bilan_n, bilan_p = build_bilan(rows, prior)
    result, cr_n, cr_p = build_compte_resultat(rows, prior)
    tft = build_tft(rows, prior, cr_n, cr_p, bilan_n, bilan_p)
    return {
        "exercise_year": 2026,
        "period_label": "2026-12",
        "comparative_year": 2025,
        "going_concern": True,
        "arrete_due_on": "2027-04-30",
        "ago_due_on": "2027-06-30",
        "entity": {
            "name": "SARL Horizon",
            "legal_name": "SARL Horizon",
            "currency_code": "XOF",
            "regime_label": "Systeme Normal",
            "starts_on": "2026-01-01",
            "ends_on": "2026-12-31",
        },
        "bilan": bilan,
        "result": result,
        "tft": tft,
        "notes": [
            {
                "number": 2,
                "title": "Regles et methodes comptables",
                "status": "A",
                "required": True,
                "body": "",
                "conformity": DEFAULT_CONFORMITY,
                "methods": "Cout historique.",
                "derogations": "",
                "extra": "Aucune reserve.",
                "computed": "",
            },
            {
                "number": 5,
                "title": "Actif circulant HAO",
                "status": "NA",
                "required": False,
                "body": "Ne doit pas apparaitre en detail.",
                "conformity": "",
                "methods": "",
                "derogations": "",
                "extra": "",
                "computed": "",
            },
            {
                "number": 11,
                "title": "Disponibilites",
                "status": "A",
                "required": False,
                "body": "Caisse et banques.",
                "conformity": "",
                "methods": "",
                "derogations": "",
                "extra": "",
                "computed": "Banques 52 : 20",
            },
        ],
    }


class FormatAmountFrTests(TestCase):
    def test_xof_thousands(self):
        self.assertEqual(format_amount_fr("1234567", "XOF"), "1 234 567")
        self.assertEqual(format_amount_fr("-40", "XOF"), "-40")

    def test_eur_decimals(self):
        self.assertEqual(format_amount_fr("1234.5", "EUR"), "1 234,50")

    def test_kmf_and_gnf_zero_decimals(self):
        self.assertEqual(format_amount_fr("1234567", "KMF"), "1 234 567")
        self.assertEqual(format_amount_fr("1234567", "GNF"), "1 234 567")

    def test_cdf_two_decimals(self):
        self.assertEqual(format_amount_fr("1234.5", "CDF"), "1 234,50")


class StatementsPdfTests(TestCase):
    def test_liasse_is_pdf_with_three_statements(self):
        pdf = render_statements_pdf(_payload(), "liasse")
        self.assertTrue(pdf.startswith(b"%PDF"))
        text = pdf.decode("latin-1", errors="ignore")
        self.assertIn("BILAN", text.upper())
        self.assertIn("Compte de resultat", text)
        self.assertIn("Tableau des flux de tresorerie", text)
        self.assertIn("Notes annexes", text)
        self.assertIn("SARL Horizon", text)
        self.assertIn("BZ", text)
        self.assertIn("SYSCOHADA", text)

    def test_kind_filters_pages(self):
        payload = _payload()
        bilan = render_statements_pdf(payload, "bilan")
        result = render_statements_pdf(payload, "result")
        tft = render_statements_pdf(payload, "tft")
        notes = render_statements_pdf(payload, "notes")
        liasse = render_statements_pdf(payload, "liasse")
        self.assertGreater(len(liasse), len(bilan))
        self.assertIn(b"Actif", bilan)
        self.assertNotIn(b"Marge commerciale", bilan)
        self.assertIn(b"Marge commerciale", result)
        self.assertIn(b"CAFG", tft)
        self.assertIn(b"Notes annexes", notes)
        self.assertNotIn(b"Marge commerciale", notes)

    def test_notes_join_status_a_only(self):
        pdf = render_statements_pdf(_payload(), "notes")
        text = pdf.decode("latin-1", errors="ignore")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("Note 2", text)
        self.assertIn("en cours de validation", text.lower())
        self.assertIn("DOCUMENT DE TEST", text.upper())
        self.assertIn("Cout historique", text)
        self.assertIn("Note 11", text)
        self.assertIn("Banques 52", text)
        self.assertIn("Caisse et banques", text)
        self.assertIn("Actif circulant HAO", text)
        self.assertNotIn("Ne doit pas apparaitre en detail", text)

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            render_statements_pdf(_payload(), "unknown")

    def test_filename(self):
        self.assertEqual(pdf_filename(_payload(), "result"), "compte-de-resultat-2026.pdf")
        self.assertEqual(pdf_filename(_payload(), "liasse"), "liasse-sn-2026.pdf")
        self.assertEqual(pdf_filename(_payload(), "notes"), "notes-annexes-2026.pdf")
        smt = {**_payload(), "regime": "smt"}
        self.assertEqual(pdf_filename(smt, "liasse"), "liasse-smt-2026.pdf")
        self.assertEqual(pdf_filename(smt, "notes"), "notes-annexes-smt-2026.pdf")

    def test_smt_liasse_skips_compte_resultat(self):
        payload = {**_payload(), "regime": "smt"}
        pdf = render_statements_pdf(payload, "liasse")
        text = pdf.decode("latin-1", errors="ignore")
        self.assertIn("Liasse SMT", text)
        self.assertIn("Etat de tresorerie", text)
        self.assertIn("Notes annexes", text)
        self.assertNotIn("Compte de resultat", text)
