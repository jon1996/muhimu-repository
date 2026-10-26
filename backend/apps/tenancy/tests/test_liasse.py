from types import SimpleNamespace
from unittest import TestCase

from apps.tenancy.liasse import country_label, identity_missing_fields, note36_text


def company(**overrides):
    base = dict(
        legal_form="sarl",
        tax_regime="reel_normal",
        country_code="CI",
        naema_code="G460000",
        control_kind="private_national",
        establishments_domestic=1,
        establishments_foreign=0,
        distinct_branch_accounts=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class CountryLabelTests(TestCase):
    def test_known_ohada_country(self):
        self.assertIn("Ivoire", country_label("CI"))

    def test_unknown_code_passthrough(self):
        self.assertEqual(country_label("ZZ"), "ZZ")


class Note36Tests(TestCase):
    def test_horizon_like_identity(self):
        text = note36_text(company())
        self.assertIn("forme SARL", text)
        self.assertIn("régime fiscal Réel normal", text)
        self.assertIn("pays Côte", text)
        self.assertIn("NAEMA G460000", text)
        self.assertIn("contrôle Privé national", text)
        self.assertIn("établissements 1 dans le pays", text)
        self.assertNotIn("hors pays", text)
        self.assertNotIn("comptabilité distincte", text)

    def test_foreign_establishments_and_branch_accounts(self):
        text = note36_text(
            company(
                establishments_domestic=2,
                establishments_foreign=1,
                distinct_branch_accounts=True,
            )
        )
        self.assertIn("établissements 2 dans le pays / 1 hors pays", text)
        self.assertIn("comptabilité distincte par établissement", text)

    def test_empty_company_has_only_country_and_establishments(self):
        text = note36_text(
            company(
                legal_form="",
                tax_regime="",
                naema_code="",
                control_kind="",
                country_code="",
                establishments_domestic=0,
                establishments_foreign=0,
            )
        )
        self.assertEqual(text, "")


class IdentityCompleteTests(TestCase):
    def test_blank_company_is_incomplete(self):
        missing = identity_missing_fields(
            company(
                legal_name="",
                address="",
                city="",
                rccm="",
                tax_id="",
                legal_form="",
                tax_regime="",
            ),
            officers=[],
        )
        self.assertIn("legal_name", missing)
        self.assertIn("rccm", missing)
        self.assertIn("tax_id", missing)
        self.assertIn("officers", missing)

    def test_required_identity_and_officer(self):
        missing = identity_missing_fields(
            company(
                legal_name="SARL Soleil",
                address="12 rue du Commerce",
                city="Abidjan",
                rccm="CI-ABJ-2026-B-1",
                tax_id="CI0001",
                legal_form="sarl",
                tax_regime="reel_normal",
            ),
            officers=[{"id": "1"}],
        )
        self.assertEqual(missing, [])
