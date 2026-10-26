"""BETA-SCOPE-01 — feature flags et refus API."""

from __future__ import annotations

from datetime import date

from django.test import Client, TestCase, override_settings

from apps.identity.models import User
from apps.ledger.models import AccountingPeriod, Entry, Exercise, Journal, JournalType
from apps.ledger.services.posting import create_draft
from apps.ledger.tests.db import LedgerDbTestCase
from apps.tenancy.models import Membership, Role

RESTRICTED = {
    "consolidation": False,
    "class9_cage": False,
    "esg": False,
    "escompte": False,
}

OPEN = {
    "consolidation": True,
    "class9_cage": True,
    "esg": True,
    "escompte": True,
}


class BetaScopeSettingsTests(TestCase):
    @override_settings(DEBUG=True, BETA_SCOPE_RESTRICT=False, BETA_FEATURES=OPEN)
    def test_dev_like_defaults_allow_features(self):
        from apps.ledger.beta_scope import is_beta_feature_enabled

        self.assertTrue(is_beta_feature_enabled("consolidation"))
        self.assertTrue(is_beta_feature_enabled("escompte"))

    @override_settings(DEBUG=False, BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_beta_restrict_defaults_deny(self):
        from apps.ledger.beta_scope import is_beta_feature_enabled

        self.assertFalse(is_beta_feature_enabled("consolidation"))
        self.assertFalse(is_beta_feature_enabled("class9_cage"))


class BetaScopeApiTests(LedgerDbTestCase):
    def setUp(self):
        super().setUp()
        self.org.slug = "beta-scope-org"
        self.org.save(update_fields=["slug"])
        self.user = User.objects.create_user(
            email="acct@beta-scope.test",
            password="Acct1234!",
            full_name="Accountant",
        )
        Membership.objects.create(organization=self.org, user=self.user, role=Role.ACCOUNTANT)
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
        Journal.objects.create(
            organization=self.org,
            company=self.company,
            code="OD",
            name="OD",
            type=JournalType.OD,
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.headers = {
            "HTTP_X_ORGANIZATION_SLUG": self.org.slug,
            "HTTP_X_COMPANY_ID": str(self.company.id),
        }

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_beta_scope_endpoint_reports_flags(self):
        response = self.client.get("/api/ledger/beta-scope", **self.headers)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["restrict_mode"])
        self.assertFalse(body["consolidation"])
        self.assertFalse(body["class9_cage"])

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_consolidation_list_forbidden(self):
        response = self.client.get("/api/ledger/consolidation", **self.headers)
        self.assertEqual(response.status_code, 403)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_class9_forbidden(self):
        response = self.client.get("/api/ledger/class9", **self.headers)
        self.assertEqual(response.status_code, 403)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_cage_forbidden(self):
        response = self.client.get("/api/ledger/cage", **self.headers)
        self.assertEqual(response.status_code, 403)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_esg_forbidden(self):
        response = self.client.get("/api/ledger/esg", **self.headers)
        self.assertEqual(response.status_code, 403)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_escompte_preview_forbidden(self):
        response = self.client.post(
            "/api/ledger/escompte/preview",
            data='{"nominal":"1000","agios":"0","due_on":"2026-06-01","campaign":false}',
            content_type="application/json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_core_balance_still_allowed(self):
        response = self.client.get(
            f"/api/ledger/balance?period_id={self.period.id}",
            **self.headers,
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_statements_pdf_still_allowed(self):
        response = self.client.get("/api/ledger/statements/pdf?kind=bilan", **self.headers)
        self.assertIn(response.status_code, (200, 400))

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=OPEN)
    def test_consolidation_allowed_when_flag_on(self):
        response = self.client.get("/api/ledger/consolidation", **self.headers)
        self.assertEqual(response.status_code, 200)

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_post_escompte_entry_forbidden_not_silent(self):
        acc415 = self.make_account("4151", "Effets")
        acc521 = self.make_account("521", "Banque")
        journal = Journal.objects.get(company=self.company)
        draft = create_draft(
            company=self.company,
            journal=journal,
            accounting_date=date(2026, 1, 15),
            value_date=None,
            description="Escompte test",
            document_ref="",
            raw_lines=[
                {"account_id": str(acc415.id), "debit": "1000", "credit": "0"},
                {"account_id": str(acc521.id), "debit": "0", "credit": "1000"},
            ],
        )
        response = self.client.post(f"/api/ledger/entries/{draft.id}/post", **self.headers)
        self.assertEqual(response.status_code, 403)
        entry = Entry.objects.get(pk=draft.id)
        self.assertEqual(entry.status, "draft")

    @override_settings(BETA_SCOPE_RESTRICT=True, BETA_FEATURES=RESTRICTED)
    def test_other_org_cannot_bypass_with_spoofed_company(self):
        other_org = self.org.__class__.objects.create(
            name="Other", slug="other-beta-scope", type=self.org.type
        )
        other_co = self.company.__class__.objects.create(
            organization=other_org, name="Other Co", currency_code="XOF"
        )
        headers = {
            "HTTP_X_ORGANIZATION_SLUG": self.org.slug,
            "HTTP_X_COMPANY_ID": str(other_co.id),
        }
        response = self.client.get("/api/ledger/consolidation", **headers)
        self.assertIn(response.status_code, (400, 403))
