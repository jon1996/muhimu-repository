"""SAAS-03 V3 / A1′ — DemoGrant sans bypass GUC (platform rôle BYPASSRLS)."""

from django.db import migrations

SQL = r"""
DROP POLICY IF EXISTS platform_demogrant_isolation ON public.platform_demogrant;
CREATE POLICY platform_demogrant_isolation ON public.platform_demogrant
  FOR ALL
  USING (user_id = public.app_current_user())
  WITH CHECK (user_id = public.app_current_user());
"""

REVERSE = r"""
DROP POLICY IF EXISTS platform_demogrant_isolation ON public.platform_demogrant;
CREATE POLICY platform_demogrant_isolation ON public.platform_demogrant
  USING (app_bypass_rls() OR user_id = app_current_user())
  WITH CHECK (app_bypass_rls() OR user_id = app_current_user());
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0002_rls"),
        ("tenancy", "0011_a1_prime_platform_role_and_functions"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE),
    ]
