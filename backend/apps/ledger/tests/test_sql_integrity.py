"""ACC-03 — intégrité PostgreSQL (immutabilité SQL + équilibre).

Nécessite PostgreSQL 16 avec la migration ``0033_acc03_sql_integrity``.
Utiliser la base temporaire ``muhimu-acc03`` (voir docker-compose.acc03-integrity.yml).
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal

from django.db import connection, connections, transaction
from django.db.utils import Error as DbError
from django.test import TransactionTestCase

from apps.ledger.models import (
    AccountingPeriod,
    BankStatement,
    BankStatementLine,
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
from apps.tenancy.models import Company, Organization, OrganizationType


def _pg_exc(callable_):
    try:
        callable_()
    except DbError as exc:
        return exc
    return None


class Acc03SqlIntegrityTests(TransactionTestCase):
    """TransactionTestCase : commits réels → triggers DEFERRABLE exercés."""

    def setUp(self):
        super().setUp()
        self.org = Organization.objects.create(
            name="Org ACC-03",
            slug="org-acc03",
            type=OrganizationType.SME,
        )
        self.company = Company.objects.create(
            organization=self.org,
            name="SARL ACC-03",
            currency_code="XOF",
        )
        self.acc411 = self._account("411", "Clients")
        self.acc401 = self._account("401", "Fournisseurs")
        self.acc521 = self._account("521", "Banques")
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=2026,
            starts_on=date(2026, 1, 1),
            ends_on=date(2026, 12, 31),
        )
        from calendar import monthrange

        for month in range(1, 13):
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

    def _account(self, code: str, label: str):
        from apps.ledger.models import Account

        account = Account(
            organization=self.org,
            company=self.company,
            code=code,
            label=label,
            is_postable=True,
            is_syscohada=True,
        )
        account.save()
        return account

    def _balanced_draft(self, amount: str = "1000", day: int = 10) -> Entry:
        return create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(2026, 1, day),
            value_date=date(2026, 1, day),
            description=f"ACC03 {amount}",
            document_ref=f"ACC03-{amount}-{day}",
            raw_lines=[
                {"account_id": str(self.acc411.id), "debit": amount, "credit": "0"},
                {"account_id": str(self.acc521.id), "debit": "0", "credit": amount},
            ],
        )

    def test_01_balanced_entry_accepted(self):
        entry = post_entry(self._balanced_draft("1500"), None)
        self.assertEqual(entry.status, EntryStatus.POSTED)

    def test_02_unbalanced_draft_rejected_by_app(self):
        from ninja.errors import HttpError

        with self.assertRaises(HttpError):
            create_draft(
                company=self.company,
                journal=self.journal,
                accounting_date=date(2026, 1, 12),
                value_date=date(2026, 1, 12),
                description="Déséquilibré",
                document_ref="BAD-1",
                raw_lines=[
                    {"account_id": str(self.acc411.id), "debit": "100", "credit": "0"},
                    {"account_id": str(self.acc521.id), "debit": "0", "credit": "50"},
                ],
            )

    def test_03_sql_post_unbalanced_rejected(self):
        entry = self._balanced_draft("200", day=13)
        line = entry.lines.get(account=self.acc411)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {EntryLine._meta.db_table} SET debit = %s WHERE id = %s",
                [Decimal("999.00"), str(line.id)],
            )
        with self.assertRaises(DbError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {Entry._meta.db_table} SET status = 'posted' WHERE id = %s",
                        [str(entry.id)],
                    )

    def test_04_sql_update_posted_amount_rejected(self):
        entry = post_entry(self._balanced_draft("300", day=14), None)
        line = entry.lines.get(account=self.acc411)

        def bad():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {EntryLine._meta.db_table} SET debit = %s WHERE id = %s",
                        [Decimal("4242.00"), str(line.id)],
                    )

        exc = _pg_exc(bad)
        self.assertIsNotNone(exc)
        self.assertIn("ACC-03", str(exc))
        line.refresh_from_db()
        self.assertEqual(line.debit, Decimal("300"))

    def test_05_sql_delete_posted_line_rejected(self):
        entry = post_entry(self._balanced_draft("400", day=15), None)
        line = entry.lines.get(account=self.acc411)

        def bad():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {EntryLine._meta.db_table} WHERE id = %s",
                        [str(line.id)],
                    )

        self.assertIsNotNone(_pg_exc(bad))
        self.assertEqual(entry.lines.count(), 2)

    def test_06_sql_delete_posted_entry_rejected(self):
        entry = post_entry(self._balanced_draft("500", day=16), None)

        def bad():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {Entry._meta.db_table} WHERE id = %s",
                        [str(entry.id)],
                    )

        self.assertIsNotNone(_pg_exc(bad))
        self.assertTrue(Entry.objects.filter(pk=entry.pk).exists())

    def test_07_sql_change_company_posted_rejected(self):
        entry = post_entry(self._balanced_draft("600", day=17), None)
        other = Company.objects.create(
            organization=self.org, name="Autre", currency_code="XOF"
        )

        def bad():
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {Entry._meta.db_table} SET company_id = %s WHERE id = %s",
                        [str(other.id), str(entry.id)],
                    )

        self.assertIsNotNone(_pg_exc(bad))

    def test_08_annotations_sql_allowed(self):
        entry = post_entry(self._balanced_draft("700", day=18), None)
        line = entry.lines.get(account=self.acc411)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {EntryLine._meta.db_table} SET due_on = %s, lettering = %s, "
                f"bank_pointage = %s WHERE id = %s",
                [date(2026, 6, 1), "L-TEST", "P-TEST", str(line.id)],
            )
        line.refresh_from_db()
        self.assertEqual(line.due_on, date(2026, 6, 1))
        self.assertEqual(line.lettering, "L-TEST")
        self.assertEqual(line.bank_pointage, "P-TEST")

    def test_09_lettering_service(self):
        a = post_entry(self._balanced_draft("800", day=19), None)
        b = post_entry(
            create_draft(
                company=self.company,
                journal=self.journal,
                accounting_date=date(2026, 1, 20),
                value_date=date(2026, 1, 20),
                description="Règlement",
                document_ref="REG-800",
                raw_lines=[
                    {"account_id": str(self.acc521.id), "debit": "800", "credit": "0"},
                    {"account_id": str(self.acc411.id), "debit": "0", "credit": "800"},
                ],
            ),
            None,
        )
        la = a.lines.get(account=self.acc411)
        lb = b.lines.get(account=self.acc411)
        party = ThirdParty.objects.create(
            organization=self.org,
            company=self.company,
            name="Client",
            reference="C-ACC03",
            account=self.acc411,
        )
        EntryLine.objects.filter(pk__in=[la.pk, lb.pk]).update(third_party_id=party.id)
        code = letter_lines(self.company, [str(la.id), str(lb.id)])
        self.assertTrue(code)
        self.assertEqual(unletter(self.company, code), 2)

    def test_10_pointage_service(self):
        entry = post_entry(
            create_draft(
                company=self.company,
                journal=self.journal,
                accounting_date=date(2026, 1, 21),
                value_date=date(2026, 1, 21),
                description="Banque",
                document_ref="BQ-ACC03",
                raw_lines=[
                    {"account_id": str(self.acc521.id), "debit": "250", "credit": "0"},
                    {"account_id": str(self.acc411.id), "debit": "0", "credit": "250"},
                ],
            ),
            None,
        )
        book = entry.lines.get(account=self.acc521)
        statement = BankStatement.objects.create(
            organization=self.org,
            company=self.company,
            account=self.acc521,
            statement_date=date(2026, 1, 21),
            bank_balance=Decimal("250"),
        )
        stmt = BankStatementLine.objects.create(
            organization=self.org,
            company=self.company,
            statement=statement,
            line_date=date(2026, 1, 21),
            label="Vir",
            bank_debit=Decimal("0"),
            bank_credit=Decimal("250"),
        )
        code = point_selection(self.company, [str(book.id)], [str(stmt.id)])
        book.refresh_from_db()
        self.assertEqual(book.bank_pointage, code)
        unpoint(self.company, code)

    def test_11_due_on_service(self):
        entry = post_entry(self._balanced_draft("900", day=22), None)
        line = entry.lines.get(account=self.acc411)
        updated = set_line_due(self.company, str(line.id), "2026-07-15")
        self.assertEqual(updated.due_on, date(2026, 7, 15))

    def test_12_reverse_entry(self):
        entry = post_entry(self._balanced_draft("1100", day=23), None)
        original_debit = entry.lines.get(account=self.acc411).debit
        reversal = reverse_entry(entry, None, description="Contrepassation ACC-03")
        self.assertEqual(reversal.status, EntryStatus.POSTED)
        entry.refresh_from_db()
        self.assertEqual(entry.lines.get(account=self.acc411).debit, original_debit)

    def test_13_transactional_import_balanced(self):
        """Import simulé : brouillon + post dans une transaction."""
        with transaction.atomic():
            entry = self._balanced_draft("1200", day=24)
            entry = post_entry(entry, None)
        self.assertEqual(Entry.objects.get(pk=entry.pk).status, EntryStatus.POSTED)

    def test_14_transactional_unbalanced_sql_rolled_back(self):
        entry = self._balanced_draft("1300", day=25)
        line = entry.lines.get(account=self.acc411)
        with self.assertRaises(DbError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {EntryLine._meta.db_table} SET debit = %s WHERE id = %s",
                        [Decimal("1301.00"), str(line.id)],
                    )
                    cursor.execute(
                        f"UPDATE {Entry._meta.db_table} SET status = 'posted', "
                        f"number = 1, number_display = 'OD-2026-00001' WHERE id = %s",
                        [str(entry.id)],
                    )
        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)
        line.refresh_from_db()
        self.assertEqual(line.debit, Decimal("1300"))

    def test_15_rollback_no_partial_post(self):
        entry = self._balanced_draft("1400", day=26)
        try:
            with transaction.atomic():
                post_entry(entry, None)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        entry.refresh_from_db()
        self.assertEqual(entry.status, EntryStatus.DRAFT)

    def test_16_concurrent_sql_cannot_unbalance_posted(self):
        entry = post_entry(self._balanced_draft("1600", day=27), None)
        line_id = str(entry.lines.get(account=self.acc411).id)
        errors: list[str] = []
        ok = threading.Event()

        def attacker():
            connections.close_all()
            try:
                with transaction.atomic():
                    with connections["default"].cursor() as cursor:
                        cursor.execute(
                            f"UPDATE {EntryLine._meta.db_table} SET debit = %s WHERE id = %s",
                            [Decimal("9999.00"), line_id],
                        )
                errors.append("update-succeeded")
            except DbError as exc:
                errors.append(f"blocked:{exc.__class__.__name__}")
            finally:
                connections.close_all()
                ok.set()

        threads = [threading.Thread(target=attacker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertTrue(ok.is_set())
        self.assertTrue(all(item.startswith("blocked:") for item in errors))
        self.assertEqual(
            EntryLine.objects.get(pk=line_id).debit,
            Decimal("1600"),
        )

    def test_17_rls_policies_still_present(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename IN ('ledger_entry', 'ledger_entryline')
                  AND policyname LIKE '%isolation%'
                """
            )
            count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 2)

    def test_18_triggers_registered(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tgname FROM pg_trigger
                WHERE NOT tgisinternal
                  AND tgrelid IN (
                    'public.ledger_entry'::regclass,
                    'public.ledger_entryline'::regclass
                  )
                  AND tgname LIKE 'trg_ledger_%'
                ORDER BY 1
                """
            )
            names = {row[0] for row in cursor.fetchall()}
        self.assertIn("trg_ledger_entry_forbid_posted_mutation", names)
        self.assertIn("trg_ledger_entryline_forbid_posted_substance", names)
        self.assertIn("trg_ledger_entry_posted_balance", names)
        self.assertIn("trg_ledger_entryline_balanced_deferred", names)

    def test_19_cascade_delete_draft_allowed(self):
        entry = self._balanced_draft("1700", day=28)
        entry_id = entry.id
        entry.delete()
        self.assertFalse(Entry.objects.filter(pk=entry_id).exists())
        self.assertFalse(EntryLine.objects.filter(entry_id=entry_id).exists())

    def test_20_multi_line_annotation_batch(self):
        entry = post_entry(self._balanced_draft("1800", day=29), None)
        ids = list(entry.lines.values_list("id", flat=True))
        EntryLine.objects.filter(id__in=ids).update(lettering="L-BATCH")
        self.assertEqual(
            EntryLine.objects.filter(id__in=ids, lettering="L-BATCH").count(),
            2,
        )

    def test_21_post_performance_smoke(self):
        start = time.perf_counter()
        for index in range(15):
            post_entry(self._balanced_draft(str(100 + index), day=1), None)
        elapsed = time.perf_counter() - start
        # Garde-fou large : détecter une régression catastrophique uniquement.
        self.assertLess(elapsed, 30.0, f"post batch trop lent: {elapsed:.2f}s")
