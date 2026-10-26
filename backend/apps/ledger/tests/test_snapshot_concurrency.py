"""ACC-01 — concurrence réelle sur BalanceSnapshot (PostgreSQL, multi-connexions)."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from decimal import Decimal

from django.db import connections
from django.test import TransactionTestCase

from apps.ledger.models import (
    Account,
    AccountingPeriod,
    BalanceSnapshot,
    Entry,
    EntryStatus,
    Exercise,
    Journal,
    JournalType,
)
from apps.ledger.services.balance import posted_movement_totals
from apps.ledger.services.posting import create_draft, post_entry
from apps.tenancy.models import Company, Organization, OrganizationType


def _post_entry_in_thread(entry_id) -> str:
    """Chaque thread : connexion Django neuve + contexte RLS, puis validation."""
    connections.close_all()
    try:
        entry = Entry.objects.get(pk=entry_id)
        posted = post_entry(entry, None)
        return str(posted.id)
    finally:
        connections.close_all()


class ConcurrentSnapshotTests(TransactionTestCase):
    """TransactionTestCase : pas de transaction enveloppante → vraie concurrence PG."""

    def setUp(self):
        super().setUp()
        self.org = Organization.objects.create(
            name="Org concurrence",
            slug="",
            type=OrganizationType.SME,
        )
        self.company = Company.objects.create(
            organization=self.org,
            name="SARL Concurrence",
            currency_code="XOF",
        )
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
        # Un journal par worker : JournalSequence.select_for_update sérialise
        # sinon toute la validation et masque la course sur BalanceSnapshot.
        self.journals = [
            Journal.objects.create(
                organization=self.org,
                company=self.company,
                code=f"J{i:02d}",
                name=f"Journal concurrence {i}",
                type=JournalType.OD,
            )
            for i in range(16)
        ]
        self.journal = self.journals[0]
        self.acc411 = self._account("411", "Clients")
        self.acc701 = self._account("701", "Ventes")
        self.acc521 = self._account("521", "Banques locales")
        self.acc601 = self._account("601", "Achats de marchandises")

    def _account(self, code: str, label: str) -> Account:
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

    def _draft(
        self,
        amount: str,
        debit_account: Account,
        credit_account: Account,
        day: int = 10,
        journal: Journal | None = None,
    ) -> Entry:
        return create_draft(
            company=self.company,
            journal=journal or self.journal,
            accounting_date=date(2026, 1, day),
            value_date=date(2026, 1, day),
            description=f"Concurrence {amount}",
            document_ref="ACC01",
            raw_lines=[
                {
                    "account_id": str(debit_account.id),
                    "debit": amount,
                    "credit": "0",
                    "label": "Débit",
                },
                {
                    "account_id": str(credit_account.id),
                    "debit": "0",
                    "credit": amount,
                    "label": "Crédit",
                },
            ],
        )

    def _assert_snapshot_matches_lines(self, account: Account) -> BalanceSnapshot:
        snap = BalanceSnapshot.objects.get(period=self.period, account=account)
        debit, credit = posted_movement_totals(self.company, self.period, account)
        self.assertEqual(snap.mov_debit, debit, msg=f"mov_debit {account.code}")
        self.assertEqual(snap.mov_credit, credit, msg=f"mov_credit {account.code}")
        self.assertEqual(snap.organization_id, self.org.id)
        self.assertEqual(snap.company_id, self.company.id)
        return snap

    def _run_concurrent_posts(self, entry_ids: list, workers: int) -> list[str]:
        posted_ids: list[str] = []
        barrier = threading.Barrier(workers, timeout=60)

        def worker(entry_id):
            # Synchronise le démarrage pour maximiser le chevauchement.
            connections.close_all()
            barrier.wait()
            return _post_entry_in_thread(entry_id)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker, entry_id) for entry_id in entry_ids]
            for future in as_completed(futures):
                posted_ids.append(future.result())

        connections.close_all()
        return posted_ids

    def test_concurrent_first_snapshot_creation_no_lost_updates(self):
        """Validations simultanées (journaux distincts) créent le 1er snapshot sans perte."""
        amount = Decimal("1000")
        workers = 8
        drafts = [
            self._draft(
                str(amount),
                self.acc411,
                self.acc701,
                day=1 + (i % 20),
                journal=self.journals[i],
            )
            for i in range(workers)
        ]
        self.assertEqual(BalanceSnapshot.objects.filter(period=self.period).count(), 0)

        self._run_concurrent_posts([d.id for d in drafts], workers=workers)

        posted = Entry.objects.filter(company=self.company, status=EntryStatus.POSTED)
        self.assertEqual(posted.count(), workers)

        snap411 = self._assert_snapshot_matches_lines(self.acc411)
        snap701 = self._assert_snapshot_matches_lines(self.acc701)
        expected = amount * workers
        self.assertEqual(snap411.mov_debit, expected)
        self.assertEqual(snap411.mov_credit, Decimal("0"))
        self.assertEqual(snap701.mov_credit, expected)
        self.assertEqual(snap701.mov_debit, Decimal("0"))
        # Un seul snapshot par compte (pas de double création).
        self.assertEqual(
            BalanceSnapshot.objects.filter(period=self.period, account=self.acc411).count(),
            1,
        )
        self.assertEqual(
            BalanceSnapshot.objects.filter(period=self.period, account=self.acc701).count(),
            1,
        )

    def test_concurrent_posts_on_existing_snapshot_accumulate(self):
        """Increments F() sur snapshot déjà présent : somme exacte sous charge."""
        # Seed séquentiel pour créer les snapshots.
        seed = self._draft("500", self.acc411, self.acc701, day=2)
        post_entry(seed, None)
        self.assertEqual(
            BalanceSnapshot.objects.get(period=self.period, account=self.acc411).mov_debit,
            Decimal("500"),
        )

        workers = 12
        unit = Decimal("250")
        drafts = [
            self._draft(
                str(unit),
                self.acc411,
                self.acc701,
                day=3 + (i % 25),
                journal=self.journals[i],
            )
            for i in range(workers)
        ]
        self._run_concurrent_posts([d.id for d in drafts], workers=workers)

        snap411 = self._assert_snapshot_matches_lines(self.acc411)
        snap701 = self._assert_snapshot_matches_lines(self.acc701)
        expected = Decimal("500") + unit * workers
        self.assertEqual(snap411.mov_debit, expected)
        self.assertEqual(snap701.mov_credit, expected)

    def test_concurrent_mixed_accounts_preserve_double_entry_totals(self):
        """Comptes distincts postés en parallèle via journaux séparés : équilibre global."""
        workers = 10
        drafts_a = [
            self._draft(
                "100",
                self.acc411,
                self.acc701,
                day=5,
                journal=self.journals[i],
            )
            for i in range(workers // 2)
        ]
        drafts_b = [
            self._draft(
                "100",
                self.acc601,
                self.acc521,
                day=6,
                journal=self.journals[workers // 2 + i],
            )
            for i in range(workers // 2)
        ]
        ids = [d.id for d in drafts_a + drafts_b]
        self._run_concurrent_posts(ids, workers=workers)

        for account in (self.acc411, self.acc701, self.acc601, self.acc521):
            self._assert_snapshot_matches_lines(account)

        total_mov_debit = sum(
            (
                BalanceSnapshot.objects.get(period=self.period, account=account).mov_debit
                for account in (self.acc411, self.acc701, self.acc601, self.acc521)
            ),
            Decimal("0"),
        )
        total_mov_credit = sum(
            (
                BalanceSnapshot.objects.get(period=self.period, account=account).mov_credit
                for account in (self.acc411, self.acc701, self.acc601, self.acc521)
            ),
            Decimal("0"),
        )
        self.assertEqual(total_mov_debit, total_mov_credit)
        self.assertEqual(total_mov_debit, Decimal("100") * workers)

    def test_opening_carried_when_first_concurrent_posts_hit_new_period(self):
        """Ouvertures reprises du mois précédent lors de la 1ʳᵉ création concurrente."""
        jan = self.period
        seed = self._draft("2000", self.acc411, self.acc701, day=15)
        post_entry(seed, None)

        february = AccountingPeriod.objects.create(
            organization=self.org,
            company=self.company,
            exercise=self.exercise,
            year=2026,
            month=2,
            starts_on=date(2026, 2, 1),
            ends_on=date(2026, 2, 28),
        )
        workers = 6
        drafts = []
        for i in range(workers):
            drafts.append(
                create_draft(
                    company=self.company,
                    journal=self.journals[i],
                    accounting_date=date(2026, 2, 1 + (i % 20)),
                    value_date=date(2026, 2, 1 + (i % 20)),
                    description="Février concurrent",
                    document_ref="ACC01-FEB",
                    raw_lines=[
                        {
                            "account_id": str(self.acc411.id),
                            "debit": "100",
                            "credit": "0",
                            "label": "Débit",
                        },
                        {
                            "account_id": str(self.acc701.id),
                            "debit": "0",
                            "credit": "100",
                            "label": "Crédit",
                        },
                    ],
                )
            )

        self._run_concurrent_posts([d.id for d in drafts], workers=workers)

        snap411 = BalanceSnapshot.objects.get(period=february, account=self.acc411)
        self.assertEqual(snap411.open_debit, Decimal("2000"))
        self.assertEqual(snap411.open_credit, Decimal("0"))
        debit, credit = posted_movement_totals(self.company, february, self.acc411)
        self.assertEqual(snap411.mov_debit, debit)
        self.assertEqual(snap411.mov_credit, credit)
        self.assertEqual(snap411.mov_debit, Decimal("100") * workers)
        # Janvier inchangé.
        jan_snap = BalanceSnapshot.objects.get(period=jan, account=self.acc411)
        self.assertEqual(jan_snap.mov_debit, Decimal("2000"))
