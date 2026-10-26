"""ACC-02 — immutabilité des écritures POSTED (ORM / QuerySet / annotations)."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import connection

from apps.ledger.models import (
    AccountingPeriod,
    Entry,
    EntryLine,
    EntryStatus,
    Exercise,
    Journal,
    JournalType,
    ThirdParty,
)
from apps.ledger.services.bank_rec import point_selection, unpoint
from apps.ledger.services.lettering import letter_lines, set_line_due, unletter
from apps.ledger.services.posting import create_draft, post_entry, reverse_entry
from apps.ledger.tests.db import LedgerDbTestCase
from apps.tenancy.models import Company, Organization, OrganizationType


class ImmutabilityPostedTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.acc521 = self.make_account("521", "Banques")
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
        # Périodes restantes pour reverse_entry (date du jour = période ouverte).
        from calendar import monthrange

        for month in range(2, 13):
            last = monthrange(2026, month)[1]
            AccountingPeriod.objects.create(
                organization=self.org,
                company=self.company,
                exercise=self.exercise,
                year=2026,
                month=month,
                starts_on=date(2026, month, 1),
                ends_on=date(2026, month, last),
            )
        self.journal = Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 10),
            value_date=date(2026, 1, 10),
            description="Vente test ACC-02",
            document_ref="ACC02-1",
            raw_lines=[
                {
                    "account_id": str(self.acc411.id),
                    "debit": "1000",
                    "credit": "0",
                    "label": "Client",
                },
                {
                    "account_id": str(self.acc521.id),
                    "debit": "0",
                    "credit": "1000",
                    "label": "Banque",
                },
            ],
        )
        self.entry = post_entry(self.entry, None)
        self.line_client = self.entry.lines.get(account=self.acc411)
        self.line_bank = self.entry.lines.get(account=self.acc521)

    def test_save_amount_blocked(self):
        self.line_client.debit = Decimal("2000")
        with self.assertRaises(ValidationError):
            self.line_client.save()

    def test_save_account_blocked(self):
        self.line_client.account = self.acc401
        with self.assertRaises(ValidationError):
            self.line_client.save()

    def test_save_company_blocked(self):
        other_org = Organization.objects.create(
            name="Autre", slug="autre-acc02", type=OrganizationType.SME
        )
        other = Company.objects.create(
            organization=other_org, name="Autre Cie", currency_code="XOF"
        )
        self.entry.company = other
        with self.assertRaises(ValidationError):
            self.entry.save()

    def test_save_accounting_date_blocked(self):
        self.entry.accounting_date = date(2026, 2, 1)
        with self.assertRaises(ValidationError):
            self.entry.save()

    def test_save_line_label_blocked(self):
        self.line_client.label = "Modifié"
        with self.assertRaises(ValidationError):
            self.line_client.save()

    def test_queryset_update_amount_blocked(self):
        with self.assertRaises(ValidationError):
            EntryLine.objects.filter(pk=self.line_client.pk).update(debit=Decimal("999"))

    def test_queryset_update_entry_status_blocked(self):
        with self.assertRaises(ValidationError):
            Entry.objects.filter(pk=self.entry.pk).update(description="hack")

    def test_queryset_update_draft_to_posted_blocked(self):
        draft = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 11),
            value_date=date(2026, 1, 11),
            description="Brouillon",
            document_ref="D1",
            raw_lines=[
                {
                    "account_id": str(self.acc411.id),
                    "debit": "100",
                    "credit": "0",
                },
                {
                    "account_id": str(self.acc521.id),
                    "debit": "0",
                    "credit": "100",
                },
            ],
        )
        with self.assertRaises(ValidationError):
            Entry.objects.filter(pk=draft.pk).update(status=EntryStatus.POSTED)

    def test_bulk_update_amount_blocked(self):
        self.line_client.debit = Decimal("5000")
        with self.assertRaises(ValidationError):
            EntryLine.objects.bulk_update([self.line_client], ["debit"])

    def test_bulk_update_entry_blocked(self):
        self.entry.description = "bulk hack"
        with self.assertRaises(ValidationError):
            Entry.objects.bulk_update([self.entry], ["description"])

    def test_delete_posted_entry_blocked(self):
        with self.assertRaises(ValidationError):
            self.entry.delete()
        with self.assertRaises(ValidationError):
            Entry.objects.filter(pk=self.entry.pk).delete()

    def test_delete_posted_line_blocked(self):
        with self.assertRaises(ValidationError):
            self.line_client.delete()
        with self.assertRaises(ValidationError):
            EntryLine.objects.filter(pk=self.line_client.pk).delete()

    def test_bulk_create_on_posted_entry_blocked(self):
        with self.assertRaises(ValidationError):
            EntryLine.objects.bulk_create(
                [
                    EntryLine(
                        organization=self.org,
                        company=self.company,
                        entry=self.entry,
                        account=self.acc401,
                        debit=Decimal("1"),
                        credit=Decimal("0"),
                        position=9,
                    )
                ]
            )

    def test_annotation_due_on_allowed(self):
        updated = set_line_due(self.company, str(self.line_client.id), "2026-03-31")
        self.assertEqual(updated.due_on, date(2026, 3, 31))
        self.line_client.refresh_from_db()
        self.assertEqual(self.line_client.due_on, date(2026, 3, 31))

    def test_annotation_lettering_allowed(self):
        settlement = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 15),
            value_date=date(2026, 1, 15),
            description="Encaissement",
            document_ref="ENC-1",
            raw_lines=[
                {
                    "account_id": str(self.acc521.id),
                    "debit": "1000",
                    "credit": "0",
                },
                {
                    "account_id": str(self.acc411.id),
                    "debit": "0",
                    "credit": "1000",
                    "label": "Règlement client",
                },
            ],
        )
        settlement = post_entry(settlement, None)
        settle_line = settlement.lines.get(account=self.acc411)
        party = ThirdParty.objects.create(
            organization=self.org,
            company=self.company,
            name="Client Demo",
            reference="C001",
            account=self.acc411,
        )
        EntryLine.objects.filter(pk__in=[self.line_client.pk, settle_line.pk]).update(
            third_party_id=party.id
        )
        code = letter_lines(self.company, [str(self.line_client.id), str(settle_line.id)])
        self.assertTrue(code)
        self.line_client.refresh_from_db()
        settle_line.refresh_from_db()
        self.assertEqual(self.line_client.lettering, code)
        self.assertEqual(settle_line.lettering, code)
        cleared = unletter(self.company, code)
        self.assertEqual(cleared, 2)

    def test_annotation_bank_pointage_allowed(self):
        EntryLine.objects.filter(pk=self.line_bank.pk).update(bank_pointage="P1")
        self.line_bank.refresh_from_db()
        self.assertEqual(self.line_bank.bank_pointage, "P1")
        EntryLine.objects.filter(pk=self.line_bank.pk).update(bank_pointage="")
        self.line_bank.refresh_from_db()
        self.assertEqual(self.line_bank.bank_pointage, "")

    def test_reverse_entry_works(self):
        reversal = reverse_entry(self.entry, None, description="Contrepassation ACC-02")
        self.assertEqual(reversal.status, EntryStatus.POSTED)
        self.assertEqual(reversal.reversed_entry_id, self.entry.id)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.status, EntryStatus.POSTED)
        self.assertEqual(self.line_client.debit, Decimal("1000"))

    def test_related_manager_update_blocked(self):
        with self.assertRaises(ValidationError):
            self.entry.lines.update(debit=Decimal("1"))

    def test_tenant_isolation_update_other_company(self):
        other_org = Organization.objects.create(
            name="Org B", slug="org-b-acc02", type=OrganizationType.SME
        )
        other = Company.objects.create(
            organization=other_org, name="Cie B", currency_code="XOF"
        )
        updated = EntryLine.objects.filter(company=other, pk=self.line_client.pk).update(
            due_on=date(2026, 4, 1)
        )
        self.assertEqual(updated, 0)
        self.line_client.refresh_from_db()
        self.assertIsNone(self.line_client.due_on)

    def test_sql_direct_amount_blocked_by_acc03(self):
        """ACC-03 : le SQL direct ne peut plus modifier un montant POSTED."""
        from django.db import transaction
        from django.db.utils import Error as DbError

        table = EntryLine._meta.db_table
        with self.assertRaises(DbError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table} SET debit = %s WHERE id = %s",
                        [Decimal("4242.00"), str(self.line_client.id)],
                    )
        self.line_client.refresh_from_db()
        self.assertEqual(self.line_client.debit, Decimal("1000"))


class ImmutabilityBankRecTests(LedgerDbTestCase):
    """Pointage bancaire via service (non-régression annotation)."""

    def setUp(self):
        super().setUp()
        self.acc521 = self.make_account("521", "Banques")
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        AccountingPeriod.objects.create(
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
            code="BQ",
            name="Banque",
            type=JournalType.BANK,
        )

    def test_point_selection_service(self):
        from apps.ledger.models import BankStatement, BankStatementLine

        entry = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, 5),
            value_date=date(2026, 1, 5),
            description="Virement",
            document_ref="BQ-1",
            raw_lines=[
                {"account_id": str(self.acc521.id), "debit": "500", "credit": "0"},
                {"account_id": str(self.acc411.id), "debit": "0", "credit": "500"},
            ],
        )
        entry = post_entry(entry, None)
        book = entry.lines.get(account=self.acc521)
        statement = BankStatement.objects.create(
            organization=self.org,
            company=self.company,
            account=self.acc521,
            statement_date=date(2026, 1, 5),
            bank_balance=Decimal("500"),
        )
        stmt_line = BankStatementLine.objects.create(
            organization=self.org,
            company=self.company,
            statement=statement,
            line_date=date(2026, 1, 5),
            label="Virement",
            bank_debit=Decimal("0"),
            bank_credit=Decimal("500"),
        )
        code = point_selection(self.company, [str(book.id)], [str(stmt_line.id)])
        book.refresh_from_db()
        self.assertEqual(book.bank_pointage, code)
        unpoint(self.company, code)
        book.refresh_from_db()
        self.assertEqual(book.bank_pointage, "")
