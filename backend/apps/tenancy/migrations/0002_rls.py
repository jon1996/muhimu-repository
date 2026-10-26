from django.db import migrations


SQL = r"""
CREATE OR REPLACE FUNCTION app_bypass_rls() RETURNS boolean AS $$
BEGIN
  RETURN COALESCE(NULLIF(current_setting('app.bypass_rls', true), ''), 'off') = 'on';
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION app_current_org() RETURNS uuid AS $$
DECLARE
  raw text;
BEGIN
  raw := NULLIF(current_setting('app.current_organization_id', true), '');
  IF raw IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN raw::uuid;
EXCEPTION WHEN others THEN
  RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

ALTER TABLE tenancy_company ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_company FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_company_isolation ON tenancy_company;
CREATE POLICY tenancy_company_isolation ON tenancy_company
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

ALTER TABLE tenancy_companyaccess ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_companyaccess FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_companyaccess_isolation ON tenancy_companyaccess;
CREATE POLICY tenancy_companyaccess_isolation ON tenancy_companyaccess
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

ALTER TABLE audit_auditlog ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_auditlog FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_auditlog_isolation ON audit_auditlog;
CREATE POLICY audit_auditlog_isolation ON audit_auditlog
  USING (
    app_bypass_rls()
    OR (organization_id IS NOT NULL AND organization_id = app_current_org())
    OR (
      organization_id IS NULL
      AND actor_id::text = NULLIF(current_setting('app.current_user_id', true), '')
    )
  )
  WITH CHECK (
    app_bypass_rls()
    OR organization_id IS NULL
    OR organization_id = app_current_org()
  );
"""

REVERSE = r"""
DROP POLICY IF EXISTS audit_auditlog_isolation ON audit_auditlog;
ALTER TABLE audit_auditlog NO FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_auditlog DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenancy_companyaccess_isolation ON tenancy_companyaccess;
ALTER TABLE tenancy_companyaccess NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenancy_companyaccess DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenancy_company_isolation ON tenancy_company;
ALTER TABLE tenancy_company NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenancy_company DISABLE ROW LEVEL SECURITY;

DROP FUNCTION IF EXISTS app_current_org();
DROP FUNCTION IF EXISTS app_bypass_rls();
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0001_initial"),
        ("audit", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE),
    ]
