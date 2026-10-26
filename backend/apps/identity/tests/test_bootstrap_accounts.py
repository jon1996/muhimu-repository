from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.identity.models import User
from apps.tenancy.models import Organization


class BootstrapAccountsTests(TestCase):
    @override_settings(BOOTSTRAP_LOCAL_ACCOUNTS=True)
    def test_local_keeps_dot_local_accounts(self):
        call_command("bootstrap_demo", verbosity=0)
        demo = User.objects.get(email="demo@muhimu.local")
        ops = User.objects.get(email="ops@muhimu.local")
        self.assertTrue(demo.is_active)
        self.assertTrue(ops.is_staff)
        self.assertTrue(demo.check_password("Demo1234!"))
        self.assertTrue(Organization.objects.filter(slug="demo-pme", is_demo=True).exists())

    @override_settings(
        BOOTSTRAP_LOCAL_ACCOUNTS=False,
        STAFF_EMAIL="jp@muhimu.tech",
        STAFF_FULL_NAME="JP Muhimu",
        STAFF_PASSWORD="ProdStaff1234!",
    )
    def test_production_disables_local_and_creates_staff(self):
        User.objects.create_user(
            email="demo@muhimu.local",
            password="Demo1234!",
            full_name="Demo",
        )
        call_command("bootstrap_demo", verbosity=0)
        demo = User.objects.get(email="demo@muhimu.local")
        self.assertFalse(demo.is_active)
        self.assertFalse(demo.is_staff)
        staff = User.objects.get(email="jp@muhimu.tech")
        self.assertTrue(staff.is_active)
        self.assertTrue(staff.is_staff)
        self.assertTrue(staff.check_password("ProdStaff1234!"))
        self.assertFalse(User.objects.filter(email="tester@muhimu.local", is_active=True).exists())
        self.assertTrue(Organization.objects.filter(slug="demo-cabinet", is_demo=True).exists())
