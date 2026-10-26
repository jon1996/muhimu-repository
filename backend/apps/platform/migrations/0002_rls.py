from django.db import migrations


SQL = r"""
CREATE OR REPLACE FUNCTION app_current_user() RETURNS uuid AS $$
DECLARE
  raw text;
BEGIN
  raw := NULLIF(current_setting('app.current_user_id', true), '');
  IF raw IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN raw::uuid;
EXCEPTION WHEN others THEN
  RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

ALTER TABLE platform_demogrant ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_demogrant FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS platform_demogrant_isolation ON platform_demogrant;
CREATE POLICY platform_demogrant_isolation ON platform_demogrant
  USING (app_bypass_rls() OR user_id = app_current_user())
  WITH CHECK (app_bypass_rls() OR user_id = app_current_user());
"""

REVERSE = r"""
DROP POLICY IF EXISTS platform_demogrant_isolation ON platform_demogrant;
ALTER TABLE platform_demogrant NO FORCE ROW LEVEL SECURITY;
ALTER TABLE platform_demogrant DISABLE ROW LEVEL SECURITY;
DROP FUNCTION IF EXISTS app_current_user();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("platform", "0001_initial"),
        ("tenancy", "0002_rls"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE),
    ]
