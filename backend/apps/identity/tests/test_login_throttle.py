"""SEC-P0-01 — rate-limit login, sessions, isolation ERP/console."""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY
from django.test import Client, TestCase, override_settings
from apps.identity.login_throttle import reset_memory_store
from apps.identity.models import User


def _login(client: Client, email: str, password: str, *, remote_addr: str = "203.0.113.10", **extra):
    return client.post(
        "/api/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
        REMOTE_ADDR=remote_addr,
        **extra,
    )


@override_settings(
    AUTH_LOGIN_RATE_LIMIT_ENABLED=True,
    AUTH_LOGIN_THROTTLE_BACKEND="memory",
    AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=5,
    AUTH_LOGIN_MAX_ATTEMPTS_IP=40,
    AUTH_LOGIN_WINDOW_SECONDS=600,
    AUTH_LOGIN_LOCKOUT_SECONDS=900,
    AUTH_TRUST_PROXY=False,
    BOOTSTRAP_LOCAL_ACCOUNTS=True,
    ROOT_URLCONF="config.urls",
    SESSION_COOKIE_NAME="muhimu_session",
    CSRF_COOKIE_NAME="muhimu_csrf",
)
class ErpLoginThrottleTests(TestCase):
    def setUp(self):
        reset_memory_store()
        self.user = User.objects.create_user(
            email="pilot@example.com",
            password="PilotPass123!",
            full_name="Pilot",
        )
        self.client = Client()

    def test_valid_login(self):
        response = _login(self.client, "pilot@example.com", "PilotPass123!")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["user"]["email"], "pilot@example.com")
        self.assertIn(SESSION_KEY, self.client.session)

    def test_wrong_password_generic(self):
        response = _login(self.client, "pilot@example.com", "WrongPass999!")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Identifiants invalides.")

    def test_unknown_account_generic(self):
        response = _login(self.client, "nobody@example.com", "Whatever123!")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Identifiants invalides.")
        self.assertNotIn("nobody", response.content.decode().lower())

    def test_disabled_account_generic(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        response = _login(self.client, "pilot@example.com", "PilotPass123!")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Identifiants invalides.")

    def test_lockout_after_email_failures(self):
        for i in range(5):
            response = _login(self.client, "pilot@example.com", f"Bad{i}!")
            self.assertIn(response.status_code, (401, 429), response.content)
        locked = _login(self.client, "pilot@example.com", "PilotPass123!")
        self.assertEqual(locked.status_code, 429, locked.content)
        self.assertIn("Trop de tentatives", locked.json()["detail"])

    def test_success_resets_email_counter(self):
        for i in range(3):
            self.assertEqual(_login(self.client, "pilot@example.com", f"Bad{i}!").status_code, 401)
        ok = _login(self.client, "pilot@example.com", "PilotPass123!")
        self.assertEqual(ok.status_code, 200)
        # Après succès, 4 nouveaux échecs ne doivent pas encore locker (seuil 5).
        for i in range(4):
            self.assertEqual(_login(self.client, "pilot@example.com", f"Again{i}!").status_code, 401)
        still = _login(self.client, "pilot@example.com", "PilotPass123!")
        self.assertEqual(still.status_code, 200)

    def test_ip_limit_independent_of_email(self):
        with override_settings(AUTH_LOGIN_MAX_ATTEMPTS_IP=3, AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=50):
            reset_memory_store()
            for i in range(3):
                email = f"spray{i}@example.com"
                response = _login(self.client, email, "Nope1234!", remote_addr="198.51.100.7")
                self.assertIn(response.status_code, (401, 429))
            blocked = _login(
                self.client,
                "pilot@example.com",
                "PilotPass123!",
                remote_addr="198.51.100.7",
            )
            self.assertEqual(blocked.status_code, 429)

    def test_window_expiry_allows_retry(self):
        with override_settings(
            AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=2,
            AUTH_LOGIN_WINDOW_SECONDS=600,
            AUTH_LOGIN_LOCKOUT_SECONDS=1,
        ):
            reset_memory_store()
            self.assertEqual(_login(self.client, "pilot@example.com", "Bad1!").status_code, 401)
            self.assertEqual(_login(self.client, "pilot@example.com", "Bad2!").status_code, 429)
            # Expire artificialement le lock mémoire.
            from apps.identity import login_throttle as lt

            store = lt.get_store()
            keys = lt._keys("erp", "pilot@example.com", "203.0.113.10")
            store.delete(keys["lock_email"], keys["fail_email"])
            ok = _login(self.client, "pilot@example.com", "PilotPass123!")
            self.assertEqual(ok.status_code, 200)

    def test_redis_unavailable_fail_closed(self):
        with override_settings(AUTH_LOGIN_THROTTLE_BACKEND="redis"):
            with patch(
                "apps.identity.login_throttle._redis_client",
                side_effect=ConnectionError("redis down"),
            ):
                response = _login(self.client, "pilot@example.com", "PilotPass123!")
                self.assertEqual(response.status_code, 503)
                self.assertIn("indisponible", response.json()["detail"].lower())

    def test_forged_xff_ignored_without_trusted_proxy(self):
        with override_settings(AUTH_LOGIN_MAX_ATTEMPTS_IP=3, AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=50):
            reset_memory_store()
            # L'attaquant forge XFF ; sans AUTH_TRUST_PROXY on compte REMOTE_ADDR.
            for i in range(3):
                response = _login(
                    self.client,
                    f"a{i}@example.com",
                    "Nope1234!",
                    remote_addr="203.0.113.50",
                    HTTP_X_FORWARDED_FOR="8.8.8.8",
                    HTTP_X_REAL_IP="8.8.8.8",
                )
                self.assertIn(response.status_code, (401, 429))
            blocked = _login(
                self.client,
                "pilot@example.com",
                "PilotPass123!",
                remote_addr="203.0.113.50",
                HTTP_X_FORWARDED_FOR="1.2.3.4",
            )
            self.assertEqual(blocked.status_code, 429)
            # Une autre IP réelle n'est pas bloquée.
            other = _login(
                self.client,
                "pilot@example.com",
                "PilotPass123!",
                remote_addr="203.0.113.51",
                HTTP_X_FORWARDED_FOR="203.0.113.50",
            )
            self.assertEqual(other.status_code, 200)

    def test_trusted_proxy_uses_x_real_ip(self):
        with override_settings(
            AUTH_TRUST_PROXY=True,
            AUTH_TRUSTED_PROXIES="10.0.0.1",
            AUTH_LOGIN_MAX_ATTEMPTS_IP=2,
            AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=50,
        ):
            reset_memory_store()
            for i in range(2):
                _login(
                    self.client,
                    f"b{i}@example.com",
                    "Nope1234!",
                    remote_addr="10.0.0.1",
                    HTTP_X_REAL_IP="198.51.100.9",
                )
            blocked = _login(
                self.client,
                "pilot@example.com",
                "PilotPass123!",
                remote_addr="10.0.0.1",
                HTTP_X_REAL_IP="198.51.100.9",
            )
            self.assertEqual(blocked.status_code, 429)

    def test_logout_invalidates_session(self):
        self.assertEqual(_login(self.client, "pilot@example.com", "PilotPass123!").status_code, 200)
        self.assertTrue(self.client.session.get(SESSION_KEY))
        out = self.client.post("/api/auth/logout", data="{}", content_type="application/json")
        self.assertEqual(out.status_code, 200)
        self.assertFalse(self.client.session.get(SESSION_KEY))
        me = self.client.get("/api/auth/me")
        self.assertIn(me.status_code, (401, 403))

    def test_password_change_keeps_session(self):
        self.assertEqual(_login(self.client, "pilot@example.com", "PilotPass123!").status_code, 200)
        response = self.client.post(
            "/api/auth/password/change",
            data=json.dumps(
                {"current_password": "PilotPass123!", "new_password": "NewPilotPass456!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPilotPass456!"))

    def test_no_password_in_audit_metadata(self):
        from apps.audit.models import AuditLog

        _login(self.client, "pilot@example.com", "BadSecret999!")
        _login(self.client, "pilot@example.com", "PilotPass123!")
        for row in AuditLog.objects.all():
            blob = json.dumps(row.metadata or {}) + (row.action or "")
            self.assertNotIn("PilotPass", blob)
            self.assertNotIn("BadSecret", blob)
            self.assertNotIn("password", blob.lower())


@override_settings(
    AUTH_LOGIN_RATE_LIMIT_ENABLED=True,
    AUTH_LOGIN_THROTTLE_BACKEND="memory",
    AUTH_LOGIN_MAX_ATTEMPTS_EMAIL=5,
    AUTH_TRUST_PROXY=False,
    BOOTSTRAP_LOCAL_ACCOUNTS=True,
    ROOT_URLCONF="config.platform_urls",
    APP_ROLE="platform",
    SESSION_COOKIE_NAME="muhimu_platform_session",
    CSRF_COOKIE_NAME="muhimu_platform_csrf",
)
class PlatformLoginSecurityTests(TestCase):
    def setUp(self):
        reset_memory_store()
        self.staff = User.objects.create_user(
            email="ops@example.com",
            password="OpsPass123!",
            full_name="Ops",
            is_staff=True,
        )
        self.erp_only = User.objects.create_user(
            email="client@example.com",
            password="ClientPass123!",
            full_name="Client",
            is_staff=False,
        )
        self.client = Client()

    def test_staff_login_ok(self):
        response = _login(self.client, "ops@example.com", "OpsPass123!")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["user"]["is_staff"])

    def test_non_staff_denied(self):
        response = _login(self.client, "client@example.com", "ClientPass123!")
        self.assertEqual(response.status_code, 403)

    def test_admin_endpoint_requires_staff(self):
        # Session ERP-like user force_login n'a pas is_staff.
        self.client.force_login(self.erp_only)
        response = self.client.get("/api/tenants")
        self.assertEqual(response.status_code, 403)

    def test_platform_lockout(self):
        for i in range(5):
            _login(self.client, "ops@example.com", f"Bad{i}!")
        locked = _login(self.client, "ops@example.com", "OpsPass123!")
        self.assertEqual(locked.status_code, 429)

    def test_erp_session_cookie_name_isolated(self):
        # Cookie platform distinct — une session ERP ne remplit pas la console.
        erp = Client()
        with override_settings(
            ROOT_URLCONF="config.urls",
            APP_ROLE="erp",
            SESSION_COOKIE_NAME="muhimu_session",
            CSRF_COOKIE_NAME="muhimu_csrf",
        ):
            # force_login sur client ERP
            pass
        self.client.force_login(self.erp_only)
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 403)
