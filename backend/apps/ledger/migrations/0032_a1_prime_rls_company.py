"""SAAS-03 V3 / A1′ — politiques RLS famille A (société) + famille C (consolidation)."""

from django.db import migrations

FAMILY_A = [
    "ledger_account",
    "ledger_accountingperiod",
    "ledger_balancesnapshot",
    "ledger_bankstatement",
    "ledger_bankstatementline",
    "ledger_cagereflection",
    "ledger_cagesection",
    "ledger_cashcount",
    "ledger_commitment",
    "ledger_depreciationcharge",
    "ledger_entry",
    "ledger_entryline",
    "ledger_esgreport",
    "ledger_exercise",
    "ledger_fixedasset",
    "ledger_fxrate",
    "ledger_inventorycampaign",
    "ledger_inventoryline",
    "ledger_journal",
    "ledger_journalsequence",
    "ledger_sourcedocument",
    "ledger_thirdparty",
]


def _policy_company(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_isolation ON public.{table};
CREATE POLICY {table}_isolation ON public.{table}
  FOR ALL
  USING (public.app_user_can_access_company(company_id))
  WITH CHECK (public.app_user_can_access_company(company_id));
"""


def _policy_org_legacy(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_isolation ON public.{table};
CREATE POLICY {table}_isolation ON public.{table}
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());
"""


SQL_FAMILY_A = "\n".join(_policy_company(t) for t in FAMILY_A)

SQL_FAMILY_C = r"""
DROP POLICY IF EXISTS ledger_consolidationgroup_isolation ON public.ledger_consolidationgroup;
CREATE POLICY ledger_consolidationgroup_isolation ON public.ledger_consolidationgroup
  FOR ALL
  USING (public.app_user_can_access_consolidation_group(id))
  WITH CHECK (
    organization_id = public.app_current_org()
    AND (
      public.app_user_is_org_admin(organization_id)
      OR public.app_user_can_access_consolidation_group(id)
    )
  );

DROP POLICY IF EXISTS ledger_consolidationmember_isolation ON public.ledger_consolidationmember;
CREATE POLICY ledger_consolidationmember_isolation ON public.ledger_consolidationmember
  FOR ALL
  USING (
    public.app_user_can_access_consolidation_group(group_id)
    AND public.app_user_can_access_company(company_id)
  )
  WITH CHECK (
    public.app_user_can_access_consolidation_group(group_id)
    AND public.app_user_can_access_company(company_id)
  );

DROP POLICY IF EXISTS ledger_consolidationelimination_isolation ON public.ledger_consolidationelimination;
CREATE POLICY ledger_consolidationelimination_isolation ON public.ledger_consolidationelimination
  FOR ALL
  USING (public.app_user_can_access_consolidation_group(group_id))
  WITH CHECK (public.app_user_can_access_consolidation_group(group_id));
"""

# Index pour perf EXISTS CompanyAccess
SQL_INDEXES = r"""
CREATE INDEX IF NOT EXISTS tenancy_companyaccess_user_company_idx
  ON public.tenancy_companyaccess (user_id, company_id);
CREATE INDEX IF NOT EXISTS tenancy_membership_user_org_active_idx
  ON public.tenancy_membership (user_id, organization_id)
  WHERE is_active = true;
"""

REVERSE_A = "\n".join(_policy_org_legacy(t) for t in reversed(FAMILY_A))

REVERSE_C = r"""
DROP POLICY IF EXISTS ledger_consolidationelimination_isolation ON public.ledger_consolidationelimination;
CREATE POLICY ledger_consolidationelimination_isolation ON public.ledger_consolidationelimination
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

DROP POLICY IF EXISTS ledger_consolidationmember_isolation ON public.ledger_consolidationmember;
CREATE POLICY ledger_consolidationmember_isolation ON public.ledger_consolidationmember
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());

DROP POLICY IF EXISTS ledger_consolidationgroup_isolation ON public.ledger_consolidationgroup;
CREATE POLICY ledger_consolidationgroup_isolation ON public.ledger_consolidationgroup
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());
"""

REVERSE_INDEXES = r"""
DROP INDEX IF EXISTS public.tenancy_companyaccess_user_company_idx;
DROP INDEX IF EXISTS public.tenancy_membership_user_org_active_idx;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0031_rls_consolidation"),
        ("tenancy", "0011_a1_prime_platform_role_and_functions"),
    ]

    operations = [
        migrations.RunSQL(SQL_FAMILY_A, REVERSE_A),
        migrations.RunSQL(SQL_FAMILY_C, REVERSE_C),
        migrations.RunSQL(SQL_INDEXES, REVERSE_INDEXES),
    ]
