from decimal import Decimal
from unittest import TestCase

from apps.ledger.services.closing import restore_pnl_rows, suggest_legal_reserve
from apps.ledger.services.sn_map import cr_amounts


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


class LegalReserveTests(TestCase):
    def test_ten_percent_until_twenty_of_capital(self):
        self.assertEqual(
            suggest_legal_reserve(Decimal("100000"), Decimal("1000000"), Decimal("0")),
            Decimal("10000"),
        )
        self.assertEqual(
            suggest_legal_reserve(Decimal("100000"), Decimal("100000"), Decimal("20000")),
            Decimal("0"),
        )
        self.assertEqual(
            suggest_legal_reserve(Decimal("-5000"), Decimal("1000000"), Decimal("0")),
            Decimal("0"),
        )


class RestorePnlTests(TestCase):
    def test_restored_cr_matches_pre_close_result(self):
        before = [
            row("701", credit=250, mov_c=250),
            row("6611", debit=80, mov_d=80),
        ]
        after = [
            row("701", debit=250, credit=250, mov_d=250, mov_c=250),
            row("6611", debit=80, credit=80, mov_d=80, mov_c=80),
            row("131", credit=170),
        ]
        restored = restore_pnl_rows(
            after,
            [
                {"code": "701", "debit": Decimal("250"), "credit": Decimal("0")},
                {"code": "6611", "debit": Decimal("0"), "credit": Decimal("80")},
                {"code": "131", "debit": Decimal("0"), "credit": Decimal("170")},
            ],
        )
        self.assertEqual(cr_amounts(restored)["XI"], cr_amounts(before)["XI"])
        self.assertEqual(cr_amounts(restored)["XI"], Decimal("170"))
        by_code = {item["code"]: item for item in restored}
        self.assertEqual(by_code["131"]["close_credit"], Decimal("170"))
