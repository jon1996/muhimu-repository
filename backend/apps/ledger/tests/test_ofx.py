from datetime import date
from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.ofx import parse_ofx, parse_ofx_date


SGML = b"""OFXHEADER:100
DATA:OFXSGML
VERSION:102
CHARSET:ISO-8859-1

<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<DTSTART>20260101
<DTEND>20260131
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260115
<TRNAMT>12000
<FITID>IN-001
<NAME>VIREMENT CLIENT
<MEMO>Facture 12
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260120
<TRNAMT>-5000
<FITID>OUT-001
<NAME>PRELEVEMENT
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>70000
<DTASOF>20260131
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""

UNSIGNED = b"""<OFX>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260301
<TRNAMT>2500
<FITID>D1
<NAME>CHEQUE
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260302
<TRNAMT>8000
<FITID>C1
<NAME>DEPOT
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>10000
<DTASOF>20260302
</LEDGERBAL>
</OFX>
"""

XML = b"""<?xml version="1.0"?>
<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>CREDIT</TRNTYPE>
            <DTPOSTED>20260410</DTPOSTED>
            <TRNAMT>1500.00</TRNAMT>
            <FITID>X1</FITID>
            <NAME>VIREMENT</NAME>
          </STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL>
          <BALAMT>1500.00</BALAMT>
          <DTASOF>20260410</DTASOF>
        </LEDGERBAL>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
"""


class OfxParseTests(TestCase):
    def test_sgml_signed_amounts(self):
        parsed = parse_ofx(SGML)
        self.assertEqual(parsed["as_of"], date(2026, 1, 31))
        self.assertEqual(parsed["balance"], Decimal("70000"))
        self.assertEqual(len(parsed["lines"]), 2)
        inflow, outflow = parsed["lines"]
        self.assertEqual(inflow["bank_credit"], Decimal("12000"))
        self.assertEqual(inflow["bank_debit"], Decimal("0"))
        self.assertEqual(inflow["label"], "VIREMENT CLIENT — Facture 12")
        self.assertEqual(outflow["bank_debit"], Decimal("5000"))
        self.assertEqual(outflow["external_id"], "OUT-001")

    def test_unsigned_uses_trntype(self):
        parsed = parse_ofx(UNSIGNED)
        debit, credit = parsed["lines"]
        self.assertEqual(debit["bank_debit"], Decimal("2500"))
        self.assertEqual(credit["bank_credit"], Decimal("8000"))

    def test_xml(self):
        parsed = parse_ofx(XML)
        self.assertEqual(parsed["as_of"], date(2026, 4, 10))
        self.assertEqual(parsed["lines"][0]["bank_credit"], Decimal("1500.00"))

    def test_date(self):
        self.assertEqual(parse_ofx_date("20260115"), date(2026, 1, 15))
        self.assertEqual(parse_ofx_date("20260115120000"), date(2026, 1, 15))
        self.assertIsNone(parse_ofx_date("abc"))
