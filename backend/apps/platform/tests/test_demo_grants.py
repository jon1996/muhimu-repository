from django.test import Client, TestCase, override_settings
from django.core import mail

from apps.identity.api import _me_payload
from apps.identity.models import User
from apps.platform.models import DemoGrant
from apps.platform.services.grants import upsert_demo_grant
from apps.tenancy.models import Company, CompanyOfficer, Membership, Organization, OrganizationType, Role


class DemoGrantAccessTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="invitee@example.com",
            password="Temp1234!",
            full_name="Invité",
        )
        self.sme = Organization.objects.create(
            name="Demo PME",
            slug="demo-pme",
            type=OrganizationType.SME,
            is_demo=True,
        )
        self.cabinet = Organization.objects.create(
            name="Demo Cabinet",
            slug="demo-cabinet",
            type=OrganizationType.CABINET,
            is_demo=True,
        )
        self.real = Organization.objects.create(
            name="Client réel",
            slug="client-reel",
            type=OrganizationType.SME,
            is_demo=False,
        )
        Membership.objects.create(organization=self.sme, user=self.user, role=Role.ACCOUNTANT)
        Membership.objects.create(organization=self.cabinet, user=self.user, role=Role.ACCOUNTANT)
        Membership.objects.create(organization=self.real, user=self.user, role=Role.OWNER)

    def _slugs(self):
        return {m.organization.slug for m in _me_payload(self.user).memberships}

    def test_without_grant_hides_demo_orgs(self):
        self.assertEqual(self._slugs(), {"client-reel"})

    def test_pme_grant_only(self):
        DemoGrant.objects.create(user=self.user, access_pme=True, access_cabinet=False, is_active=True)
        self.assertEqual(self._slugs(), {"client-reel", "demo-pme"})

    def test_inactive_grant_hides_demo(self):
        DemoGrant.objects.create(user=self.user, access_pme=True, access_cabinet=True, is_active=False)
        self.assertEqual(self._slugs(), {"client-reel"})


@override_settings(
    ROOT_URLCONF="config.platform_urls",
    APP_ROLE="platform",
    SESSION_COOKIE_NAME="muhimu_platform_session",
    CSRF_COOKIE_NAME="muhimu_platform_csrf",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ERP_PUBLIC_URL="http://127.0.0.1:3001",
)
class PlatformDemoApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            email="ops@test.local",
            password="Ops1234!",
            full_name="Ops",
            is_staff=True,
        )
        self.sme = Organization.objects.create(
            name="Demo PME",
            slug="demo-pme",
            type=OrganizationType.SME,
            is_demo=True,
        )
        self.cabinet = Organization.objects.create(
            name="Demo Cabinet",
            slug="demo-cabinet",
            type=OrganizationType.CABINET,
            is_demo=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_invite_creates_user_grant_membership_and_email(self):
        response = self.client.post(
            "/api/demo/grants",
            data={
                "email": "prospect@example.com",
                "full_name": "Prospect",
                "access_pme": True,
                "access_cabinet": False,
                "send_email": True,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        payload = response.json()
        self.assertEqual(payload["email"], "prospect@example.com")
        self.assertTrue(payload["access_pme"])
        self.assertFalse(payload["access_cabinet"])
        self.assertTrue(payload["temporary_password"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(payload["email_sent"])
        self.assertEqual(payload["email_error"], "")
        self.assertIn(payload["temporary_password"], mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)
        self.assertEqual(mail.outbox[0].alternatives[0][1], "text/html")
        self.assertIn(payload["temporary_password"], mail.outbox[0].alternatives[0][0])
        guest = User.objects.get(email="prospect@example.com")
        self.assertTrue(guest.check_password(payload["temporary_password"]))
        self.assertTrue(
            Membership.objects.filter(
                user=guest, organization=self.sme, is_active=True
            ).exists()
        )
        self.assertFalse(
            Membership.objects.filter(
                user=guest, organization=self.cabinet, is_active=True
            ).exists()
        )

    def test_non_staff_cannot_login(self):
        User.objects.create_user(email="demo@test.local", password="Demo1234!")
        anon = Client()
        response = anon.post(
            "/api/auth/login",
            data={"email": "demo@test.local", "password": "Demo1234!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_revoke_drops_demo_memberships(self):
        grant, _ = upsert_demo_grant(
            email="gone@example.com",
            full_name="Gone",
            access_pme=True,
            access_cabinet=True,
            granted_by=self.staff,
            send_email=False,
            reset_password=True,
        )
        guest = grant.user
        self.assertTrue(Membership.objects.filter(user=guest, is_active=True).exists())
        response = self.client.post(f"/api/demo/grants/{grant.id}/revoke")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["is_active"])
        self.assertFalse(Membership.objects.filter(user=guest, is_active=True).exists())

    def test_staff_cannot_receive_demo_grant(self):
        with self.assertRaises(ValueError):
            upsert_demo_grant(
                email=self.staff.email,
                access_pme=True,
                granted_by=self.staff,
                send_email=False,
            )

    @override_settings(BOOTSTRAP_LOCAL_ACCOUNTS=False)
    def test_invite_rejects_muhimu_local_in_production(self):
        response = self.client.post(
            "/api/demo/grants",
            data={
                "email": "demo@muhimu.local",
                "access_pme": True,
                "send_email": False,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400, response.content)


@override_settings(
    ROOT_URLCONF="config.platform_urls",
    APP_ROLE="platform",
    SESSION_COOKIE_NAME="muhimu_platform_session",
    CSRF_COOKIE_NAME="muhimu_platform_csrf",
)
class PlatformDashboardApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            email="ops@test.local",
            password="Ops1234!",
            full_name="Ops",
            is_staff=True,
        )
        User.objects.create_user(
            email="client@test.local",
            password="Client1234!",
            full_name="Client Test",
        )
        Organization.objects.create(
            name="SARL Soleil",
            slug="sarl-soleil",
            type=OrganizationType.SME,
            is_demo=False,
        )
        Organization.objects.create(
            name="Cabinet Demo",
            slug="demo-cabinet",
            type=OrganizationType.CABINET,
            is_demo=True,
        )
        self.client = Client()
        self.client.force_login(self.staff)

    def test_dashboard_kpis(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["kpis"]["org_count"], 2)
        self.assertEqual(payload["kpis"]["client_count"], 1)
        self.assertEqual(payload["kpis"]["demo_count"], 1)
        self.assertEqual(payload["kpis"]["user_count"], 1)
        labels = {item["label"] for item in payload["by_type"]}
        self.assertEqual(labels, {"PME", "Cabinets"})
        self.assertEqual(len(payload["orgs_by_week"]), 8)


@override_settings(
    ROOT_URLCONF="config.platform_urls",
    APP_ROLE="platform",
    SESSION_COOKIE_NAME="muhimu_platform_session",
    CSRF_COOKIE_NAME="muhimu_platform_csrf",
)
class PlatformDirectoryApiTests(TestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user(
            email="ops@test.local",
            password="Ops1234!",
            full_name="Ops",
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            email="client@test.local",
            password="Client1234!",
            full_name="Client Test",
        )
        self.sme = Organization.objects.create(
            name="SARL Soleil",
            slug="sarl-soleil",
            type=OrganizationType.SME,
            is_demo=False,
        )
        self.cabinet = Organization.objects.create(
            name="Cabinet Demo",
            slug="demo-cabinet",
            type=OrganizationType.CABINET,
            is_demo=True,
        )
        company = Company.objects.create(
            organization=self.sme,
            name="SARL Soleil",
            legal_name="SARL Soleil",
            country_code="CI",
            currency_code="XOF",
            rccm="CI-ABJ-2026-B-1",
            tax_id="CI0001",
            legal_form="sarl",
            tax_regime="reel_normal",
            city="Abidjan",
            address="12 rue du Commerce",
        )
        CompanyOfficer.objects.create(
            organization=self.sme,
            company=company,
            full_name="Awa Koné",
            role="manager",
        )
        Membership.objects.create(organization=self.sme, user=self.owner, role=Role.OWNER)
        self.client = Client()
        self.client.force_login(self.staff)

    def test_staff_sees_all_organizations_and_companies(self):
        response = self.client.get("/api/tenants")
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["org_count"], 2)
        self.assertEqual(payload["pme_count"], 1)
        self.assertEqual(payload["cabinet_count"], 1)
        self.assertEqual(payload["client_count"], 1)
        names = {item["name"] for item in payload["organizations"]}
        self.assertEqual(names, {"SARL Soleil", "Cabinet Demo"})
        soleil = next(item for item in payload["organizations"] if item["slug"] == "sarl-soleil")
        self.assertFalse(soleil["is_demo"])
        self.assertTrue(soleil["identity_complete"])
        self.assertEqual(soleil["companies"][0]["rccm"], "CI-ABJ-2026-B-1")
        self.assertEqual(soleil["members"][0]["email"], "client@test.local")

    def test_staff_sees_users_with_orgs(self):
        response = self.client.get("/api/users")
        self.assertEqual(response.status_code, 200, response.content)
        emails = {item["email"] for item in response.json()}
        self.assertIn("client@test.local", emails)
        self.assertIn("ops@test.local", emails)
        client = next(item for item in response.json() if item["email"] == "client@test.local")
        self.assertEqual(client["organizations"][0]["slug"], "sarl-soleil")
        self.assertFalse(client["is_staff"])

    def test_non_staff_cannot_list_tenants(self):
        guest = Client()
        guest.force_login(self.owner)
        response = guest.get("/api/tenants")
        self.assertEqual(response.status_code, 403)
