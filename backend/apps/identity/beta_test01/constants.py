from __future__ import annotations

from apps.identity.beta_test01 import ORG_SLUG, PROVISION_TAG

# Données 100 % fictives — PME OHADA (République du Congo, XAF).
ORG_NAME = "Démo BETA-TEST-01 — cabinet fictif OHADA (2 dossiers PME)"
COMPANY_MAIN = "SARL Fleuve Congo"
COMPANY_ISOL = "SARL Niari Logistique"

USER_SPECS = (
    ("beta-test.owner@beta-test.muhimu.local", "Mireille Okemba", "owner"),
    ("beta-test.comptable@beta-test.muhimu.local", "Jean-Baptiste Moukoko", "accountant"),
    ("beta-test.viewer@beta-test.muhimu.local", "Claire Ngoma", "viewer"),
    ("beta-test.isol@beta-test.muhimu.local", "Paul Isolation", "isol"),
)

THIRD_PARTIES = (
    ("CLI-FICT-01", "client", "Entreprise Liboko SARL (fictif)"),
    ("FOU-FICT-01", "supplier", "Fournitures Congo Est (fictif)"),
)

# Écriture principale 2026 (vente) — montants XAF.
SALE_AMOUNT = "1000000"
SALE_DEBIT_ACCOUNT = "411"
SALE_CREDIT_ACCOUNT = "701"

CLOSE_YEAR = 2025
OPERATIONS_YEAR = 2026

__all__ = [
    "PROVISION_TAG",
    "ORG_SLUG",
    "ORG_NAME",
    "COMPANY_MAIN",
    "COMPANY_ISOL",
    "USER_SPECS",
    "THIRD_PARTIES",
    "SALE_AMOUNT",
    "CLOSE_YEAR",
    "OPERATIONS_YEAR",
]
