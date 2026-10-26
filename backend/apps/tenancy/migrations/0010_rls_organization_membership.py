"""SAAS-03 V2 — RLS sur tenancy_organization et tenancy_membership.

Réutilise app_current_user() (platform.0002) et app_bypass_rls() / app_current_org()
(tenancy.0002).

Politiques :
- membership : lignes de l'utilisateur courant, ou de l'organisation active.
- organization : org courante, ou org pour laquelle l'utilisateur a un membership actif.
- INSERT organization : utilisateur authentifié (création de dossier).
- INSERT membership : soi-même, ou dans l'org courante (admin / bootstrap via bypass).
"""

from django.db import migrations

SQL = r"""
-- Assurer app_current_user (créée par platform.0002 ; idempotente ici).
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

ALTER TABLE tenancy_membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_membership FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_membership_isolation ON tenancy_membership;
CREATE POLICY tenancy_membership_isolation ON tenancy_membership
  USING (
    app_bypass_rls()
    OR user_id = app_current_user()
    OR organization_id = app_current_org()
  )
  WITH CHECK (
    app_bypass_rls()
    OR user_id = app_current_user()
    OR organization_id = app_current_org()
  );

ALTER TABLE tenancy_organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenancy_organization FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_organization_isolation ON tenancy_organization;
CREATE POLICY tenancy_organization_isolation ON tenancy_organization
  USING (
    app_bypass_rls()
    OR id = app_current_org()
    OR EXISTS (
      SELECT 1
      FROM tenancy_membership m
      WHERE m.organization_id = tenancy_organization.id
        AND m.user_id = app_current_user()
        AND m.is_active = true
    )
  )
  WITH CHECK (
    app_bypass_rls()
    OR app_current_user() IS NOT NULL
  );
"""

REVERSE = r"""
DROP POLICY IF EXISTS tenancy_organization_isolation ON tenancy_organization;
ALTER TABLE tenancy_organization NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenancy_organization DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenancy_membership_isolation ON tenancy_membership;
ALTER TABLE tenancy_membership NO FORCE ROW LEVEL SECURITY;
ALTER TABLE tenancy_membership DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0009_organization_is_demo"),
        ("platform", "0002_rls"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE),
    ]
