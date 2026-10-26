from unittest import TestCase

from apps.tenancy.ohada import (
    FUNCTIONAL_CURRENCIES,
    OHADA_COUNTRIES,
    OHADA_MEMBERS,
    UnknownOhadaCountry,
    currency_for_country,
    resolve_country_currency,
)


class OhadaCurrencyMapTests(TestCase):
    def test_seventeen_members(self):
        self.assertEqual(len(OHADA_MEMBERS), 17)
        self.assertEqual(len(OHADA_COUNTRIES), 17)

    def test_uemoa_xof(self):
        for code in ("BJ", "BF", "CI", "GW", "ML", "NE", "SN", "TG"):
            self.assertEqual(currency_for_country(code), "XOF")

    def test_cemac_xaf(self):
        for code in ("CM", "CF", "TD", "CG", "GQ", "GA"):
            self.assertEqual(currency_for_country(code), "XAF")

    def test_non_cfa_members(self):
        self.assertEqual(currency_for_country("KM"), "KMF")
        self.assertEqual(currency_for_country("CD"), "CDF")
        self.assertEqual(currency_for_country("GN"), "GNF")

    def test_functional_set(self):
        self.assertEqual(FUNCTIONAL_CURRENCIES, {"XOF", "XAF", "KMF", "CDF", "GNF"})

    def test_resolve_rejects_unknown(self):
        with self.assertRaises(UnknownOhadaCountry):
            resolve_country_currency("FR")
        self.assertIsNone(currency_for_country("ZZ"))
