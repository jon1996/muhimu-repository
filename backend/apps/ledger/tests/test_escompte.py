from decimal import Decimal
from unittest import TestCase

from ninja.errors import HttpError

from apps.ledger.services.escompte import discount_net, liability_code


class DiscountMathTests(TestCase):
    def test_net_is_nominal_minus_agios(self):
        self.assertEqual(discount_net(Decimal("100000"), Decimal("2500")), Decimal("97500"))
        self.assertEqual(discount_net(Decimal("100000"), Decimal("0")), Decimal("100000"))

    def test_rejects_agios_above_nominal(self):
        with self.assertRaises(HttpError):
            discount_net(Decimal("100"), Decimal("101"))
        with self.assertRaises(HttpError):
            discount_net(Decimal("0"), Decimal("0"))
        with self.assertRaises(HttpError):
            discount_net(Decimal("100"), Decimal("-1"))

    def test_campaign_uses_564(self):
        self.assertEqual(liability_code(False), "565")
        self.assertEqual(liability_code(True), "564")

    def test_five_lines_balance(self):
        nominal = Decimal("100000")
        agios = Decimal("2500")
        net = discount_net(nominal, agios)
        self.assertEqual(nominal + net + agios, nominal + nominal)
