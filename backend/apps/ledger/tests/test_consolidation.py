from datetime import date
from decimal import Decimal

from ninja.errors import HttpError

from apps.ledger.models import AccountingPeriod, ConsolidationGroup, Exercise, Journal, JournalType
from apps.ledger.services.consolidation import (
    add_elimination,
    add_member,
    build_consolidated,
    create_group,
    group_pdf,
    remove_member,
)
from apps.ledger.services.posting import create_draft, post_entry
from apps.ledger.tests.db import LedgerDbTestCase
from apps.tenancy.models import Company


class ConsolidationTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.parent = self.company
        self.child = Company.objects.create(
            organization=self.org, name="SARL Fille", currency_code="XOF"
        )
        self.parent_books = self._books(self.parent)
        self.child_books = self._books(self.child)
        self._post(
            self.parent,
            self.parent_books,
            [
                {"account_id": str(self.parent_books["521"].id), "debit": "1000", "credit": "0"},
                {"account_id": str(self.parent_books["101"].id), "debit": "0", "credit": "1000"},
            ],
        )
        self._post(
            self.parent,
            self.parent_books,
            [
                {"account_id": str(self.parent_books["411"].id), "debit": "500", "credit": "0"},
                {"account_id": str(self.parent_books["701"].id), "debit": "0", "credit": "500"},
            ],
        )
        self._post(
            self.child,
            self.child_books,
            [
                {"account_id": str(self.child_books["521"].id), "debit": "400", "credit": "0"},
                {"account_id": str(self.child_books["101"].id), "debit": "0", "credit": "400"},
            ],
        )
        self._post(
            self.child,
            self.child_books,
            [
                {"account_id": str(self.child_books["411"].id), "debit": "200", "credit": "0"},
                {"account_id": str(self.child_books["701"].id), "debit": "0", "credit": "200"},
            ],
        )
        self._post(
            self.child,
            self.child_books,
            [
                {"account_id": str(self.child_books["601"].id), "debit": "100", "credit": "0"},
                {"account_id": str(self.child_books["401"].id), "debit": "0", "credit": "100"},
            ],
        )

    def _books(self, company):
        exercise = Exercise.objects.create(
            organization=self.org,
            company=company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        period = AccountingPeriod.objects.create(
            organization=self.org,
            company=company,
            exercise=exercise,
            year=2026,
            month=1,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 1, 31),
        )
        journal = Journal.objects.create(
            organization=self.org,
            company=company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        codes = {
            "101": "Capital",
            "401": "Fournisseurs",
            "411": "Clients",
            "521": "Banque",
            "601": "Achats",
            "701": "Ventes",
        }
        accounts = {}
        for code, label in codes.items():
            existing = company.accounts.filter(code=code).first()
            accounts[code] = existing or self.make_account_for(company, code, label)
        accounts["exercise"] = exercise
        accounts["period"] = period
        accounts["journal"] = journal
        return accounts

    def make_account_for(self, company, code, label):
        from apps.ledger.models import Account

        account = Account(
            organization=self.org,
            company=company,
            code=code,
            label=label,
            is_postable=True,
        )
        account.save()
        return account

    def _post(self, company, books, lines):
        entry = create_draft(
            company=company,
            journal=books["journal"],
            accounting_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Consol",
            document_ref="CONS",
            raw_lines=lines,
        )
        return post_entry(entry, None)

    def _line(self, panel, block, code):
        statements = panel["statements"]
        if block == "actif":
            lines = statements["bilan"]["actif"]
        elif block == "passif":
            lines = statements["bilan"]["passif"]
        elif block == "result":
            lines = statements["result"]["lines"]
        else:
            lines = statements["tft"]["lines"]
        return next(item for item in lines if item["code"] == code)

    def test_consolidated_requires_parent(self):
        with self.assertRaises(HttpError):
            create_group(
                self.org,
                {"name": "Groupe", "kind": "consolidated", "year": 2026},
            )

    def test_full_method_sums_and_minority(self):
        panel = create_group(
            self.org,
            {
                "name": "Groupe Horizon",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        add_member(
            self.org,
            panel["id"],
            {"company_id": str(self.child.id), "method": "full", "ownership_pct": "80"},
        )
        panel = build_consolidated(ConsolidationGroup.objects.get(id=panel["id"]))
        self.assertEqual(self._line(panel, "actif", "BS")["current"], "1400")
        self.assertEqual(self._line(panel, "actif", "BI")["current"], "700")
        self.assertEqual(self._line(panel, "passif", "CA")["current"], "1320")
        self.assertEqual(self._line(panel, "passif", "CN")["current"], "80")
        self.assertEqual(self._line(panel, "result", "TA")["current"], "700")
        self.assertEqual(self._line(panel, "result", "RA")["current"], "-100")
        self.assertEqual(panel["minorities"], "80")

    def test_combined_keeps_full_equity(self):
        panel = create_group(
            self.org,
            {"name": "Combiné Alpha", "kind": "combined", "year": 2026, "currency_code": "XOF"},
        )
        add_member(self.org, panel["id"], {"company_id": str(self.parent.id), "method": "combined"})
        add_member(self.org, panel["id"], {"company_id": str(self.child.id), "method": "combined"})
        panel = build_consolidated(ConsolidationGroup.objects.get(id=panel["id"]))
        self.assertEqual(self._line(panel, "passif", "CA")["current"], "1400")
        self.assertFalse(any(line["code"] == "CN" for line in panel["statements"]["bilan"]["passif"]))
        self.assertEqual(self._line(panel, "result", "TA")["current"], "700")

    def test_proportional_scales_subsidiary(self):
        panel = create_group(
            self.org,
            {
                "name": "Prop",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        add_member(
            self.org,
            panel["id"],
            {"company_id": str(self.child.id), "method": "proportional", "ownership_pct": "50"},
        )
        panel = build_consolidated(ConsolidationGroup.objects.get(id=panel["id"]))
        self.assertEqual(self._line(panel, "actif", "BS")["current"], "1200")
        self.assertEqual(self._line(panel, "result", "TA")["current"], "600")
        self.assertEqual(panel["minorities"], "0")

    def test_eliminations_reduce_sales_and_purchases(self):
        panel = create_group(
            self.org,
            {
                "name": "Élim",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        add_member(
            self.org,
            panel["id"],
            {"company_id": str(self.child.id), "method": "full", "ownership_pct": "80"},
        )
        add_elimination(self.org, panel["id"], {"code": "TA", "amount": "200", "kind": "sales", "label": "CA intra"})
        add_elimination(self.org, panel["id"], {"code": "RA", "amount": "-100", "kind": "sales", "label": "Achats intra"})
        panel = build_consolidated(ConsolidationGroup.objects.get(id=panel["id"]))
        self.assertEqual(self._line(panel, "result", "TA")["current"], "500")
        self.assertEqual(self._line(panel, "result", "RA")["current"], "0")
        self.assertEqual(self._line(panel, "result", "XB")["current"], "500")

    def test_equity_is_skipped(self):
        panel = create_group(
            self.org,
            {
                "name": "ME",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        add_member(
            self.org,
            panel["id"],
            {"company_id": str(self.child.id), "method": "equity", "ownership_pct": "40"},
        )
        panel = build_consolidated(ConsolidationGroup.objects.get(id=panel["id"]))
        self.assertEqual(self._line(panel, "result", "TA")["current"], "500")
        self.assertTrue(any("équivalence" in item.lower() for item in panel["warnings"]))

    def test_cannot_remove_parent(self):
        panel = create_group(
            self.org,
            {
                "name": "Mère",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        parent_member = next(item for item in panel["members"] if item["is_parent"])
        with self.assertRaises(HttpError):
            remove_member(self.org, panel["id"], parent_member["id"])

    def test_pdf_consolidated(self):
        panel = create_group(
            self.org,
            {
                "name": "PDF Groupe",
                "kind": "consolidated",
                "year": 2026,
                "parent_id": str(self.parent.id),
            },
        )
        add_member(
            self.org,
            panel["id"],
            {"company_id": str(self.child.id), "method": "full", "ownership_pct": "80"},
        )
        pdf, name = group_pdf(self.org, panel["id"], "liasse")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn("consolidee", name)
