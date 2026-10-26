"""États membres OHADA et devise légale de tenue des comptes.

17 membres : UEMOA (XOF), CEMAC (XAF), Comores (KMF), RDC (CDF), Guinée (GNF).
Décimales ISO 4217 : XOF/XAF/KMF/GNF = 0 ; CDF = 2.
"""

from __future__ import annotations

# (ISO 3166-1 alpha-2, libellé FR, ISO 4217)
OHADA_MEMBERS: tuple[tuple[str, str, str], ...] = (
    ("BJ", "Bénin", "XOF"),
    ("BF", "Burkina Faso", "XOF"),
    ("CM", "Cameroun", "XAF"),
    ("CF", "Centrafrique", "XAF"),
    ("TD", "Tchad", "XAF"),
    ("KM", "Comores", "KMF"),
    ("CG", "Congo", "XAF"),
    ("CD", "RDC", "CDF"),
    ("CI", "Côte d’Ivoire", "XOF"),
    ("GQ", "Guinée équatoriale", "XAF"),
    ("GA", "Gabon", "XAF"),
    ("GN", "Guinée", "GNF"),
    ("GW", "Guinée-Bissau", "XOF"),
    ("ML", "Mali", "XOF"),
    ("NE", "Niger", "XOF"),
    ("SN", "Sénégal", "XOF"),
    ("TG", "Togo", "XOF"),
)

OHADA_COUNTRIES = {code: name for code, name, _currency in OHADA_MEMBERS}
OHADA_CURRENCIES = {code: currency for code, _name, currency in OHADA_MEMBERS}
FUNCTIONAL_CURRENCIES = frozenset(OHADA_CURRENCIES.values())
ZERO_DECIMAL_CURRENCIES = frozenset({"XOF", "XAF", "KMF", "GNF"})


class UnknownOhadaCountry(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Pays invalide : {code or 'vide'} n’est pas un État membre OHADA.")


def country_label(code: str) -> str:
    code = (code or "").upper()
    return OHADA_COUNTRIES.get(code, code)


def currency_for_country(code: str) -> str | None:
    return OHADA_CURRENCIES.get((code or "").upper())


def resolve_country_currency(code: str) -> tuple[str, str]:
    country = (code or "").upper()[:2]
    currency = OHADA_CURRENCIES.get(country)
    if not currency:
        raise UnknownOhadaCountry(country)
    return country, currency
