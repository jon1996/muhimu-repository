from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.sn_map import (
    bilan_amounts,
    build_bilan,
    build_compte_resultat,
    build_tft,
    cafg,
    cr_amounts,
    matches,
)


def row(code: str, debit=0, credit=0, mov_d=0, mov_c=0) -> dict:
    return {
        "code": code,
        "close_debit": Decimal(str(debit)),
        "close_credit": Decimal(str(credit)),
        "mov_debit": Decimal(str(mov_d)),
        "mov_credit": Decimal(str(mov_c)),
        "open_debit": Decimal("0"),
        "open_credit": Decimal("0"),
    }


def net(amounts, code: str) -> Decimal:
    return amounts[code].net


class MatchesTests(TestCase):
    def test_2181_is_ae_not_ah(self):
        self.assertTrue(matches("2181", ("211", "2181", "2191")))
        self.assertFalse(matches("2181", ("217", "218", "219"), ("2181", "2191", "2193")))

    def test_28181_fraction_is_ae_contra(self):
        self.assertTrue(matches("28181", ("2811", "28181", "2911", "29181", "29191")))
        self.assertFalse(
            matches("28181", ("2817", "2818", "2917", "2918", "2919"), ("28181", "29181", "29191", "29193"))
        )

    def test_2818_residual_is_ah(self):
        self.assertTrue(matches("28182", ("2817", "2818", "2917", "2918", "2919"), ("28181", "29181", "29191", "29193")))
        self.assertFalse(matches("28182", ("2811", "28181")))


class BilanMappingTests(TestCase):
    def test_incorporeal_and_transport_split(self):
        amounts = bilan_amounts(
            [
                row("211", debit=100),
                row("2181", debit=40),
                row("2182", debit=25),
                row("216", debit=80),
                row("2811", credit=10),
                row("241", debit=200),
                row("245", debit=50),
                row("2495", debit=15),
            ]
        )
        self.assertEqual(net(amounts, "AE"), Decimal("130"))  # 100+40-10
        self.assertEqual(net(amounts, "AH"), Decimal("25"))
        self.assertEqual(net(amounts, "AG"), Decimal("80"))
        self.assertEqual(net(amounts, "AM"), Decimal("200"))
        self.assertEqual(net(amounts, "AN"), Decimal("65"))

    def test_185_and_class4_by_sign(self):
        amounts = bilan_amounts(
            [
                row("185", debit=30),
                row("421", debit=20),
                row("431", credit=15),
                row("401", credit=70),
                row("4091", debit=12),
                row("478", debit=8),
                row("479", credit=5),
                row("4998", credit=9),
                row("4991", credit=4),
            ]
        )
        self.assertEqual(net(amounts, "BJ"), Decimal("50"))
        self.assertEqual(net(amounts, "DK"), Decimal("15"))
        self.assertEqual(net(amounts, "DJ"), Decimal("70"))
        self.assertEqual(net(amounts, "BH"), Decimal("12"))
        self.assertEqual(net(amounts, "BU"), Decimal("8"))
        self.assertEqual(net(amounts, "DV"), Decimal("5"))
        self.assertEqual(net(amounts, "DH"), Decimal("9"))
        self.assertEqual(net(amounts, "DN"), Decimal("4"))

    def test_185_credit_goes_to_dm_not_bj(self):
        amounts = bilan_amounts([row("185", credit=40)])
        self.assertEqual(net(amounts, "BJ"), Decimal("0"))
        self.assertEqual(net(amounts, "DM"), Decimal("40"))

    def test_cb_minus_and_cj_signed(self):
        amounts = bilan_amounts(
            [
                row("1013", credit=1000),
                row("109", debit=200),
                row("1291", debit=50),
                row("139", debit=30),
                row("132", credit=99),
            ]
        )
        self.assertEqual(net(amounts, "CA"), Decimal("1000"))
        self.assertEqual(net(amounts, "CB"), Decimal("-200"))
        self.assertEqual(net(amounts, "CH"), Decimal("-50"))
        self.assertEqual(net(amounts, "CJ"), Decimal("-30"))

    def test_balanced_cash_and_capital(self):
        payload, current, _prior = build_bilan(
            [row("5211", debit=800), row("1013", credit=800)],
            [],
        )
        self.assertEqual(current["BZ"].net, current["DZ"].net)
        self.assertTrue(payload["balanced"])
        codes = [line["code"] for line in payload["actif"]]
        self.assertIn("AE", codes)
        self.assertIn("BZ", codes)


class CompteResultatTests(TestCase):
    def test_official_line_composition(self):
        values = cr_amounts(
            [
                row("701", credit=1000),
                row("702", credit=400),
                row("705", credit=100),
                row("601", debit=300),
                row("6031", credit=20),
                row("621", debit=50),
                row("631", debit=10),
                row("641", debit=25),
                row("721", credit=80),
                row("736", credit=15),
            ]
        )
        self.assertEqual(values["TA"], Decimal("1000"))
        self.assertEqual(values["TB"], Decimal("400"))
        self.assertEqual(values["TC"], Decimal("100"))
        self.assertEqual(values["RA"], Decimal("-300"))
        self.assertEqual(values["RB"], Decimal("20"))
        self.assertEqual(values["RH"], Decimal("-60"))
        self.assertEqual(values["RI"], Decimal("-25"))
        self.assertEqual(values["TF"], Decimal("80"))
        self.assertEqual(values["TE"], Decimal("15"))
        self.assertEqual(values["XA"], Decimal("720"))
        self.assertEqual(values["XB"], Decimal("1500"))

    def test_ibe_label_when_ebe_negative(self):
        payload, current, _prior = build_compte_resultat(
            [row("601", debit=100), row("6611", debit=50)],
            [],
        )
        self.assertLess(current["XD"], Decimal("0"))
        xd = next(line for line in payload["lines"] if line["code"] == "XD")
        self.assertEqual(xd["label"], "Insuffisance brute d’exploitation")
        rh = next(line for line in payload["lines"] if line["code"] == "RH")
        self.assertEqual(rh["label"], "Services extérieurs")

    def test_participation_and_tax_after_hao(self):
        values = cr_amounts(
            [
                row("701", credit=200),
                row("821", credit=30),
                row("811", debit=10),
                row("871", debit=5),
                row("891", debit=8),
            ]
        )
        self.assertEqual(values["XH"], Decimal("20"))
        self.assertEqual(values["XI"], values["XG"] + values["XH"] + values["RQ"] + values["RS"])
        self.assertEqual(values["RQ"], Decimal("-5"))
        self.assertEqual(values["RS"], Decimal("-8"))


class TftTests(TestCase):
    def test_cafg_starts_from_ebe_not_net_income(self):
        rows = [
            row("701", credit=1000),
            row("6611", debit=200),
            row("6813", debit=80),
            row("6542", debit=15),
            row("7542", credit=25),
            row("771", credit=10),
            row("671", debit=40),
        ]
        cr = cr_amounts(rows)
        self.assertEqual(cr["XD"], Decimal("810"))
        self.assertEqual(cr["XI"], Decimal("700"))
        self.assertEqual(cafg(cr, rows), Decimal("770"))

    def test_za_and_operational_codes(self):
        current_rows = [
            row("5211", debit=300, mov_d=300),
            row("1013", credit=500, mov_c=200),
            row("311", debit=200, mov_d=80),
        ]
        prior_rows = [
            row("5211", debit=120),
            row("1013", credit=300),
            row("311", debit=120),
        ]
        _bilan, bilan_n, bilan_p = build_bilan(current_rows, prior_rows)
        _result, cr_n, cr_p = build_compte_resultat(current_rows, prior_rows)
        tft = build_tft(current_rows, prior_rows, cr_n, cr_p, bilan_n, bilan_p)
        codes = [line["code"] for line in tft["lines"]]
        self.assertEqual(codes[:6], ["ZA", "FA", "FB", "FC", "FD", "FE"])
        za = next(line for line in tft["lines"] if line["code"] == "ZA")
        fc = next(line for line in tft["lines"] if line["code"] == "FC")
        self.assertEqual(za["current"], "120")
        self.assertEqual(fc["current"], "-80")

    def test_fe_excludes_immo_suppliers(self):
        current_rows = [
            row("401", credit=100),
            row("4812", credit=40),
            row("5211", debit=140),
        ]
        prior_rows = [
            row("401", credit=70),
            row("4812", credit=10),
            row("5211", debit=80),
        ]
        _bilan, bilan_n, bilan_p = build_bilan(current_rows, prior_rows)
        _result, cr_n, cr_p = build_compte_resultat(current_rows, prior_rows)
        tft = build_tft(current_rows, prior_rows, cr_n, cr_p, bilan_n, bilan_p)
        fe = next(line for line in tft["lines"] if line["code"] == "FE")
        self.assertEqual(fe["current"], "30")

    def test_investment_register_overrides_class2_movements(self):
        current_rows = [
            row("211", debit=80, mov_d=80),
            row("244", debit=300, mov_d=300),
            row("5211", debit=100),
        ]
        prior_rows = [row("5211", debit=100)]
        _bilan, bilan_n, bilan_p = build_bilan(current_rows, prior_rows)
        _result, cr_n, cr_p = build_compte_resultat(current_rows, prior_rows)
        tft = build_tft(
            current_rows,
            prior_rows,
            cr_n,
            cr_p,
            bilan_n,
            bilan_p,
            investment={"ff": Decimal("-50"), "fg": Decimal("-200"), "fh": Decimal("-10")},
        )
        by_code = {line["code"]: line["current"] for line in tft["lines"]}
        self.assertEqual(by_code["FF"], "-50")
        self.assertEqual(by_code["FG"], "-200")
        self.assertEqual(by_code["FH"], "-10")

    def test_dividends_feed_fn(self):
        current_rows = [row("5211", debit=100)]
        prior_rows = [row("5211", debit=100)]
        _bilan, bilan_n, bilan_p = build_bilan(current_rows, prior_rows)
        _result, cr_n, cr_p = build_compte_resultat(current_rows, prior_rows)
        tft = build_tft(
            current_rows,
            prior_rows,
            cr_n,
            cr_p,
            bilan_n,
            bilan_p,
            dividends=Decimal("-40000"),
        )
        fn = next(line for line in tft["lines"] if line["code"] == "FN")
        self.assertEqual(fn["current"], "-40000")


class AnalysisAndNotesTests(TestCase):
    def test_fr_and_tn(self):
        from apps.ledger.services.sn_map import financial_analysis

        _payload, current, prior = build_bilan(
            [row("211", debit=400), row("5211", debit=600), row("1013", credit=1000)],
            [row("211", debit=400), row("5211", debit=500), row("1013", credit=900)],
        )
        analysis = financial_analysis(current, prior)
        self.assertEqual(analysis["fr"]["current"], "600")
        self.assertEqual(analysis["tn"]["current"], "600")
        self.assertEqual(analysis["bfe"]["current"], "0")

    def test_placement_subline_does_not_inflate_totals(self):
        amounts = bilan_amounts([row("2281", debit=50), row("2315", debit=80)])
        self.assertEqual(net(amounts, "AJ_P"), Decimal("50"))
        self.assertEqual(net(amounts, "AK_P"), Decimal("80"))
        self.assertEqual(net(amounts, "AJ"), Decimal("50"))
        self.assertEqual(net(amounts, "AZ"), Decimal("130"))

    def test_note_2_always_present_and_legacy_text_goes_to_extra(self):
        from apps.ledger.services.notes_sn import parse_notes

        notes = parse_notes("Méthode FIFO sur les stocks.")
        self.assertEqual(len(notes), 36)
        note2 = notes[1]
        self.assertEqual(note2["number"], 2)
        self.assertEqual(note2["status"], "A")
        self.assertEqual(note2["extra"], "Méthode FIFO sur les stocks.")
        self.assertTrue(note2["conformity"])
        self.assertEqual(notes[0]["status"], "NA")

