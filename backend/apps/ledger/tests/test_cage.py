from decimal import Decimal
from datetime import date
from unittest import TestCase as UnitTestCase

from ninja.errors import HttpError

from apps.ledger.models import (
    AccountingPeriod,
    CageReflection,
    CageSection,
    Entry,
    Exercise,
    Journal,
    JournalType,
)
from apps.ledger.services.cage import (
    allocate_cage,
    close_cage,
    create_section,
    net_to_reflect,
    reflect_entry,
    reflect_period,
    reflection_kind,
    reflection_pairs,
    section_code,
)
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase


class ReflectionMathTests(UnitTestCase):
    def test_kind_skips_class_8_and_4(self):
        self.assertEqual(reflection_kind("601"), "charge")
        self.assertEqual(reflection_kind("701"), "product")
        self.assertEqual(reflection_kind("81"), "")
        self.assertEqual(reflection_kind("411"), "")

    def test_net_charge_and_product(self):
        self.assertEqual(net_to_reflect("charge", Decimal("1000"), Decimal("0")), Decimal("1000"))
        self.assertEqual(net_to_reflect("charge", Decimal("0"), Decimal("1000")), Decimal("-1000"))
        self.assertEqual(net_to_reflect("product", Decimal("0"), Decimal("500")), Decimal("500"))
        self.assertEqual(net_to_reflect("product", Decimal("500"), Decimal("0")), Decimal("-500"))
        self.assertEqual(net_to_reflect("", Decimal("10"), Decimal("0")), Decimal("0"))

    def test_charge_pairs(self):
        lines = reflection_pairs("charge", Decimal("1000"), "95", "921")
        self.assertEqual(lines[0]["account_id"], "95")
        self.assertEqual(lines[0]["debit"], "1000")
        self.assertEqual(lines[1]["account_id"], "921")
        self.assertEqual(lines[1]["credit"], "1000")

    def test_charge_reversal_inverts(self):
        lines = reflection_pairs("charge", Decimal("-1000"), "95", "921")
        self.assertEqual(lines[0]["account_id"], "921")
        self.assertEqual(lines[0]["debit"], "1000")
        self.assertEqual(lines[1]["account_id"], "95")
        self.assertEqual(lines[1]["credit"], "1000")

    def test_product_pairs(self):
        lines = reflection_pairs("product", Decimal("500"), "95", "927")
        self.assertEqual(lines[0]["account_id"], "927")
        self.assertEqual(lines[0]["debit"], "500")
        self.assertEqual(lines[1]["account_id"], "95")
        self.assertEqual(lines[1]["credit"], "500")

    def test_product_reversal_inverts(self):
        lines = reflection_pairs("product", Decimal("-500"), "95", "927")
        self.assertEqual(lines[0]["account_id"], "95")
        self.assertEqual(lines[0]["debit"], "500")
        self.assertEqual(lines[1]["account_id"], "927")
        self.assertEqual(lines[1]["credit"], "500")

    def test_zero_is_empty(self):
        self.assertEqual(reflection_pairs("charge", Decimal("0"), "95", "921"), [])

    def test_section_code_sanitizes(self):
        self.assertEqual(section_code("prod"), "PROD")
        self.assertEqual(section_code("prod-1"), "PROD1")
        with self.assertRaises(HttpError):
            section_code("---")


class CageEngineTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        self.period = AccountingPeriod.objects.create(
            organization=self.org,
            company=self.company,
            exercise=self.exercise,
            year=2026,
            month=1,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        self.journal = Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.acc601 = self.make_account("601", "Achats")
        self.acc701 = self.make_account("701", "Ventes")
        self.section = create_section(self.company, {"code": "PROD", "label": "Production"})

    def _post(self, lines, description="Test"):
        entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description=description,
            document_ref="CAGE-TEST",
            raw_lines=lines,
        )
        return post_entry(entry, None)

    def test_first_section_is_default_and_opens_95(self):
        self.assertTrue(self.section.is_default)
        self.assertEqual(self.section.account.code, "95-PROD")
        self.assertTrue(self.section.account.is_postable)
        self.assertFalse(self.section.account.is_syscohada)

    def test_duplicate_section_rejected(self):
        with self.assertRaises(HttpError):
            create_section(self.company, {"code": "PROD", "label": "Autre"})

    def test_post_charge_reflects_once(self):
        entry = self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "1000", "credit": "0", "label": "Achat"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "1000", "label": "Fourn"},
            ]
        )
        reflection = CageReflection.objects.get(source_entry=entry)
        cage = reflection.cage_entry
        self.assertEqual(cage.source, "cage")
        codes = {line.account.code: (line.debit, line.credit) for line in cage.lines.all()}
        self.assertEqual(codes["95-PROD"], (Decimal("1000"), Decimal("0")))
        self.assertEqual(codes["921"], (Decimal("0"), Decimal("1000")))
        self.assertEqual(CageReflection.objects.filter(source_entry=entry).count(), 1)
        again = reflect_entry(entry, None)
        self.assertEqual(again.id, reflection.id)
        self.assertEqual(Entry.objects.filter(company=self.company, source="cage").count(), 1)

    def test_post_product_credits_section(self):
        entry = self._post(
            [
                {"account_id": str(self.acc411.id), "debit": "2000", "credit": "0", "label": "Client"},
                {"account_id": str(self.acc701.id), "debit": "0", "credit": "2000", "label": "Vente"},
            ]
        )
        cage = CageReflection.objects.get(source_entry=entry).cage_entry
        codes = {line.account.code: (line.debit, line.credit) for line in cage.lines.all()}
        self.assertEqual(codes["927"], (Decimal("2000"), Decimal("0")))
        self.assertEqual(codes["95-PROD"], (Decimal("0"), Decimal("2000")))

    def test_reflect_period_is_noop_the_second_time(self):
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "100", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "100"},
            ]
        )
        first = reflect_period(self.company, self.period, None)
        self.assertEqual(first["created"], 0)
        self.assertEqual(first["pending"], 0)
        self.assertEqual(len(first["results"]), 1)
        self.assertEqual(first["results"][0]["charges"], "100.00")
        self.assertEqual(first["results"][0]["result"], "-100.00")

    def test_class_8_is_not_reflected(self):
        acc81 = self.make_account("81", "HAO")
        acc82 = self.make_account("82", "Produits HAO")
        entry = self._post(
            [
                {"account_id": str(acc81.id), "debit": "50", "credit": "0"},
                {"account_id": str(acc82.id), "debit": "0", "credit": "50"},
            ]
        )
        self.assertFalse(CageReflection.objects.filter(source_entry=entry).exists())
        self.assertEqual(Entry.objects.filter(company=self.company, source="cage").count(), 0)

    def test_no_section_skips_auto_reflect(self):
        CageSection.objects.filter(company=self.company).update(is_active=False)
        entry = self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "10", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "10"},
            ]
        )
        self.assertFalse(CageReflection.objects.filter(source_entry=entry).exists())
        self.assertEqual(Entry.objects.filter(company=self.company, source="cage").count(), 0)

    def test_reflect_period_picks_up_entries_posted_before_section(self):
        CageSection.objects.filter(company=self.company).delete()
        entry = self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "80", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "80"},
            ]
        )
        self.assertFalse(CageReflection.objects.filter(source_entry=entry).exists())
        create_section(self.company, {"code": "ADMIN", "label": "Administration"})
        payload = reflect_period(self.company, self.period, None)
        self.assertEqual(payload["created"], 1)
        self.assertTrue(CageReflection.objects.filter(source_entry=entry).exists())

    def test_stock_in_moves_95_to_941(self):
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "400", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "400"},
            ]
        )
        panel = allocate_cage(
            self.company,
            self.period,
            None,
            {"section_id": str(self.section.id), "kind": "stock_in", "amount": "150"},
        )
        self.assertEqual(panel["results"][0]["charges"], "400.00")
        self.assertEqual(panel["results"][0]["products"], "150.00")
        self.assertEqual(panel["results"][0]["result"], "-250.00")
        codes = {
            line.account.code: (line.debit, line.credit)
            for line in Entry.objects.get(company=self.company, source="cage_alloc").lines.all()
        }
        self.assertEqual(codes["941"], (Decimal("150"), Decimal("0")))
        self.assertEqual(codes["95-PROD"][1], Decimal("150"))

    def test_variance_and_incorporation(self):
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "300", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "300"},
            ]
        )
        allocate_cage(
            self.company,
            self.period,
            None,
            {"section_id": str(self.section.id), "kind": "variance", "amount": "40"},
        )
        allocate_cage(
            self.company,
            self.period,
            None,
            {"section_id": str(self.section.id), "kind": "charge_ni", "amount": "10"},
        )
        row = reflect_period(self.company, self.period, None)["results"][0]
        self.assertEqual(row["charges"], "300.00")
        self.assertEqual(row["products"], "50.00")
        self.assertEqual(row["result"], "-250.00")

    def test_close_95_to_981(self):
        self._post(
            [
                {"account_id": str(self.acc411.id), "debit": "800", "credit": "0"},
                {"account_id": str(self.acc701.id), "debit": "0", "credit": "800"},
            ]
        )
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "200", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "200"},
            ]
        )
        first = close_cage(self.company, self.period, None)
        self.assertTrue(first["closed"])
        self.assertEqual(first["results"][0]["result"], "600.00")
        self.assertEqual(first["analytical_result"], "600.00")
        close = Entry.objects.get(company=self.company, source="cage_close")
        codes = {line.account.code: (line.debit, line.credit) for line in close.lines.all()}
        self.assertEqual(codes["95-PROD"], (Decimal("600"), Decimal("0")))
        self.assertEqual(codes["981"], (Decimal("0"), Decimal("600")))
        again = close_cage(self.company, self.period, None)
        self.assertEqual(again["close_entry_id"], first["close_entry_id"])
        self.assertEqual(Entry.objects.filter(company=self.company, source="cage_close").count(), 1)

    def test_close_blocked_while_pending(self):
        CageSection.objects.filter(company=self.company).update(is_active=False)
        self._post(
            [
                {"account_id": str(self.acc601.id), "debit": "30", "credit": "0"},
                {"account_id": str(self.acc401.id), "debit": "0", "credit": "30"},
            ]
        )
        CageSection.objects.filter(company=self.company).update(is_active=True)
        with self.assertRaises(HttpError):
            close_cage(self.company, self.period, None)
