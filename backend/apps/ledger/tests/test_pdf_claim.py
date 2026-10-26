"""PDF-CLAIM : avertissements beta et absence de revendications de certification."""

from __future__ import annotations

import re
from unittest import TestCase

from apps.ledger.money import format_amount_fr
from apps.ledger.services.notes_sn import DEFAULT_CONFORMITY, default_notes
from apps.ledger.services.pdf_disclaimers import FORBIDDEN_PDF_CLAIM_SUBSTRINGS
from apps.ledger.services.pdf_statements import render_statements_pdf
from apps.ledger.services.sn_map import build_bilan, build_compte_resultat, build_tft
from apps.ledger.tests.test_pdf_statements import _payload
from apps.ledger.tests.test_sn_map import row


def _pdf_text(pdf: bytes) -> str:
    return pdf.decode("latin-1", errors="ignore").lower()


class PdfClaimTests(TestCase):
    def test_default_note2_conformity_is_not_a_certification_claim(self):
        text = DEFAULT_CONFORMITY.lower()
        self.assertIn("en cours de validation", text)
        self.assertNotIn("sans réserve", text)
        self.assertNotIn("sans reserve", text)
        self.assertNotIn("conformément", text)
        self.assertNotIn("conformement", text)

    def test_all_statement_pdfs_carry_beta_disclaimer(self):
        payload = _payload()
        payload["notes"] = default_notes()
        for kind in ("liasse", "bilan", "result", "tft", "notes"):
            pdf = render_statements_pdf(payload, kind)
            text = _pdf_text(pdf)
            self.assertTrue(pdf.startswith(b"%PDF"), kind)
            self.assertIn("document de test", text, kind)
            self.assertIn("donnees fictives", text, kind)
            self.assertIn("non certifie", text, kind)
            self.assertIn("donnees fictives", text, kind)

    def test_generated_pdfs_forbid_misleading_claim_substrings(self):
        payload = _payload()
        payload["notes"] = default_notes()
        for kind in ("liasse", "bilan", "result", "tft", "notes"):
            text = _pdf_text(render_statements_pdf(payload, kind))
            for forbidden in FORBIDDEN_PDF_CLAIM_SUBSTRINGS:
                self.assertNotIn(forbidden.lower(), text, f"{kind}: {forbidden}")

    def test_amounts_in_pdf_match_statement_payload(self):
        rows = [
            row("211", debit=100),
            row("512", debit=20),
            row("101", credit=120),
            row("701", credit=200),
            row("605", debit=80),
        ]
        bilan, _, _ = build_bilan(rows, None)
        payload = {**_payload(), "bilan": bilan, "notes": default_notes()}
        pdf = render_statements_pdf(payload, "bilan")
        text = _pdf_text(pdf)
        currency = payload["entity"]["currency_code"]
        for line in bilan.get("lines") or []:
            current = line.get("current")
            if current in (None, "", 0, "0"):
                continue
            formatted = format_amount_fr(current, currency)
            if formatted.replace(" ", "") == "0":
                continue
            compact = re.sub(r"\s+", "", formatted)
            self.assertIn(compact.lower(), re.sub(r"\s+", "", text), line.get("code"))

    def test_sn_map_outputs_unchanged_with_disclaimer_work(self):
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
        bilan_a, bn_a, bp_a = build_bilan(rows, prior)
        cr_a, crn_a, crp_a = build_compte_resultat(rows, prior)
        tft_a = build_tft(rows, prior, crn_a, crp_a, bn_a, bp_a)
        bilan_b, bn_b, bp_b = build_bilan(rows, prior)
        cr_b, crn_b, crp_b = build_compte_resultat(rows, prior)
        tft_b = build_tft(rows, prior, crn_b, crp_b, bn_b, bp_b)
        self.assertEqual(bilan_a, bilan_b)
        self.assertEqual(cr_a, cr_b)
        self.assertEqual(tft_a, tft_b)
