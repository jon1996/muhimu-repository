from django.test import Client, TestCase

from apps.identity.api import _me_payload
from apps.identity.models import User
from apps.tenancy.models import Company, Membership, Organization, OrganizationType, Role


class OwnOrganizationTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            email="tester@example.com",
            password="Temp1234!",
            full_name="Testeur",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_create_own_pme_empty_books(self):
        response = self.client.post(
            "/api/organizations/own",
            data={
                "type": "sme",
                "name": "Ma SARL",
                "company_name": "SARL Soleil",
                "legal_name": "SARL Soleil",
                "country_code": "CI",
                "currency_code": "XOF",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["name"], "Ma SARL")
        self.assertEqual(payload["type"], "sme")
        self.assertFalse(payload["is_demo"])
        self.assertEqual(payload["setup_data"], "empty")
        org = Organization.objects.get(id=payload["id"])
        self.assertTrue(
            Membership.objects.filter(user=self.user, organization=org, role=Role.OWNER).exists()
        )
        company = Company.objects.get(organization=org)
        self.assertEqual(company.name, "SARL Soleil")
        self.assertEqual(company.country_code, "CI")
        self.assertEqual(company.currency_code, "XOF")
        slugs = {m.organization.slug for m in _me_payload(self.user).memberships}
        self.assertIn(org.slug, slugs)

    def test_currency_follows_ohada_country(self):
        cases = (("GN", "GNF"), ("CD", "CDF"), ("KM", "KMF"), ("CF", "XAF"), ("GQ", "XAF"))
        for country, currency in cases:
            with self.subTest(country=country):
                response = self.client.post(
                    "/api/organizations/own",
                    data={
                        "type": "sme",
                        "name": f"Org {country}",
                        "company_name": f"Ste {country}",
                        "country_code": country,
                        "currency_code": "XOF",
                    },
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200, response.content)
                org = Organization.objects.get(id=response.json()["id"])
                company = Company.objects.get(organization=org)
                self.assertEqual(company.country_code, country)
                self.assertEqual(company.currency_code, currency)

    def test_rejects_non_ohada_country(self):
        response = self.client.post(
            "/api/organizations/own",
            data={
                "type": "sme",
                "name": "France SAS",
                "company_name": "France SAS",
                "country_code": "FR",
                "currency_code": "EUR",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_own_company_identity_starts_incomplete(self):
        created = self.client.post(
            "/api/organizations/own",
            data={
                "type": "sme",
                "name": "Ma SARL",
                "company_name": "SARL Soleil",
                "legal_name": "SARL Soleil",
                "country_code": "CI",
            },
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200, created.content)
        org = Organization.objects.get(id=created.json()["id"])
        headers = {"HTTP_X_ORGANIZATION_SLUG": org.slug}
        listing = self.client.get("/api/companies", **headers)
        self.assertEqual(listing.status_code, 200, listing.content)
        company = listing.json()[0]
        self.assertFalse(company["identity_complete"])
        self.assertIn("rccm", company["identity_missing"])
        self.assertIn("officers", company["identity_missing"])

        company_id = company["id"]
        headers["HTTP_X_COMPANY_ID"] = company_id
        saved = self.client.patch(
            f"/api/companies/{company_id}/settings",
            data={
                "legal_name": "SARL Soleil",
                "country_code": "CI",
                "address": "12 rue du Commerce",
                "city": "Abidjan",
                "rccm": "CI-ABJ-2026-B-1",
                "tax_id": "CI0001",
                "legal_form": "sarl",
                "tax_regime": "reel_normal",
            },
            content_type="application/json",
            **headers,
        )
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertFalse(saved.json()["identity_complete"])
        officer = self.client.post(
            f"/api/companies/{company_id}/officers",
            data={"full_name": "Awa Koné", "role": "manager"},
            content_type="application/json",
            **headers,
        )
        self.assertEqual(officer.status_code, 200, officer.content)
        listing = self.client.get("/api/companies", **headers)
        self.assertTrue(listing.json()[0]["identity_complete"])
        self.assertEqual(listing.json()[0]["identity_missing"], [])
