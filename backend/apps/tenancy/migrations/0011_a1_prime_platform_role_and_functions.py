"""SAAS-03 V3 / A1′ — rôle muhimu_platform + fonctions d'autorisation durcies.

- Crée muhimu_platform (LOGIN, NOSUPERUSER, BYPASSRLS).
- Neutralise le bypass GUC (app_bypass_rls → toujours false).
- Ajoute app_user_can_access_company() SECURITY DEFINER.
- Durcit search_path / EXECUTE des helpers app_*.
"""

from __future__ import annotations

import os

from django.db import migrations

PLATFORM_ROLE = "muhimu_platform"
APP_ROLE = "muhimu_app"


def create_platform_role(apps, schema_editor):
    password = (
        os.getenv("POSTGRES_PLATFORM_PASSWORD")
        or os.getenv("POSTGRES_APP_PASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
        or "muhimu"
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [PLATFORM_ROLE])
        if cursor.fetchone():
            cursor.execute(
                f"ALTER ROLE {PLATFORM_ROLE} WITH LOGIN NOSUPERUSER NOCREATEDB "
                f"NOCREATEROLE NOINHERIT BYPASSRLS"
            )
            cursor.execute(f"ALTER ROLE {PLATFORM_ROLE} PASSWORD %s", [password])
        else:
            cursor.execute(
                f"CREATE ROLE {PLATFORM_ROLE} LOGIN PASSWORD %s "
                f"NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS",
                [password],
            )
        # Privilèges DML alignés sur muhimu_app — pas de GRANT du rôle aux connexions ERP.
        dbname = schema_editor.connection.settings_dict["NAME"]
        cursor.execute(f'GRANT CONNECT ON DATABASE "{dbname}" TO {PLATFORM_ROLE}')
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {PLATFORM_ROLE}")
        cursor.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {PLATFORM_ROLE}"
        )
        cursor.execute(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {PLATFORM_ROLE}"
        )
        cursor.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {PLATFORM_ROLE}"
        )
        cursor.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {PLATFORM_ROLE}"
        )
        # Isolation des rôles : muhimu_app ne doit pas pouvoir SET ROLE platform.
        cursor.execute(
            """
            SELECT 1 FROM pg_auth_members am
            JOIN pg_roles r ON r.oid = am.roleid
            JOIN pg_roles m ON m.oid = am.member
            WHERE r.rolname = %s AND m.rolname = %s
            """,
            [PLATFORM_ROLE, APP_ROLE],
        )
        if cursor.fetchone():
            cursor.execute(f"REVOKE {PLATFORM_ROLE} FROM {APP_ROLE}")
        cursor.execute(
            """
            SELECT 1 FROM pg_auth_members am
            JOIN pg_roles r ON r.oid = am.roleid
            JOIN pg_roles m ON m.oid = am.member
            WHERE r.rolname = %s AND m.rolname = %s
            """,
            [APP_ROLE, PLATFORM_ROLE],
        )
        if cursor.fetchone():
            cursor.execute(f"REVOKE {APP_ROLE} FROM {PLATFORM_ROLE}")


def drop_platform_role(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP ROLE IF EXISTS {PLATFORM_ROLE}")


SQL_FUNCTIONS = r"""
-- ---------------------------------------------------------------------------
-- Helpers d'identité (INVOKER) — GUC non cryptographique (menace modèle A1′).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.app_current_user() RETURNS uuid
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
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
$$;

CREATE OR REPLACE FUNCTION public.app_current_org() RETURNS uuid
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
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
$$;

-- A1′ : le GUC app.bypass_rls n'a plus aucun effet.
-- Contournement RLS = attribut BYPASSRLS du rôle de connexion uniquement.
CREATE OR REPLACE FUNCTION public.app_bypass_rls() RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
BEGIN
  RETURN false;
END;
$$;

-- Autorisation société dérivée de Membership / CompanyAccess (fail closed).
CREATE OR REPLACE FUNCTION public.app_user_can_access_company(p_company_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user uuid := public.app_current_user();
  v_org  uuid := public.app_current_org();
  v_company_org uuid;
  v_company_active boolean;
  v_role text;
  v_org_type text;
BEGIN
  IF p_company_id IS NULL OR v_user IS NULL OR v_org IS NULL THEN
    RETURN false;
  END IF;

  SELECT c.organization_id, c.is_active
    INTO v_company_org, v_company_active
  FROM public.tenancy_company c
  WHERE c.id = p_company_id;

  IF NOT FOUND OR v_company_active IS NOT TRUE THEN
    RETURN false;
  END IF;

  IF v_company_org <> v_org THEN
    RETURN false;
  END IF;

  SELECT m.role, o.type
    INTO v_role, v_org_type
  FROM public.tenancy_membership m
  JOIN public.tenancy_organization o ON o.id = m.organization_id
  WHERE m.organization_id = v_org
    AND m.user_id = v_user
    AND m.is_active IS TRUE;

  IF NOT FOUND THEN
    RETURN false;
  END IF;

  IF v_role IN ('owner', 'admin') THEN
    RETURN true;
  END IF;

  IF v_org_type = 'sme' THEN
    RETURN true;
  END IF;

  RETURN EXISTS (
    SELECT 1
    FROM public.tenancy_companyaccess a
    WHERE a.company_id = p_company_id
      AND a.user_id = v_user
      AND a.organization_id = v_org
  );
END;
$$;

-- Admin org pouvant créer / gérer des sociétés (INSERT company avant Access).
CREATE OR REPLACE FUNCTION public.app_user_is_org_admin(p_org_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user uuid := public.app_current_user();
BEGIN
  IF p_org_id IS NULL OR v_user IS NULL THEN
    RETURN false;
  END IF;
  RETURN EXISTS (
    SELECT 1
    FROM public.tenancy_membership m
    WHERE m.organization_id = p_org_id
      AND m.user_id = v_user
      AND m.is_active IS TRUE
      AND m.role IN ('owner', 'admin')
  );
END;
$$;

-- Consolidation : accès si admin/SME, ou toutes les sociétés membres accessibles.
CREATE OR REPLACE FUNCTION public.app_user_can_access_consolidation_group(p_group_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user uuid := public.app_current_user();
  v_org  uuid := public.app_current_org();
  v_group_org uuid;
  v_role text;
  v_org_type text;
  v_member_count int;
  v_allowed_count int;
BEGIN
  IF p_group_id IS NULL OR v_user IS NULL OR v_org IS NULL THEN
    RETURN false;
  END IF;

  SELECT g.organization_id INTO v_group_org
  FROM public.ledger_consolidationgroup g
  WHERE g.id = p_group_id;

  IF NOT FOUND OR v_group_org <> v_org THEN
    RETURN false;
  END IF;

  SELECT m.role, o.type
    INTO v_role, v_org_type
  FROM public.tenancy_membership m
  JOIN public.tenancy_organization o ON o.id = m.organization_id
  WHERE m.organization_id = v_org
    AND m.user_id = v_user
    AND m.is_active IS TRUE;

  IF NOT FOUND THEN
    RETURN false;
  END IF;

  IF v_role IN ('owner', 'admin') OR v_org_type = 'sme' THEN
    RETURN true;
  END IF;

  SELECT count(*) INTO v_member_count
  FROM public.ledger_consolidationmember cm
  WHERE cm.group_id = p_group_id;

  IF v_member_count = 0 THEN
    RETURN true;
  END IF;

  SELECT count(*) INTO v_allowed_count
  FROM public.ledger_consolidationmember cm
  WHERE cm.group_id = p_group_id
    AND public.app_user_can_access_company(cm.company_id);

  RETURN v_allowed_count = v_member_count;
END;
$$;

ALTER FUNCTION public.app_current_user() OWNER TO CURRENT_USER;
ALTER FUNCTION public.app_current_org() OWNER TO CURRENT_USER;
ALTER FUNCTION public.app_bypass_rls() OWNER TO CURRENT_USER;
ALTER FUNCTION public.app_user_can_access_company(uuid) OWNER TO CURRENT_USER;
ALTER FUNCTION public.app_user_is_org_admin(uuid) OWNER TO CURRENT_USER;
ALTER FUNCTION public.app_user_can_access_consolidation_group(uuid) OWNER TO CURRENT_USER;

REVOKE ALL ON FUNCTION public.app_current_user() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_current_org() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_bypass_rls() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_user_can_access_company(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_user_is_org_admin(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.app_user_can_access_consolidation_group(uuid) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.app_current_user() TO muhimu_app, muhimu_platform;
GRANT EXECUTE ON FUNCTION public.app_current_org() TO muhimu_app, muhimu_platform;
GRANT EXECUTE ON FUNCTION public.app_bypass_rls() TO muhimu_app, muhimu_platform;
GRANT EXECUTE ON FUNCTION public.app_user_can_access_company(uuid) TO muhimu_app, muhimu_platform;
GRANT EXECUTE ON FUNCTION public.app_user_is_org_admin(uuid) TO muhimu_app, muhimu_platform;
GRANT EXECUTE ON FUNCTION public.app_user_can_access_consolidation_group(uuid) TO muhimu_app, muhimu_platform;
"""

SQL_TENANCY_POLICIES = r"""
-- Famille B — company : accès dérivé (pas seulement organization_id).
DROP POLICY IF EXISTS tenancy_company_isolation ON public.tenancy_company;
CREATE POLICY tenancy_company_isolation ON public.tenancy_company
  FOR ALL
  USING (public.app_user_can_access_company(id))
  WITH CHECK (
    organization_id = public.app_current_org()
    AND (
      public.app_user_can_access_company(id)
      OR public.app_user_is_org_admin(organization_id)
    )
  );

-- Famille B — companyaccess : admin org ou sa propre ligne.
DROP POLICY IF EXISTS tenancy_companyaccess_isolation ON public.tenancy_companyaccess;
CREATE POLICY tenancy_companyaccess_isolation ON public.tenancy_companyaccess
  FOR ALL
  USING (
    organization_id = public.app_current_org()
    AND (
      user_id = public.app_current_user()
      OR public.app_user_is_org_admin(organization_id)
    )
  )
  WITH CHECK (
    organization_id = public.app_current_org()
    AND public.app_user_is_org_admin(organization_id)
  );

-- Officers : société accessible.
DROP POLICY IF EXISTS tenancy_companyofficer_isolation ON public.tenancy_companyofficer;
CREATE POLICY tenancy_companyofficer_isolation ON public.tenancy_companyofficer
  FOR ALL
  USING (public.app_user_can_access_company(company_id))
  WITH CHECK (public.app_user_can_access_company(company_id));

-- Org / membership : retirer la dépendance au bypass GUC (déjà false).
-- Réaffirmer les politiques V2 sans app_bypass_rls().
ALTER TABLE public.tenancy_membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenancy_membership FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_membership_isolation ON public.tenancy_membership;
CREATE POLICY tenancy_membership_isolation ON public.tenancy_membership
  FOR ALL
  USING (
    user_id = public.app_current_user()
    OR organization_id = public.app_current_org()
  )
  WITH CHECK (
    user_id = public.app_current_user()
    OR organization_id = public.app_current_org()
  );

ALTER TABLE public.tenancy_organization ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenancy_organization FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenancy_organization_isolation ON public.tenancy_organization;
CREATE POLICY tenancy_organization_isolation ON public.tenancy_organization
  FOR ALL
  USING (
    id = public.app_current_org()
    OR EXISTS (
      SELECT 1
      FROM public.tenancy_membership m
      WHERE m.organization_id = tenancy_organization.id
        AND m.user_id = public.app_current_user()
        AND m.is_active = true
    )
  )
  WITH CHECK (public.app_current_user() IS NOT NULL);

-- Audit : plus de bypass GUC.
DROP POLICY IF EXISTS audit_auditlog_isolation ON public.audit_auditlog;
CREATE POLICY audit_auditlog_isolation ON public.audit_auditlog
  FOR ALL
  USING (
    (organization_id IS NOT NULL AND organization_id = public.app_current_org())
    OR (
      organization_id IS NULL
      AND actor_id = public.app_current_user()
    )
  )
  WITH CHECK (
    organization_id IS NULL
    OR organization_id = public.app_current_org()
  );
"""

REVERSE_FUNCTIONS = r"""
DROP POLICY IF EXISTS audit_auditlog_isolation ON public.audit_auditlog;
CREATE POLICY audit_auditlog_isolation ON public.audit_auditlog
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

DROP POLICY IF EXISTS tenancy_organization_isolation ON public.tenancy_organization;
CREATE POLICY tenancy_organization_isolation ON public.tenancy_organization
  USING (
    app_bypass_rls()
    OR id = app_current_org()
    OR EXISTS (
      SELECT 1 FROM tenancy_membership m
      WHERE m.organization_id = tenancy_organization.id
        AND m.user_id = app_current_user()
        AND m.is_active = true
    )
  )
  WITH CHECK (app_bypass_rls() OR app_current_user() IS NOT NULL);

DROP POLICY IF EXISTS tenancy_membership_isolation ON public.tenancy_membership;
CREATE POLICY tenancy_membership_isolation ON public.tenancy_membership
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

DROP POLICY IF EXISTS tenancy_companyofficer_isolation ON public.tenancy_companyofficer;
CREATE POLICY tenancy_companyofficer_isolation ON public.tenancy_companyofficer
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

DROP POLICY IF EXISTS tenancy_companyaccess_isolation ON public.tenancy_companyaccess;
CREATE POLICY tenancy_companyaccess_isolation ON public.tenancy_companyaccess
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

DROP POLICY IF EXISTS tenancy_company_isolation ON public.tenancy_company;
CREATE POLICY tenancy_company_isolation ON public.tenancy_company
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

DROP FUNCTION IF EXISTS public.app_user_can_access_consolidation_group(uuid);
DROP FUNCTION IF EXISTS public.app_user_is_org_admin(uuid);
DROP FUNCTION IF EXISTS public.app_user_can_access_company(uuid);

CREATE OR REPLACE FUNCTION app_bypass_rls() RETURNS boolean AS $$
BEGIN
  RETURN COALESCE(NULLIF(current_setting('app.bypass_rls', true), ''), 'off') = 'on';
END;
$$ LANGUAGE plpgsql STABLE;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0010_rls_organization_membership"),
        ("ledger", "0031_rls_consolidation"),
        ("platform", "0002_rls"),
        ("audit", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(create_platform_role, drop_platform_role),
        migrations.RunSQL(SQL_FUNCTIONS, migrations.RunSQL.noop),
        migrations.RunSQL(SQL_TENANCY_POLICIES, REVERSE_FUNCTIONS),
    ]
