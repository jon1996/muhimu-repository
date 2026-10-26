"""SEC-SESSION-01 — expiration inactivité, plafond absolu, cookies, CSRF."""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import SESSION_KEY
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.identity.login_throttle import reset_memory_store
from apps.identity.models import User
from apps.identity.session_policy import SESSION_AUTH_AT_KEY, SESSION_LAST_ACTIVITY_KEY
from apps.tenancy.models import Company, Membership, Organization


def _login(client: Client, email: str, password: str) -> int:
    response = client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
        REMOTE_ADDR="203.0.113.10",
    )
    return response.status_code


SHORT_POLICY = dict(
    AUTH_LOGIN_RATE_LIMIT_ENABLED=False,
    BOOTSTRAP_LOCAL_ACCOUNTS=True,
    ROOT_URLCONF="config.urls",
    SESSION_COOKIE_NAME="muhimu_session",
    CSRF_COOKIE_NAME="muhimu_csrf",
    SESSION_POLICY_ENABLED=True,
    SESSION_IDLE_TIMEOUT_SECONDS=30 * 60,
    SESSION_ABSOLUTE_TIMEOUT_SECONDS=12 * 60 * 60,
    SESSION_IDLE_WARN_BEFORE_SECONDS=300,
    SESSION_EXPIRE_AT_BROWSER_CLOSE=True,
)


@override_settings(**SHORT_POLICY)
class SessionPolicyTests(TestCase):
    def setUp(self):
        reset_memory_store()
        self.user = User.objects.create_user(
            email="acct@example.com",
            password="AcctPass123!",
            full_name="Comptable",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="OtherPass123!",
            full_name="Autre",
        )
        self.org = Organization.objects.create(name="Org A", slug="org-a", type="sme")
        Membership.objects.create(user=self.user, organization=self.org, role="owner")
        Membership.objects.create(user=self.other, organization=self.org, role="viewer")
        Company.objects.create(organization=self.org, name="Co", currency_code="XAF")
        self.client = Client()

    def test_login_stamps_session_timestamps(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        self.assertIn(SESSION_AUTH_AT_KEY, self.client.session)
        self.assertIn(SESSION_LAST_ACTIVITY_KEY, self.client.session)

    @override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60, SESSION_ABSOLUTE_TIMEOUT_SECONDS=3600)
    def test_idle_expiry_after_inactivity(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        frozen = timezone.now()
        with self.settings(SESSION_IDLE_TIMEOUT_SECONDS=60):
            with patch_time(frozen + timedelta(seconds=61)):
                me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.headers.get("X-Muhimu-Session-Expired"), "idle")

    @override_settings(SESSION_IDLE_TIMEOUT_SECONDS=3600, SESSION_ABSOLUTE_TIMEOUT_SECONDS=120)
    def test_absolute_expiry_despite_activity(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        frozen = timezone.now()
        # Activité légitime avant le plafond absolu.
        with patch_time(frozen + timedelta(seconds=30)):
            touch = self.client.get("/api/companies", HTTP_X_ORGANIZATION_SLUG="org-a")
            self.assertEqual(touch.status_code, 200)
        with patch_time(frozen + timedelta(seconds=121)):
            me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.headers.get("X-Muhimu-Session-Expired"), "absolute")

    @override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60)
    def test_legitimate_activity_refreshes_idle(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        frozen = timezone.now()
        with patch_time(frozen + timedelta(seconds=50)):
            ok = self.client.get("/api/companies", HTTP_X_ORGANIZATION_SLUG="org-a")
            self.assertEqual(ok.status_code, 200)
        with patch_time(frozen + timedelta(seconds=70)):
            me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)

    def test_auth_me_does_not_refresh_idle(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        last_at = self.client.session[SESSION_LAST_ACTIVITY_KEY]
        self.client.get("/api/auth/me")
        self.client.get("/api/auth/me")
        self.assertEqual(self.client.session[SESSION_LAST_ACTIVITY_KEY], last_at)

    def test_background_header_does_not_refresh_idle(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        last_at = self.client.session[SESSION_LAST_ACTIVITY_KEY]
        self.client.get(
            "/api/companies",
            HTTP_X_ORGANIZATION_SLUG="org-a",
            HTTP_X_MUHIMU_SESSION_ACTIVITY="background",
        )
        self.assertEqual(self.client.session[SESSION_LAST_ACTIVITY_KEY], last_at)

    @override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60)
    def test_logout_invalidates_immediately(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        self.assertEqual(
            self.client.post("/api/auth/logout", data="{}", content_type="application/json").status_code,
            200,
        )
        self.assertFalse(self.client.session.get(SESSION_KEY))
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    @override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60)
    def test_second_tab_sees_expired_session(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        session_key = self.client.session.session_key
        frozen = timezone.now()
        with patch_time(frozen + timedelta(seconds=61)):
            expired = self.client.get("/api/companies", HTTP_X_ORGANIZATION_SLUG="org-a")
        self.assertEqual(expired.status_code, 401)
        tab2 = Client()
        tab2.cookies["muhimu_session"] = session_key
        me = tab2.get("/api/auth/me")
        self.assertEqual(me.status_code, 401)

    def test_unauthenticated_csrf_does_not_create_session_activity(self):
        csrf = self.client.get("/api/csrf")
        self.assertEqual(csrf.status_code, 200)

    def test_session_status_endpoint_no_touch(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        last_at = self.client.session[SESSION_LAST_ACTIVITY_KEY]
        status = self.client.get("/api/auth/session")
        self.assertEqual(status.status_code, 200)
        body = status.json()
        self.assertTrue(body["authenticated"])
        self.assertIsNotNone(body["idle_expires_at"])
        self.assertEqual(self.client.session[SESSION_LAST_ACTIVITY_KEY], last_at)

    def test_user_isolation(self):
        c1 = Client()
        c2 = Client()
        self.assertEqual(_login(c1, "acct@example.com", "AcctPass123!"), 200)
        self.assertEqual(_login(c2, "other@example.com", "OtherPass123!"), 200)
        self.assertNotEqual(c1.session.session_key, c2.session.session_key)
        self.assertEqual(c1.get("/api/auth/me").json()["user"]["email"], "acct@example.com")
        self.assertEqual(c2.get("/api/auth/me").json()["user"]["email"], "other@example.com")

    def test_password_change_still_authenticated(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        change = self.client.post(
            "/api/auth/password/change",
            data=json.dumps(
                {"current_password": "AcctPass123!", "new_password": "NewAcctPass456!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(change.status_code, 200, change.content)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    @override_settings(SESSION_POLICY_ENABLED=False)
    def test_policy_disabled_skips_idle_check(self):
        self.assertEqual(_login(self.client, "acct@example.com", "AcctPass123!"), 200)
        old = timezone.now().timestamp() - 86400 * 2
        self.client.session[SESSION_AUTH_AT_KEY] = old
        self.client.session[SESSION_LAST_ACTIVITY_KEY] = old
        self.client.session.save()
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)


class patch_time:
    """Contexte : avance timezone.now() pour les contrôles d'expiration."""

    def __init__(self, moment):
        self.moment = moment
        self._patch = None

    def __enter__(self):
        from unittest.mock import patch

        self._patch = patch("apps.identity.session_policy.timezone.now", return_value=self.moment)
        self._patch.start()
        return self

    def __exit__(self, *args):
        if self._patch:
            self._patch.stop()
