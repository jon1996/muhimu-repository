from django.core import mail
from django.test import Client, TestCase, override_settings

from apps.identity.models import User


@override_settings(
    ROOT_URLCONF="config.platform_urls",
    APP_ROLE="platform",
    SESSION_COOKIE_NAME="muhimu_platform_session",
    CSRF_COOKIE_NAME="muhimu_platform_csrf",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="mail.privateemail.com",
    EMAIL_PORT=465,
    EMAIL_HOST_USER="noreply@muhimu.test",
    EMAIL_HOST_PASSWORD="secret",
    DEFAULT_FROM_EMAIL="Muhimu <noreply@muhimu.test>",
    EMAIL_USE_SSL=True,
    EMAIL_USE_TLS=False,
)
class PlatformMailApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            email="ops@test.local",
            password="Ops1234!",
            full_name="Ops",
            is_staff=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_mail_status_hides_password(self):
        response = self.client.get("/api/mail/status")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["provider"], "Namecheap Private Email")
        self.assertEqual(payload["host"], "mail.privateemail.com")
        self.assertEqual(payload["port"], 465)
        self.assertEqual(payload["username"], "noreply@muhimu.test")
        self.assertTrue(payload["password_set"])
        self.assertNotIn("secret", response.content.decode())
        self.assertNotIn("password", payload)

    def test_send_test_email(self):
        response = self.client.post(
            "/api/mail/test",
            data={"to": "verif@example.com"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["to"], "verif@example.com")
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["verif@example.com"])
        self.assertIn("test d'envoi", message.subject)
        self.assertTrue(message.alternatives)
        self.assertEqual(message.alternatives[0][1], "text/html")
        self.assertIn("Muhimu", message.alternatives[0][0])

    def test_invalid_recipient(self):
        response = self.client.post(
            "/api/mail/test",
            data={"to": "pas-un-email"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_non_staff_cannot_send(self):
        guest = User.objects.create_user(email="guest@test.local", password="Guest1234!")
        client = Client()
        client.force_login(guest)
        response = client.get("/api/mail/status")
        self.assertEqual(response.status_code, 403)
