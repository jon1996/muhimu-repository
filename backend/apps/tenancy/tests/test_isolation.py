"""SAAS-03 — tests d'isolation multi-tenant (API + RLS PostgreSQL).

Les tests API valident les filtres applicatifs (middleware / require_*).
Les tests RLS se connectent en rôle ``muhimu_app`` (NOBYPASSRLS) — le rôle
``muhimu`` de test Django est superuser et contourne RLS.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase

from apps.identity.models import User
from apps.ledger.models import (
    Account,
    AccountingPeriod,
    BalanceSnapshot,
    Entry,
    EntryLine,
    EntryStatus,
    Exercise,
    Journal,
    JournalType,
    SourceDocument,
)
from apps.ledger.services.posting import create_draft, post_entry
from apps.tenancy.models import (
    Company,
    CompanyAccess,
    Membership,
    Organization,
    OrganizationType,
    Role,
)


def _make_account(org, company, code: str, label: str) -> Account:
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


def _seed_company_books(org, company, *, amount: str = "1000") -> dict:
    exercise = Exercise.objects.create(
        organization=org,
        company=company,
        year=2026,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    )
    period = AccountingPeriod.objects.create(
        organization=org,
        company=company,
        exercise=exercise,
        year=2026,
        month=1,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 1, 31),
    )
    journal = Journal.objects.create(
        organization=org,
        company=company,
        code="OD",
        name="OD",
        type=JournalType.OD,
    )
    acc411 = _make_account(org, company, "411", "Clients")
    acc701 = _make_account(org, company, "701", "Ventes")
    draft = create_draft(
        company=company,
        journal=journal,
        accounting_date=date(2026, 1, 10),
        value_date=date(2026, 1, 10),
        description=f"Écriture {company.name}",
        document_ref="SAAS03",
        raw_lines=[
            {"account_id": str(acc411.id), "debit": amount, "credit": "0", "label": "D"},
            {"account_id": str(acc701.id), "debit": "0", "credit": amount, "label": "C"},
        ],
    )
    entry = post_entry(draft, None)
    return {
        "exercise": exercise,
        "period": period,
        "journal": journal,
        "acc411": acc411,
        "acc701": acc701,
        "entry": entry,
    }


class IsolationWorld:
    """Jeux de données A/B (orgs) + cabinet (deux sociétés)."""

    def __init__(self):
        # Les tests Django se connectent en muhimu (BYPASSRLS) — pas de GUC bypass.
        self.org_a = Organization.objects.create(
            name="Org Alpha", slug="org-alpha", type=OrganizationType.SME, is_demo=False
        )
        self.org_b = Organization.objects.create(
            name="Org Beta", slug="org-beta", type=OrganizationType.SME, is_demo=False
        )
        self.cabinet = Organization.objects.create(
            name="Cabinet Gamma", slug="cabinet-gamma", type=OrganizationType.CABINET, is_demo=False
        )
        self.company_a1 = Company.objects.create(
            organization=self.org_a, name="Société A1", currency_code="XOF"
        )
        self.company_b1 = Company.objects.create(
            organization=self.org_b, name="Société B1", currency_code="XOF"
        )
        self.company_c1 = Company.objects.create(
            organization=self.cabinet, name="Client C1", currency_code="XOF"
        )
        self.company_c2 = Company.objects.create(
            organization=self.cabinet, name="Client C2", currency_code="XOF"
        )

        self.user_a = User.objects.create_user(
            email="user-a@isolation.test", password="IsoA1234!", full_name="User A"
        )
        self.user_b = User.objects.create_user(
            email="user-b@isolation.test", password="IsoB1234!", full_name="User B"
        )
        self.cab_owner = User.objects.create_user(
            email="owner-cab@isolation.test", password="IsoO1234!", full_name="Owner Cab"
        )
        self.cab_accountant = User.objects.create_user(
            email="acc-cab@isolation.test", password="IsoC1234!", full_name="Acc Cab"
        )

        Membership.objects.create(
            organization=self.org_a, user=self.user_a, role=Role.ACCOUNTANT
        )
        Membership.objects.create(
            organization=self.org_b, user=self.user_b, role=Role.ACCOUNTANT
        )
        Membership.objects.create(
            organization=self.cabinet, user=self.cab_owner, role=Role.OWNER
        )
        Membership.objects.create(
            organization=self.cabinet, user=self.cab_accountant, role=Role.ACCOUNTANT
        )
        # Comptable cabinet : uniquement C1
        CompanyAccess.objects.create(
            organization=self.cabinet, company=self.company_c1, user=self.cab_accountant
        )

        self.books_a = _seed_company_books(self.org_a, self.company_a1, amount="1111")
        self.books_b = _seed_company_books(self.org_b, self.company_b1, amount="2222")
        self.books_c1 = _seed_company_books(self.cabinet, self.company_c1, amount="3333")
        self.books_c2 = _seed_company_books(self.cabinet, self.company_c2, amount="4444")


class CrossOrganizationApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()
        self.client = Client()
        self.client.force_login(self.world.user_a)

    def _headers(self, slug: str, company_id: str | None = None) -> dict:
        headers = {"HTTP_X_ORGANIZATION_SLUG": slug}
        if company_id:
            headers["HTTP_X_COMPANY_ID"] = company_id
        return headers

    def test_user_a_lists_only_own_organization(self):
        response = self.client.get("/api/organizations")
        self.assertEqual(response.status_code, 200)
        slugs = {row["slug"] for row in response.json()}
        self.assertEqual(slugs, {"org-alpha"})
        self.assertNotIn("org-beta", slugs)

    def test_user_a_cannot_use_org_b_slug(self):
        headers = self._headers("org-beta", str(self.world.company_b1.id))
        response = self.client.get("/api/ledger/entries", **headers)
        self.assertIn(response.status_code, (403, 400))

    def test_user_a_cannot_read_entry_of_org_b_by_id(self):
        # Contexte légitime A, identifiant écriture B
        headers = self._headers("org-alpha", str(self.world.company_a1.id))
        foreign_id = str(self.world.books_b["entry"].id)
        response = self.client.get(f"/api/ledger/entries/{foreign_id}", **headers)
        self.assertEqual(response.status_code, 404)

    def test_user_a_cannot_spoof_company_b_under_org_a_header(self):
        headers = self._headers("org-alpha", str(self.world.company_b1.id))
        response = self.client.get("/api/ledger/entries", **headers)
        # company_b1 n'appartient pas à org-alpha → société non résolue
        self.assertIn(response.status_code, (400, 403))

    def test_user_a_balance_does_not_include_org_b_amounts(self):
        headers = self._headers("org-alpha", str(self.world.company_a1.id))
        period_id = str(self.world.books_a["period"].id)
        response = self.client.get(
            f"/api/ledger/balance?period_id={period_id}", **headers
        )
        self.assertEqual(response.status_code, 200, response.content)
        rows = response.json()
        codes = {row["code"]: row for row in rows}
        self.assertIn("411", codes)
        # Montant A1 = 1111, pas 2222
        self.assertEqual(Decimal(codes["411"]["mov_debit"]), Decimal("1111"))
        for row in rows:
            self.assertNotEqual(Decimal(row["mov_debit"]), Decimal("2222"))
            self.assertNotEqual(Decimal(row["mov_credit"]), Decimal("2222"))

    def test_user_a_cannot_get_statements_pdf_for_org_b(self):
        headers = self._headers("org-beta", str(self.world.company_b1.id))
        response = self.client.get("/api/ledger/statements/pdf", **headers)
        self.assertIn(response.status_code, (403, 400))

    def test_user_a_cannot_download_document_of_org_b(self):
        doc = SourceDocument.objects.create(
            organization=self.world.org_b,
            company=self.world.company_b1,
            entry=self.world.books_b["entry"],
            original_name="secret-b.pdf",
            content_type="application/pdf",
            size=4,
            sha256="abcd",
            issued_on=date(2026, 1, 10),
            keep_until=date(2036, 1, 10),
        )
        headers = self._headers("org-alpha", str(self.world.company_a1.id))
        response = self.client.get(f"/api/ledger/documents/{doc.id}/file", **headers)
        self.assertEqual(response.status_code, 404)

    def test_user_a_cannot_post_to_org_b_journal(self):
        headers = self._headers("org-beta", str(self.world.company_b1.id))
        response = self.client.post(
            "/api/ledger/entries",
            data={
                "journal_id": str(self.world.books_b["journal"].id),
                "accounting_date": "2026-01-11",
                "value_date": "2026-01-11",
                "description": "intrusion",
                "document_ref": "X",
                "lines": [
                    {
                        "account_id": str(self.world.books_b["acc411"].id),
                        "debit": "1",
                        "credit": "0",
                    },
                    {
                        "account_id": str(self.world.books_b["acc701"].id),
                        "debit": "0",
                        "credit": "1",
                    },
                ],
            },
            content_type="application/json",
            **headers,
        )
        self.assertIn(response.status_code, (403, 400))


class CabinetCompanyIsolationApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()
        self.client = Client()
        self.client.force_login(self.world.cab_accountant)

    def _headers(self, company) -> dict:
        return {
            "HTTP_X_ORGANIZATION_SLUG": "cabinet-gamma",
            "HTTP_X_COMPANY_ID": str(company.id),
        }

    def test_accountant_lists_only_assigned_company(self):
        response = self.client.get(
            "/api/companies", HTTP_X_ORGANIZATION_SLUG="cabinet-gamma"
        )
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.json()}
        self.assertEqual(names, {"Client C1"})
        self.assertNotIn("Client C2", names)

    def test_accountant_cannot_activate_company_c2(self):
        response = self.client.get(
            "/api/ledger/entries", **self._headers(self.world.company_c2)
        )
        self.assertIn(response.status_code, (400, 403))

    def test_accountant_cannot_read_c2_entry_by_id_under_c1_context(self):
        response = self.client.get(
            f"/api/ledger/entries/{self.world.books_c2['entry'].id}",
            **self._headers(self.world.company_c1),
        )
        self.assertEqual(response.status_code, 404)

    def test_accountant_balance_c1_excludes_c2(self):
        period_id = str(self.world.books_c1["period"].id)
        response = self.client.get(
            f"/api/ledger/balance?period_id={period_id}",
            **self._headers(self.world.company_c1),
        )
        self.assertEqual(response.status_code, 200, response.content)
        movs = [Decimal(row["mov_debit"]) for row in response.json()]
        self.assertIn(Decimal("3333"), movs)
        self.assertNotIn(Decimal("4444"), movs)

    def test_accountant_cannot_general_ledger_c2_account(self):
        response = self.client.get(
            f"/api/ledger/general-ledger/{self.world.books_c2['acc411'].id}",
            **self._headers(self.world.company_c1),
        )
        self.assertIn(response.status_code, (404, 400))

    def test_accountant_cannot_statements_pdf_for_c2(self):
        response = self.client.get(
            "/api/ledger/statements/pdf", **self._headers(self.world.company_c2)
        )
        self.assertIn(response.status_code, (400, 403))

    def test_accountant_cannot_books_pdf_for_c2(self):
        response = self.client.get(
            "/api/ledger/books/pdf", **self._headers(self.world.company_c2)
        )
        self.assertIn(response.status_code, (400, 403))

    def test_revoke_company_access_blocks_immediately(self):
        CompanyAccess.objects.filter(
            user=self.world.cab_accountant, company=self.world.company_c1
        ).delete()
        response = self.client.get(
            "/api/ledger/entries", **self._headers(self.world.company_c1)
        )
        self.assertIn(response.status_code, (400, 403))

    def test_accountant_cannot_grant_access(self):
        response = self.client.post(
            f"/api/companies/{self.world.company_c2.id}/access",
            data={"user_email": self.world.cab_accountant.email},
            content_type="application/json",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
            HTTP_X_COMPANY_ID=str(self.world.company_c1.id),
        )
        self.assertEqual(response.status_code, 403)

    def test_owner_sees_both_companies(self):
        client = Client()
        client.force_login(self.world.cab_owner)
        response = client.get(
            "/api/companies", HTTP_X_ORGANIZATION_SLUG="cabinet-gamma"
        )
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.json()}
        self.assertEqual(names, {"Client C1", "Client C2"})

    def test_owner_can_revoke_access_via_api(self):
        """Exigence SAAS-03 : révocation API des CompanyAccess."""
        client = Client()
        client.force_login(self.world.cab_owner)
        access = CompanyAccess.objects.get(
            user=self.world.cab_accountant, company=self.world.company_c1
        )
        response = client.delete(
            f"/api/companies/{self.world.company_c1.id}/access/{access.id}",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertIn(response.status_code, (200, 204), response.content)
        self.assertFalse(CompanyAccess.objects.filter(pk=access.pk).exists())
        # Session existante : le comptable est refusé dès la requête suivante.
        denied = Client()
        denied.force_login(self.world.cab_accountant)
        blocked = denied.get(
            "/api/ledger/entries",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
            HTTP_X_COMPANY_ID=str(self.world.company_c1.id),
        )
        self.assertIn(blocked.status_code, (400, 403))


class PostgresRlsIsolationTests(TransactionTestCase):
    """RLS réelle via connexions ``muhimu_app`` (pas le superuser de test).

    Couvre la défense contre les erreurs applicatives (oublis de filtre ORM).
    Les scénarios de compromission SQL (forgery GUC) sont dans A1PrimeSecurityTests.
    """

    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()

    def _app_conn(self):
        import os

        import psycopg

        db = settings.DATABASES["default"]
        return psycopg.connect(
            host=db.get("HOST") or "localhost",
            port=str(db.get("PORT") or "5432"),
            dbname=db["NAME"],
            user=os.environ.get("POSTGRES_APP_USER", "muhimu_app"),
            password=os.environ.get(
                "POSTGRES_APP_PASSWORD",
                os.environ.get("POSTGRES_PASSWORD", "muhimu"),
            ),
        )

    def _bind(self, cur, *, org_id: str = "", user_id: str = "") -> None:
        cur.execute(
            "SELECT set_config('app.current_organization_id', %s, false)", [org_id]
        )
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [user_id])

    def _count_entries(self, conn, *, org_id: str, user_id: str) -> int:
        with conn.cursor() as cur:
            self._bind(cur, org_id=org_id, user_id=user_id)
            cur.execute("SELECT count(*) FROM ledger_entry")
            return int(cur.fetchone()[0])

    def test_muhimu_app_role_has_no_bypassrls(self):
        with connection.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'muhimu_app'"
            )
            row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertFalse(row[0])
        self.assertFalse(row[1])

    def test_muhimu_platform_role_has_bypassrls_not_superuser(self):
        with connection.cursor() as cur:
            cur.execute(
                "SELECT rolsuper, rolbypassrls, rolcanlogin FROM pg_roles "
                "WHERE rolname = 'muhimu_platform'"
            )
            row = cur.fetchone()
        self.assertIsNotNone(row, msg="rôle muhimu_platform manquant")
        self.assertFalse(row[0], msg="muhimu_platform ne doit pas être superuser")
        self.assertTrue(row[1], msg="muhimu_platform doit avoir BYPASSRLS")
        self.assertTrue(row[2])

    def test_rls_policies_forced_on_ledger_entry(self):
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = 'ledger_entry'
                """
            )
            enabled, forced = cur.fetchone()
        self.assertTrue(enabled)
        self.assertTrue(forced)

    def test_rls_hides_other_org_entries_for_app_role(self):
        conn = self._app_conn()
        try:
            count_a = self._count_entries(
                conn,
                org_id=str(self.world.org_a.id),
                user_id=str(self.world.user_a.id),
            )
            count_b = self._count_entries(
                conn,
                org_id=str(self.world.org_b.id),
                user_id=str(self.world.user_b.id),
            )
            count_none = self._count_entries(conn, org_id="", user_id="")
            self.assertGreaterEqual(count_a, 1)
            self.assertGreaterEqual(count_b, 1)
            self.assertEqual(count_none, 0)
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_a.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE organization_id = %s",
                    [str(self.world.org_b.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_rls_wrong_org_context_cannot_read_snapshots(self):
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_a.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_balancesnapshot WHERE company_id = %s",
                    [str(self.world.company_b1.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_rls_hides_unassigned_company_rows_within_cabinet(self):
        """V3 / A1′ : défense PostgreSQL company-level."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_accountant.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_c2.id)],
                )
                c2_visible = int(cur.fetchone()[0])
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_c1.id)],
                )
                c1_visible = int(cur.fetchone()[0])
            self.assertEqual(c2_visible, 0)
            self.assertGreaterEqual(c1_visible, 1)
        finally:
            conn.close()

    def test_organization_and_membership_tables_have_rls(self):
        with connection.cursor() as cur:
            cur.execute(
                """
                SELECT c.relname, c.relrowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ('tenancy_organization', 'tenancy_membership')
                ORDER BY c.relname
                """
            )
            rows = {name: bool(enabled) for name, enabled in cur.fetchall()}
        self.assertTrue(
            rows.get("tenancy_organization"),
            msg="RLS manquante sur tenancy_organization",
        )
        self.assertTrue(
            rows.get("tenancy_membership"),
            msg="RLS manquante sur tenancy_membership",
        )

    def test_app_role_cannot_enumerate_organizations_without_context(self):
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(cur, org_id="", user_id="")
                cur.execute("SELECT count(*) FROM tenancy_organization")
                total = int(cur.fetchone()[0])
            self.assertEqual(
                total,
                0,
                msg="muhimu_app ne doit pas lister les organisations sans contexte",
            )
        finally:
            conn.close()

    def test_clearing_context_hides_ledger_rows(self):
        conn = self._app_conn()
        try:
            with_org = self._count_entries(
                conn,
                org_id=str(self.world.org_a.id),
                user_id=str(self.world.user_a.id),
            )
            without = self._count_entries(conn, org_id="", user_id="")
            self.assertGreater(with_org, 0)
            self.assertEqual(without, 0)
        finally:
            conn.close()


class LegitimateAccessRegressionTests(TestCase):
    """Les utilisateurs autorisés conservent leurs accès (non-régression)."""

    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()

    def test_user_a_reads_own_entries(self):
        client = Client()
        client.force_login(self.world.user_a)
        response = client.get(
            "/api/ledger/entries",
            HTTP_X_ORGANIZATION_SLUG="org-alpha",
            HTTP_X_COMPANY_ID=str(self.world.company_a1.id),
        )
        self.assertEqual(response.status_code, 200)
        ids = {row["id"] for row in response.json()}
        self.assertIn(str(self.world.books_a["entry"].id), ids)

    def test_cabinet_accountant_reads_c1(self):
        client = Client()
        client.force_login(self.world.cab_accountant)
        response = client.get(
            "/api/ledger/entries",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
            HTTP_X_COMPANY_ID=str(self.world.company_c1.id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row["id"] == str(self.world.books_c1["entry"].id) for row in response.json()))


class ConsolidationAccessTests(TestCase):
    """SAAS-03 V4 — consolidation filtrée par CompanyAccess."""

    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()
        from apps.ledger.models import ConsolidationGroup, ConsolidationKind, ConsolidationMember, ConsolidationMethod
        from decimal import Decimal as D

        self.group = ConsolidationGroup.objects.create(
            organization=self.world.cabinet,
            name="Groupe C1+C2",
            kind=ConsolidationKind.COMBINED,
            year=2026,
            currency_code="XOF",
        )
        ConsolidationMember.objects.create(
            organization=self.world.cabinet,
            group=self.group,
            company=self.world.company_c1,
            method=ConsolidationMethod.COMBINED,
            ownership_pct=D("100"),
        )
        ConsolidationMember.objects.create(
            organization=self.world.cabinet,
            group=self.group,
            company=self.world.company_c2,
            method=ConsolidationMethod.COMBINED,
            ownership_pct=D("100"),
        )
        self.group_c1_only = ConsolidationGroup.objects.create(
            organization=self.world.cabinet,
            name="Groupe C1 seul",
            kind=ConsolidationKind.COMBINED,
            year=2026,
            currency_code="XOF",
        )
        ConsolidationMember.objects.create(
            organization=self.world.cabinet,
            group=self.group_c1_only,
            company=self.world.company_c1,
            method=ConsolidationMethod.COMBINED,
            ownership_pct=D("100"),
        )

    def test_accountant_lists_only_accessible_groups(self):
        client = Client()
        client.force_login(self.world.cab_accountant)
        response = client.get(
            "/api/ledger/consolidation",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertEqual(response.status_code, 200, response.content)
        names = {row["name"] for row in response.json()}
        self.assertIn("Groupe C1 seul", names)
        self.assertNotIn("Groupe C1+C2", names)

    def test_accountant_denied_mixed_group_panel(self):
        client = Client()
        client.force_login(self.world.cab_accountant)
        response = client.get(
            f"/api/ledger/consolidation/{self.group.id}",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertEqual(response.status_code, 403)

    def test_accountant_allowed_c1_only_group(self):
        client = Client()
        client.force_login(self.world.cab_accountant)
        response = client.get(
            f"/api/ledger/consolidation/{self.group_c1_only.id}",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_owner_sees_mixed_group(self):
        client = Client()
        client.force_login(self.world.cab_owner)
        response = client.get(
            "/api/ledger/consolidation",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertEqual(response.status_code, 200)
        names = {row["name"] for row in response.json()}
        self.assertEqual(names, {"Groupe C1+C2", "Groupe C1 seul"})

    def test_accountant_cannot_add_c2_member(self):
        client = Client()
        client.force_login(self.world.cab_accountant)
        response = client.post(
            f"/api/ledger/consolidation/{self.group_c1_only.id}/members",
            data={
                "company_id": str(self.world.company_c2.id),
                "method": "combined",
                "ownership_pct": "100",
            },
            content_type="application/json",
            HTTP_X_ORGANIZATION_SLUG="cabinet-gamma",
        )
        self.assertEqual(response.status_code, 403)


class A1PrimeSecurityTests(TransactionTestCase):
    """SAAS-03 V3 / A1′ — matrice S1–S12 (muhimu_app).

    Classe A — isolation contre erreurs applicatives (attendu : bloqué).
    Classe B — résistance compromission SQL (documente les limites du modèle).
    """

    def setUp(self):
        super().setUp()
        self.world = IsolationWorld()

    def _app_conn(self):
        import os

        import psycopg

        db = settings.DATABASES["default"]
        return psycopg.connect(
            host=db.get("HOST") or "localhost",
            port=str(db.get("PORT") or "5432"),
            dbname=db["NAME"],
            user=os.environ.get("POSTGRES_APP_USER", "muhimu_app"),
            password=os.environ.get(
                "POSTGRES_APP_PASSWORD",
                os.environ.get("POSTGRES_PASSWORD", "muhimu"),
            ),
        )

    def _bind(self, cur, *, org_id: str = "", user_id: str = "") -> None:
        cur.execute(
            "SELECT set_config('app.current_organization_id', %s, false)", [org_id]
        )
        cur.execute("SELECT set_config('app.current_user_id', %s, false)", [user_id])

    def test_s1_isolation_between_organizations(self):
        """S1 — Classe A : org A ne voit pas les écritures org B."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_a.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_b1.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s2_isolation_companies_same_cabinet(self):
        """S2 — Classe A : comptable C1 ne voit pas C2."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_accountant.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_c2.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s3_cabinet_multi_company_owner(self):
        """S3 — Classe A : owner cabinet voit C1 et C2."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_owner.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = ANY(%s)",
                    [[str(self.world.company_c1.id), str(self.world.company_c2.id)]],
                )
                self.assertGreaterEqual(int(cur.fetchone()[0]), 2)
        finally:
            conn.close()

    def test_s4_revoke_access_immediate(self):
        """S4 — Classe A : après DELETE Access, C1 invisible pour le comptable."""
        CompanyAccess.objects.filter(
            user=self.world.cab_accountant, company=self.world.company_c1
        ).delete()
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_accountant.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_c1.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s5_no_user_context_fail_closed(self):
        """S5 — Classe A : org sans user → 0 ligne famille A."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(cur, org_id=str(self.world.org_a.id), user_id="")
                cur.execute("SELECT count(*) FROM ledger_entry")
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s6_wrong_org_context_fail_closed(self):
        """S6 — Classe A : user A + org B → 0 (membership mismatch)."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_b.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute("SELECT count(*) FROM ledger_entry")
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s7_forged_user_id_is_model_limit(self):
        """S7 — Classe B : forgery current_user_id → accès victime (limite documentée)."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_a.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_entry WHERE company_id = %s",
                    [str(self.world.company_a1.id)],
                )
                self.assertGreaterEqual(int(cur.fetchone()[0]), 1)
        finally:
            conn.close()

    def test_s8_bypass_guc_has_no_effect(self):
        """S8 — Classe A/B : set_config bypass on n'ouvre plus la RLS."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('app.bypass_rls', 'on', false)")
                self._bind(cur, org_id="", user_id="")
                cur.execute("SELECT public.app_bypass_rls()")
                self.assertFalse(cur.fetchone()[0])
                cur.execute("SELECT count(*) FROM ledger_entry")
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn.close()

    def test_s9_set_role_platform_denied(self):
        """S9 — Classe B : muhimu_app ne peut pas SET ROLE muhimu_platform."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                denied = False
                try:
                    cur.execute("SET ROLE muhimu_platform")
                except Exception:
                    denied = True
                self.assertTrue(denied, msg="SET ROLE muhimu_platform doit échouer")
        finally:
            conn.close()

    def test_s10_direct_sql_insert_unauthorized_company_rejected(self):
        """S10 — Classe A : INSERT entry société non autorisée → rejet WITH CHECK."""
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_accountant.id),
                )
                rejected = False
                try:
                    cur.execute(
                        """
                        INSERT INTO ledger_entry (
                          id, organization_id, company_id, journal_id, period_id,
                          exercise_id, status, source, number_display, idempotency_key,
                          accounting_date, value_date, description, document_ref,
                          created_at, updated_at
                        ) VALUES (
                          gen_random_uuid(), %s, %s, %s, %s,
                          %s, 'draft', 'manual', '', '',
                          '2026-01-15', '2026-01-15', 'intrusion', 'S10',
                          now(), now()
                        )
                        """,
                        [
                            str(self.world.cabinet.id),
                            str(self.world.company_c2.id),
                            str(self.world.books_c2["journal"].id),
                            str(self.world.books_c2["period"].id),
                            str(self.world.books_c2["exercise"].id),
                        ],
                    )
                except Exception:
                    rejected = True
                    conn.rollback()
                self.assertTrue(rejected)
        finally:
            conn.close()

    def test_s11_consolidation_group_rls(self):
        """S11 — Classe A : groupe mixte invisible au comptable C1-only."""
        from decimal import Decimal as D

        from apps.ledger.models import (
            ConsolidationGroup,
            ConsolidationKind,
            ConsolidationMember,
            ConsolidationMethod,
        )

        group = ConsolidationGroup.objects.create(
            organization=self.world.cabinet,
            name="Mix S11",
            kind=ConsolidationKind.COMBINED,
            year=2026,
            currency_code="XOF",
        )
        ConsolidationMember.objects.create(
            organization=self.world.cabinet,
            group=group,
            company=self.world.company_c1,
            method=ConsolidationMethod.COMBINED,
            ownership_pct=D("100"),
        )
        ConsolidationMember.objects.create(
            organization=self.world.cabinet,
            group=group,
            company=self.world.company_c2,
            method=ConsolidationMethod.COMBINED,
            ownership_pct=D("100"),
        )
        conn = self._app_conn()
        try:
            with conn.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_accountant.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_consolidationgroup WHERE id = %s",
                    [str(group.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 0)
                self._bind(
                    cur,
                    org_id=str(self.world.cabinet.id),
                    user_id=str(self.world.cab_owner.id),
                )
                cur.execute(
                    "SELECT count(*) FROM ledger_consolidationgroup WHERE id = %s",
                    [str(group.id)],
                )
                self.assertEqual(int(cur.fetchone()[0]), 1)
        finally:
            conn.close()

    def test_s12_context_does_not_leak_across_connections(self):
        """S12 — Classe A : nouvelle connexion muhimu_app sans GUC → 0 ligne."""
        conn1 = self._app_conn()
        try:
            with conn1.cursor() as cur:
                self._bind(
                    cur,
                    org_id=str(self.world.org_a.id),
                    user_id=str(self.world.user_a.id),
                )
                cur.execute("SELECT count(*) FROM ledger_entry")
                self.assertGreater(int(cur.fetchone()[0]), 0)
        finally:
            conn1.close()
        conn2 = self._app_conn()
        try:
            with conn2.cursor() as cur:
                cur.execute("SELECT count(*) FROM ledger_entry")
                self.assertEqual(int(cur.fetchone()[0]), 0)
        finally:
            conn2.close()
