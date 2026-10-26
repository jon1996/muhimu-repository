from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest import TestCase

from ninja.errors import HttpError

from apps.ledger.services.amortization import linear_charge
from apps.ledger.services.assets import suggest_contra_codes, validate_asset_payload


class LinearChargeTests(TestCase):
    def test_full_month_equals_monthly_quota(self):
        charge = linear_charge(
            cost=Decimal("120000"),
            residual=Decimal("0"),
            useful_life_months=60,
            in_service_on=date(2026, 1, 1),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            already_charged=Decimal("0"),
            currency="XOF",
        )
        self.assertEqual(charge, Decimal("2000"))

    def test_mid_month_prorata_from_in_service(self):
        charge = linear_charge(
            cost=Decimal("120000"),
            residual=Decimal("0"),
            useful_life_months=60,
            in_service_on=date(2026, 1, 16),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            already_charged=Decimal("0"),
            currency="XOF",
        )
        self.assertEqual(charge, Decimal("1032"))

    def test_land_zero_life_has_no_charge(self):
        charge = linear_charge(
            cost=Decimal("5000000"),
            residual=Decimal("0"),
            useful_life_months=0,
            in_service_on=date(2026, 1, 1),
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            already_charged=Decimal("0"),
            currency="XOF",
        )
        self.assertEqual(charge, Decimal("0"))

    def test_charge_capped_at_remaining_base(self):
        charge = linear_charge(
            cost=Decimal("120000"),
            residual=Decimal("0"),
            useful_life_months=60,
            in_service_on=date(2026, 1, 1),
            period_start=date(2030, 12, 1),
            period_end=date(2030, 12, 31),
            already_charged=Decimal("119500"),
            currency="XOF",
        )
        self.assertEqual(charge, Decimal("500"))


class SuggestAndValidateTests(TestCase):
    def test_suggest_contra_for_corporeal_and_incorporeal(self):
        self.assertEqual(suggest_contra_codes("2442"), ("28442", "6813"))
        self.assertEqual(suggest_contra_codes("2181"), ("28181", "6812"))

    def test_component_under_12_months_is_a_charge(self):
        company = SimpleNamespace(currency_code="XOF")
        with self.assertRaises(HttpError) as ctx:
            validate_asset_payload(
                company,
                {
                    "cost": "100000",
                    "residual_value": "0",
                    "useful_life_months": 6,
                    "kind": "component",
                    "asset_account_id": "unused",
                    "acquired_on": date(2026, 1, 1),
                    "in_service_on": date(2026, 1, 1),
                },
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("12 mois", str(ctx.exception))
