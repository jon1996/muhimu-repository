-- Validations OPS-01 sur base restaurée (lecture seule logique).
\set ON_ERROR_STOP on

SELECT current_database() AS db, current_setting('server_version') AS pg_version;

SELECT rolname, rolsuper, rolbypassrls, rolcanlogin
FROM pg_roles
WHERE rolname IN ('muhimu', 'muhimu_app', 'muhimu_platform')
ORDER BY 1;

SELECT count(*) AS tables
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

SELECT count(*) AS rls_forced
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
  AND c.relrowsecurity AND c.relforcerowsecurity;

SELECT count(*) AS policies FROM pg_policies WHERE schemaname = 'public';

SELECT proname
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public' AND p.prosecdef
ORDER BY 1;

SELECT extname FROM pg_extension ORDER BY 1;

SELECT
  (SELECT count(*) FROM tenancy_organization) AS orgs,
  (SELECT count(*) FROM tenancy_company) AS companies,
  (SELECT count(*) FROM ledger_journal) AS journals,
  (SELECT count(*) FROM ledger_entry) AS entries,
  (SELECT count(*) FROM ledger_entryline) AS lines,
  (SELECT count(*) FROM ledger_balancesnapshot) AS snapshots,
  (SELECT count(*) FROM identity_user) AS users;

-- Équilibre débit/crédit global
SELECT
  coalesce(sum(debit), 0) AS total_debit,
  coalesce(sum(credit), 0) AS total_credit,
  coalesce(sum(debit), 0) - coalesce(sum(credit), 0) AS imbalance
FROM ledger_entryline;

-- Écritures déséquilibrées (doit être 0)
SELECT count(*) AS unbalanced_entries
FROM (
  SELECT e.id
  FROM ledger_entry e
  JOIN ledger_entryline l ON l.entry_id = e.id
  GROUP BY e.id
  HAVING coalesce(sum(l.debit), 0) <> coalesce(sum(l.credit), 0)
) x;

-- FK orphelines lignes → écritures (doit être 0)
SELECT count(*) AS orphan_lines
FROM ledger_entryline l
LEFT JOIN ledger_entry e ON e.id = l.entry_id
WHERE e.id IS NULL;

-- app_bypass_rls false sous muhimu_app
SET SESSION AUTHORIZATION muhimu_app;
SELECT current_user AS as_app, public.app_bypass_rls() AS app_bypass_rls;
DO $$
BEGIN
  BEGIN
    EXECUTE 'SET ROLE muhimu_platform';
    RAISE EXCEPTION 'UNEXPECTED: muhimu_app could SET ROLE muhimu_platform';
  EXCEPTION
    WHEN insufficient_privilege THEN
      RAISE NOTICE 'OK: SET ROLE muhimu_platform denied from muhimu_app';
    WHEN OTHERS THEN
      IF SQLERRM ILIKE '%permission%' OR SQLERRM ILIKE '%denied%' OR SQLERRM ILIKE '%cannot%' THEN
        RAISE NOTICE 'OK: SET ROLE denied (%)', SQLERRM;
      ELSE
        RAISE;
      END IF;
  END;
END
$$;
RESET SESSION AUTHORIZATION;

-- Contournement GUC bypass (doit rester false / non privilégié pour app)
SET SESSION AUTHORIZATION muhimu_app;
SELECT set_config('app.bypass_rls', 'true', false);
SELECT public.app_bypass_rls() AS bypass_after_guc_forge;
RESET SESSION AUTHORIZATION;
