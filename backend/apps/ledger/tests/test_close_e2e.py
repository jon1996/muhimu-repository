"""CLOSE-01 — validation E2E du cycle clôture / affectation / à-nouveaux.

Résultats attendus calculés hors ``close_exercise`` (soldes lignes + formules locales).
Politique réouverture bêta : R0+R2 (aucun REOPEN self-service).
"""

from __future__ import annotations

import threading
from datetime import date
from decimal import Decimal

from django.db import connections, transaction
from django.test import Client, TransactionTestCase
from ninja.errors import HttpError

from apps.identity.models import User
from apps.ledger.models import (
    Account,
    AccountingPeriod,
    Entry,
    EntryLine,
    EntryStatus,
    Exercise,
    ExerciseStatus,
    Journal,
    JournalType,
)
from apps.ledger.services.balance import posted_movement_totals, trial_balance, trial_balance_ytd
from apps.ledger.services.closing import allocate_result, close_exercise, preview_close
from apps.ledger.services.opening import post_opening
from apps.ledger.services.posting import create_draft, post_entry, reverse_entry
from apps.ledger.services.sn_map import cr_amounts
from apps.tenancy.models import (
    Company,
    Membership,
    Organization,
    OrganizationType,
    Role,
)

ZERO = Decimal("0")


def _account(org, company, code: str, label: str) -> Account:
    account = Account(
        organization=org,
        company=company,
        code=code,
        label=label,
        is_postable=True,
        is_syscohada=True,
    )
    account.save()
    return account


def _line_totals(entry: Entry) -> tuple[Decimal, Decimal]:
    debit = sum((line.debit for line in entry.lines.all()), ZERO)
    credit = sum((line.credit for line in entry.lines.all()), ZERO)
    return debit, credit


class CloseE2EWorld:
    """Société XOF N=2025 avec journaux, périodes et comptes PCGO minimaux."""

    def __init__(self, *, slug: str = "close01", name: str = "SARL CLOSE-01"):
        self.org = Organization.objects.create(
            name=f"Org {name}", slug=slug, type=OrganizationType.SME
        )
        self.company = Company.objects.create(
            organization=self.org, name=name, currency_code="XOF"
        )
        self.year = 2025
        self.exercise = Exercise.objects.create(
            organization=self.org,
            company=self.company,
            year=self.year,
            starts_on=date(self.year, 1, 1),
            ends_on=date(self.year, 12, 31),
        )
        for month in range(1, 13):
            last = 31 if month in {1, 3, 5, 7, 8, 10, 12} else 30 if month != 2 else 28
            AccountingPeriod.objects.create(
                organization=self.org,
                company=self.company,
                exercise=self.exercise,
                year=self.year,
                month=month,
                starts_on=date(self.year, month, 1),
                ends_on=date(self.year, month, last),
            )
        self.journal = Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        codes = {
            "101": "Capital",
            "111": "Réserve légale",
            "118": "Réserves libres",
            "121": "Report à nouveau",
            "129": "Report à nouveau débiteur",
            "131": "Résultat — bénéfice",
            "139": "Résultat — perte",
            "401": "Fournisseurs",
            "411": "Clients",
            "465": "Dividendes à payer",
            "521": "Banques",
            "601": "Achats marchandises",
            "622": "Rémunérations d'intermédiaires",
            "701": "Ventes marchandises",
        }
        self.accounts = {
            code: _account(self.org, self.company, code, label)
            for code, label in codes.items()
        }

    def post(self, day: int, description: str, lines: list[tuple[str, str, str]]) -> Entry:
        raw = [
            {
                "account_id": str(self.accounts[code].id),
                "debit": debit,
                "credit": credit,
                "label": description,
            }
            for code, debit, credit in lines
        ]
        draft = create_draft(
            company=self.company,
            journal=self.journal,
            accounting_date=date(self.year, 1, day),
            value_date=date(self.year, 1, day),
            description=description,
            document_ref=f"CLOSE01-{day}-{description[:12]}",
            raw_lines=raw,
        )
        return post_entry(draft, None)

    def seed_profit(self) -> dict[str, Decimal]:
        """Capital 5M, achats 1.8M, ventes 2.1M, charges 0.2M → bénéfice attendu 100_000."""
        self.post(
            2,
            "Apport capital",
            [("521", "5000000", "0"), ("101", "0", "5000000")],
        )
        self.post(
            5,
            "Achats",
            [("601", "1800000", "0"), ("521", "0", "1800000")],
        )
        self.post(
            10,
            "Ventes",
            [("521", "2100000", "0"), ("701", "0", "2100000")],
        )
        self.post(
            15,
            "Charges",
            [("622", "200000", "0"), ("521", "0", "200000")],
        )
        # Attendu indépendant : ventes − achats − charges
        expected_xi = Decimal("2100000") - Decimal("1800000") - Decimal("200000")
        return {
            "expected_xi": expected_xi,
            "expected_revenue": Decimal("2100000"),
            "capital": Decimal("5000000"),
        }

    def seed_loss(self) -> dict[str, Decimal]:
        self.post(
            2,
            "Apport capital",
            [("521", "1000000", "0"), ("101", "0", "1000000")],
        )
        self.post(
            8,
            "Charges seules",
            [("622", "300000", "0"), ("521", "0", "300000")],
        )
        return {"expected_xi": Decimal("-300000"), "expected_revenue": ZERO}


class CloseE2ETests(TransactionTestCase):
    def test_01_close_balanced_profit_exercise(self):
        world = CloseE2EWorld(slug="close01-bal")
        expect = world.seed_profit()
        preview = preview_close(world.company, world.exercise)
        self.assertTrue(preview["can_close"], preview["blockers"])
        self.assertEqual(preview["net_result"], expect["expected_xi"])

        closed = close_exercise(world.company, world.exercise, None, closed_on=date(2026, 1, 15))
        self.assertEqual(closed.status, ExerciseStatus.CLOSED)
        self.assertEqual(closed.net_result, expect["expected_xi"])
        self.assertIsNotNone(closed.result_entry_id)

        result = Entry.objects.get(pk=closed.result_entry_id)
        self.assertEqual(result.status, EntryStatus.POSTED)
        self.assertEqual(result.source, "result_close")
        debit, credit = _line_totals(result)
        self.assertEqual(debit, credit)
        self.assertGreater(debit, ZERO)

        by_code = {
            line.account.code: line.debit - line.credit for line in result.lines.all()
        }
        # Classes 6/7 soldées via OD ; 131 créditeur du bénéfice
        self.assertEqual(by_code.get("131", ZERO), -expect["expected_xi"])
        ytd = {row["code"]: row for row in trial_balance_ytd(world.company, closed)}
        self.assertEqual(
            ytd["601"]["close_debit"] - ytd["601"]["close_credit"],
            ZERO,
        )
        self.assertEqual(
            ytd["701"]["close_debit"] - ytd["701"]["close_credit"],
            ZERO,
        )
        self.assertEqual(
            ytd["131"]["close_credit"] - ytd["131"]["close_debit"],
            expect["expected_xi"],
        )

    def test_02_close_with_profit_matches_independent_xi(self):
        world = CloseE2EWorld(slug="close01-profit")
        expect = world.seed_profit()
        rows = trial_balance_ytd(world.company, world.exercise)
        independent = cr_amounts(rows)["XI"]
        self.assertEqual(independent, expect["expected_xi"])
        closed = close_exercise(world.company, world.exercise, None)
        self.assertEqual(closed.net_result, independent)

    def test_03_close_with_loss(self):
        world = CloseE2EWorld(slug="close01-loss")
        expect = world.seed_loss()
        closed = close_exercise(world.company, world.exercise, None)
        self.assertEqual(closed.net_result, expect["expected_xi"])
        result = Entry.objects.get(pk=closed.result_entry_id)
        debit, credit = _line_totals(result)
        self.assertEqual(debit, credit)
        line_139 = result.lines.get(account=world.accounts["139"])
        self.assertEqual(line_139.debit, -expect["expected_xi"])

    def test_04_close_empty_operations_bs_only(self):
        world = CloseE2EWorld(slug="close01-empty")
        world.post(
            3,
            "Capital seul",
            [("521", "100000", "0"), ("101", "0", "100000")],
        )
        preview = preview_close(world.company, world.exercise)
        self.assertTrue(preview["can_close"])
        self.assertEqual(preview["net_result"], ZERO)
        closed = close_exercise(world.company, world.exercise, None)
        self.assertEqual(closed.status, ExerciseStatus.CLOSED)
        self.assertEqual(closed.net_result, ZERO)
        self.assertIsNone(closed.result_entry_id)
        self.assertEqual(
            Entry.objects.filter(exercise=closed, source="result_close").count(),
            0,
        )

    def test_05_refuse_close_with_drafts(self):
        world = CloseE2EWorld(slug="close01-draft")
        world.seed_profit()
        create_draft(
            company=world.company,
            journal=world.journal,
            accounting_date=date(2025, 1, 20),
            value_date=date(2025, 1, 20),
            description="Brouillon bloquant",
            document_ref="DRAFT-1",
            raw_lines=[
                {
                    "account_id": str(world.accounts["521"].id),
                    "debit": "10",
                    "credit": "0",
                },
                {
                    "account_id": str(world.accounts["701"].id),
                    "debit": "0",
                    "credit": "10",
                },
            ],
        )
        preview = preview_close(world.company, world.exercise)
        self.assertFalse(preview["can_close"])
        with self.assertRaises(HttpError) as ctx:
            close_exercise(world.company, world.exercise, None)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_06_refuse_second_close_no_duplicate(self):
        world = CloseE2EWorld(slug="close01-twice")
        world.seed_profit()
        close_exercise(world.company, world.exercise, None)
        with self.assertRaises(HttpError) as ctx:
            close_exercise(world.company, world.exercise, None)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(
            Entry.objects.filter(
                company=world.company, source="result_close", status=EntryStatus.POSTED
            ).count(),
            1,
        )

    def test_07_refuse_post_on_closed_exercise(self):
        world = CloseE2EWorld(slug="close01-nopost")
        world.seed_profit()
        close_exercise(world.company, world.exercise, None)
        with self.assertRaises(HttpError):
            world.post(
                25,
                "Après clôture",
                [("521", "1", "0"), ("701", "0", "1")],
            )

    def test_08_allocate_profit(self):
        world = CloseE2EWorld(slug="close01-alloc")
        expect = world.seed_profit()
        closed = close_exercise(world.company, world.exercise, None)
        # Réserve légale 10 % = 10_000 ; RAN = reste
        legal = Decimal("10000")
        retained = expect["expected_xi"] - legal
        allocated = allocate_result(
            world.company,
            closed,
            None,
            {
                "approved_on": date(2026, 3, 1),
                "legal_reserve": str(legal),
                "free_reserve": "0",
                "retained": str(retained),
                "dividends": "0",
            },
        )
        self.assertIsNotNone(allocated.allocation_entry_id)
        alloc = Entry.objects.get(pk=allocated.allocation_entry_id)
        self.assertEqual(alloc.status, EntryStatus.POSTED)
        debit, credit = _line_totals(alloc)
        self.assertEqual(debit, credit)
        self.assertEqual(debit, expect["expected_xi"])
        self.assertEqual(allocated.legal_reserve_amount, legal)
        self.assertEqual(allocated.retained_amount, retained)
        # Affectation sur N+1
        self.assertEqual(alloc.exercise.year, 2026)
        with self.assertRaises(HttpError):
            allocate_result(
                world.company,
                allocated,
                None,
                {
                    "approved_on": date(2026, 3, 2),
                    "legal_reserve": str(legal),
                    "free_reserve": "0",
                    "retained": str(retained),
                    "dividends": "0",
                },
            )

    def test_09_opening_n1_matches_closing_balances(self):
        world = CloseE2EWorld(slug="close01-an")
        expect = world.seed_profit()
        closed = close_exercise(world.company, world.exercise, None)
        next_ex = Exercise.objects.get(company=world.company, year=2026)
        # Après clôture (avant affectation) : BS + 131 ; pas de 6/7
        bank = Decimal("5000000") - Decimal("1800000") + Decimal("2100000") - Decimal("200000")
        opening_lines = [
            {"code": "521", "debit": format(bank, "f"), "credit": "0"},
            {"code": "101", "debit": "0", "credit": "5000000"},
            {
                "code": "131",
                "debit": "0",
                "credit": format(expect["expected_xi"], "f"),
            },
        ]
        result = post_opening(world.company, next_ex, None, opening_lines)
        self.assertTrue(result["posted"])
        an = Entry.objects.get(id=result["entry_id"])
        self.assertEqual(an.source, "opening")
        debit, credit = _line_totals(an)
        self.assertEqual(debit, credit)
        codes = {line.account.code for line in an.lines.all()}
        self.assertNotIn("601", codes)
        self.assertNotIn("701", codes)
        self.assertNotIn("622", codes)
        january = next_ex.periods.get(month=1)
        rows = {row["code"]: row for row in trial_balance(world.company, january)}
        self.assertEqual(rows["521"]["mov_debit"], bank)
        self.assertEqual(rows["101"]["mov_credit"], Decimal("5000000"))
        self.assertEqual(rows["131"]["mov_credit"], expect["expected_xi"])
        # Affectation ensuite sur N+1 (mécanisme existant)
        allocate_result(
            world.company,
            closed,
            None,
            {
                "approved_on": date(2026, 3, 1),
                "legal_reserve": "10000",
                "free_reserve": "0",
                "retained": str(expect["expected_xi"] - Decimal("10000")),
                "dividends": "0",
            },
        )

    def test_10_isolation_two_companies(self):
        a = CloseE2EWorld(slug="close01-iso-a", name="Cie A")
        b = CloseE2EWorld(slug="close01-iso-b", name="Cie B")
        a.seed_profit()
        b.seed_loss()
        close_exercise(a.company, a.exercise, None)
        self.assertEqual(b.exercise.status, ExerciseStatus.OPEN)
        self.assertEqual(
            Entry.objects.filter(company=b.company, source="result_close").count(),
            0,
        )
        close_exercise(b.company, b.exercise, None)
        self.assertEqual(
            Exercise.objects.get(pk=a.exercise.pk).net_result,
            Decimal("100000"),
        )
        self.assertEqual(
            Exercise.objects.get(pk=b.exercise.pk).net_result,
            Decimal("-300000"),
        )

    def test_11_transactional_rollback_no_partial_close(self):
        world = CloseE2EWorld(slug="close01-rollback")
        world.seed_profit()
        try:
            with transaction.atomic():
                close_exercise(world.company, world.exercise, None)
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass
        world.exercise.refresh_from_db()
        self.assertEqual(world.exercise.status, ExerciseStatus.OPEN)
        self.assertEqual(
            Entry.objects.filter(company=world.company, source="result_close").count(),
            0,
        )

    def test_12_concurrent_close_no_duplicate(self):
        world = CloseE2EWorld(slug="close01-conc")
        world.seed_profit()
        exercise_id = str(world.exercise.id)
        company_id = str(world.company.id)
        results: list[str] = []

        def worker():
            connections.close_all()
            try:
                company = Company.objects.get(pk=company_id)
                exercise = Exercise.objects.get(pk=exercise_id)
                close_exercise(company, exercise, None)
                results.append("ok")
            except HttpError as exc:
                results.append(f"http:{exc.status_code}")
            except Exception as exc:  # noqa: BLE001 — concurrence
                results.append(f"err:{exc.__class__.__name__}")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        self.assertEqual(results.count("ok"), 1, results)
        self.assertEqual(
            Entry.objects.filter(
                company=world.company, source="result_close", status=EntryStatus.POSTED
            ).count(),
            1,
        )
        self.assertEqual(
            Exercise.objects.get(pk=exercise_id).status,
            ExerciseStatus.CLOSED,
        )

    def test_13_posted_close_entry_immutable_acc02_acc03(self):
        world = CloseE2EWorld(slug="close01-imm")
        world.seed_profit()
        closed = close_exercise(world.company, world.exercise, None)
        result = Entry.objects.get(pk=closed.result_entry_id)
        line = result.lines.first()
        from django.core.exceptions import ValidationError
        from django.db.utils import Error as DbError

        with self.assertRaises(ValidationError):
            EntryLine.objects.filter(pk=line.pk).update(debit=Decimal("1"))
        with self.assertRaises(DbError):
            with transaction.atomic():
                with connections["default"].cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {EntryLine._meta.db_table} SET debit = %s WHERE id = %s",
                        [Decimal("1"), str(line.id)],
                    )

    def test_14_reverse_does_not_reopen_closed_exercise(self):
        world = CloseE2EWorld(slug="close01-rev")
        world.seed_profit()
        closed = close_exercise(world.company, world.exercise, None)
        result = Entry.objects.get(pk=closed.result_entry_id)
        origin_debit = result.lines.first().debit
        # Contrepassation éventuelle sur N+1 (ouvert) : R2 — sans réouvrir N.
        try:
            reverse_entry(result, None, description="Correction N+1")
        except HttpError:
            pass
        closed.refresh_from_db()
        self.assertEqual(closed.status, ExerciseStatus.CLOSED)
        result.refresh_from_db()
        self.assertEqual(result.status, EntryStatus.POSTED)
        self.assertEqual(result.lines.first().debit, origin_debit)

    def test_15_no_reopen_self_service(self):
        from apps.ledger import services as ledger_services
        from apps.ledger.services import closing as closing_mod

        self.assertFalse(hasattr(closing_mod, "reopen_exercise"))
        self.assertFalse(hasattr(ledger_services, "reopen_exercise"))
        world = CloseE2EWorld(slug="close01-noreopen")
        world.seed_profit()
        close_exercise(world.company, world.exercise, None)
        with self.assertRaises(HttpError):
            post_opening(
                world.company,
                world.exercise,
                None,
                [
                    {"code": "521", "debit": "100", "credit": "0"},
                    {"code": "101", "debit": "0", "credit": "100"},
                ],
            )

    def test_16_allocate_loss_to_ran(self):
        world = CloseE2EWorld(slug="close01-loss-alloc")
        expect = world.seed_loss()
        closed = close_exercise(world.company, world.exercise, None)
        allocated = allocate_result(
            world.company,
            closed,
            None,
            {
                "approved_on": date(2026, 2, 1),
                "legal_reserve": "0",
                "free_reserve": "0",
                "retained": str(-expect["expected_xi"]),
                "dividends": "0",
            },
        )
        alloc = Entry.objects.get(pk=allocated.allocation_entry_id)
        debit, credit = _line_totals(alloc)
        self.assertEqual(debit, credit)
        self.assertEqual(
            alloc.lines.get(account=world.accounts["129"]).debit,
            -expect["expected_xi"],
        )

    def test_17_snapshots_acc01_consistent_after_close(self):
        world = CloseE2EWorld(slug="close01-snap")
        world.seed_profit()
        closed = close_exercise(world.company, world.exercise, None)
        result = Entry.objects.get(pk=closed.result_entry_id)
        period = result.period
        for line in result.lines.select_related("account"):
            mov_d, mov_c = posted_movement_totals(world.company, period, line.account)
            # La vérité terrain période = SUM lignes POSTED ; snapshots mis à jour à post
            from apps.ledger.models import BalanceSnapshot

            snap = BalanceSnapshot.objects.get(period=period, account=line.account)
            # mov snapshot doit coller au total des mouvements de la période
            self.assertEqual(snap.mov_debit, mov_d)
            self.assertEqual(snap.mov_credit, mov_c)

    def test_18_unauthorized_and_cross_company_api(self):
        world = CloseE2EWorld(slug="close01-api")
        world.seed_profit()
        viewer = User.objects.create_user(
            email="viewer-close01@test.local", password="View1234!", full_name="Viewer"
        )
        Membership.objects.create(
            organization=world.org, user=viewer, role=Role.VIEWER
        )
        client = Client()
        client.force_login(viewer)
        response = client.post(
            "/api/ledger/exercise/close",
            data={"year": world.year},
            content_type="application/json",
            HTTP_X_ORGANIZATION_SLUG=world.org.slug,
            HTTP_X_COMPANY_ID=str(world.company.id),
        )
        self.assertEqual(response.status_code, 403)

        other = CloseE2EWorld(slug="close01-api-b", name="Autre")
        other.seed_profit()
        accountant = User.objects.create_user(
            email="acc-close01@test.local", password="Acc1234!", full_name="Acc"
        )
        Membership.objects.create(
            organization=world.org, user=accountant, role=Role.ACCOUNTANT
        )
        client.force_login(accountant)
        # Tentative de clôturer l'exercice de l'autre société via en-tête société A
        # mais année uniquement — l'API résout l'exercice de la société active.
        response = client.post(
            "/api/ledger/exercise/close",
            data={"year": other.year},
            content_type="application/json",
            HTTP_X_ORGANIZATION_SLUG=world.org.slug,
            HTTP_X_COMPANY_ID=str(world.company.id),
        )
        # Exercice other.year sur company world → existe ; close world (profit)
        self.assertIn(response.status_code, {200, 201})
        other.exercise.refresh_from_db()
        self.assertEqual(other.exercise.status, ExerciseStatus.OPEN)

    def test_19_ytd_includes_january_movements(self):
        """Contrôle du correctif technique trial_balance_ytd (CLOSE-01)."""
        world = CloseE2EWorld(slug="close01-ytd")
        expect = world.seed_profit()
        december = world.exercise.periods.get(month=12)
        dec_rows = trial_balance(world.company, december)
        ytd_rows = trial_balance_ytd(world.company, world.exercise)
        # Décembre seul : souvent vide si aucune écriture en décembre
        self.assertEqual(cr_amounts(ytd_rows)["XI"], expect["expected_xi"])
        if not dec_rows:
            self.assertNotEqual(cr_amounts(dec_rows or []).get("XI", ZERO), expect["expected_xi"])
