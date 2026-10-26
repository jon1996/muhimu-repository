"""ACC-03 — intégrité PostgreSQL : immutabilité POSTED + équilibre débit/crédit.

Appliquer uniquement après autorisation explicite sur chaque environnement.
Les tests ACC-03 utilisent une base PostgreSQL temporaire isolée.
"""

from django.db import migrations

FORWARD = r"""
-- =============================================================================
-- ACC-03 : helpers
-- =============================================================================
CREATE OR REPLACE FUNCTION public.ledger_assert_entry_balanced(p_entry_id uuid)
RETURNS void
LANGUAGE plpgsql
STRICT
SET search_path = pg_catalog, public
AS $$
DECLARE
  st text;
  td numeric(19, 2);
  tc numeric(19, 2);
BEGIN
  SELECT e.status INTO st FROM public.ledger_entry AS e WHERE e.id = p_entry_id;
  IF st IS NULL OR st <> 'posted' THEN
    RETURN;
  END IF;

  SELECT COALESCE(SUM(l.debit), 0), COALESCE(SUM(l.credit), 0)
    INTO td, tc
  FROM public.ledger_entryline AS l
  WHERE l.entry_id = p_entry_id;

  IF td <> tc THEN
    RAISE EXCEPTION
      'ACC-03: écriture % déséquilibrée (débit=% crédit=%)',
      p_entry_id, td, tc
      USING ERRCODE = 'check_violation';
  END IF;
  IF td = 0 THEN
    RAISE EXCEPTION
      'ACC-03: écriture % sans montant',
      p_entry_id
      USING ERRCODE = 'check_violation';
  END IF;
END;
$$;

-- =============================================================================
-- Immutabilité Entry (POSTED) — immédiat, pas de GUC de contournement
-- =============================================================================
CREATE OR REPLACE FUNCTION public.ledger_forbid_posted_entry_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status = 'posted' THEN
      RAISE EXCEPTION 'ACC-03: écriture validée immuable (DELETE)'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;

  -- UPDATE : toute mutation lorsque l'état précédent est posted
  IF OLD.status = 'posted' THEN
    RAISE EXCEPTION 'ACC-03: écriture validée immuable (UPDATE)'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ledger_entry_forbid_posted_mutation ON public.ledger_entry;
CREATE TRIGGER trg_ledger_entry_forbid_posted_mutation
  BEFORE UPDATE OR DELETE ON public.ledger_entry
  FOR EACH ROW
  EXECUTE FUNCTION public.ledger_forbid_posted_entry_mutation();

-- =============================================================================
-- Immutabilité EntryLine — annotations whitelist uniquement
-- =============================================================================
CREATE OR REPLACE FUNCTION public.ledger_forbid_posted_line_substance()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
  parent_status text;
BEGIN
  IF TG_OP = 'INSERT' THEN
    SELECT e.status INTO parent_status
    FROM public.ledger_entry AS e WHERE e.id = NEW.entry_id;
    IF parent_status = 'posted' THEN
      RAISE EXCEPTION 'ACC-03: ligne d''une écriture validée immuable (INSERT)'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
  END IF;

  IF TG_OP = 'DELETE' THEN
    SELECT e.status INTO parent_status
    FROM public.ledger_entry AS e WHERE e.id = OLD.entry_id;
    IF parent_status = 'posted' THEN
      RAISE EXCEPTION 'ACC-03: ligne d''une écriture validée immuable (DELETE)'
        USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;

  -- UPDATE
  SELECT e.status INTO parent_status
  FROM public.ledger_entry AS e WHERE e.id = OLD.entry_id;
  IF parent_status IS DISTINCT FROM 'posted' THEN
    RETURN NEW;
  END IF;

  IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
     OR NEW.company_id IS DISTINCT FROM OLD.company_id
     OR NEW.entry_id IS DISTINCT FROM OLD.entry_id
     OR NEW.account_id IS DISTINCT FROM OLD.account_id
     OR NEW.cage_section_id IS DISTINCT FROM OLD.cage_section_id
     OR NEW.label IS DISTINCT FROM OLD.label
     OR NEW.debit IS DISTINCT FROM OLD.debit
     OR NEW.credit IS DISTINCT FROM OLD.credit
     OR NEW.currency_code IS DISTINCT FROM OLD.currency_code
     OR NEW.foreign_amount IS DISTINCT FROM OLD.foreign_amount
     OR NEW.fx_rate IS DISTINCT FROM OLD.fx_rate
     OR NEW.position IS DISTINCT FROM OLD.position
  THEN
    RAISE EXCEPTION 'ACC-03: ligne d''une écriture validée immuable (UPDATE substance)'
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;

  -- Whitelist : due_on, lettering, bank_pointage, third_party_id
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ledger_entryline_forbid_posted_substance ON public.ledger_entryline;
CREATE TRIGGER trg_ledger_entryline_forbid_posted_substance
  BEFORE INSERT OR UPDATE OR DELETE ON public.ledger_entryline
  FOR EACH ROW
  EXECUTE FUNCTION public.ledger_forbid_posted_line_substance();

-- =============================================================================
-- Équilibre — contrôle IMMÉDIAT au passage POSTED (chemin nominal post_entry)
-- =============================================================================
CREATE OR REPLACE FUNCTION public.ledger_trg_entry_posted_balance()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF NEW.status = 'posted'
     AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'posted') THEN
    PERFORM public.ledger_assert_entry_balanced(NEW.id);
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ledger_entry_posted_balance ON public.ledger_entry;
CREATE TRIGGER trg_ledger_entry_posted_balance
  AFTER INSERT OR UPDATE OF status ON public.ledger_entry
  FOR EACH ROW
  EXECUTE FUNCTION public.ledger_trg_entry_posted_balance();

-- =============================================================================
-- Équilibre — constraint trigger DEFERRABLE (filet transactionnel)
-- Vérifie en fin de transaction si l'écriture est posted (insert/update montants).
-- =============================================================================
CREATE OR REPLACE FUNCTION public.ledger_trg_entryline_balanced_deferred()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
DECLARE
  eid uuid;
BEGIN
  eid := COALESCE(NEW.entry_id, OLD.entry_id);
  PERFORM public.ledger_assert_entry_balanced(eid);
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_ledger_entryline_balanced_deferred ON public.ledger_entryline;
CREATE CONSTRAINT TRIGGER trg_ledger_entryline_balanced_deferred
  AFTER INSERT OR DELETE OR UPDATE OF debit, credit, entry_id
  ON public.ledger_entryline
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW
  EXECUTE FUNCTION public.ledger_trg_entryline_balanced_deferred();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS trg_ledger_entryline_balanced_deferred ON public.ledger_entryline;
DROP TRIGGER IF EXISTS trg_ledger_entry_posted_balance ON public.ledger_entry;
DROP TRIGGER IF EXISTS trg_ledger_entryline_forbid_posted_substance ON public.ledger_entryline;
DROP TRIGGER IF EXISTS trg_ledger_entry_forbid_posted_mutation ON public.ledger_entry;

DROP FUNCTION IF EXISTS public.ledger_trg_entryline_balanced_deferred();
DROP FUNCTION IF EXISTS public.ledger_trg_entry_posted_balance();
DROP FUNCTION IF EXISTS public.ledger_forbid_posted_line_substance();
DROP FUNCTION IF EXISTS public.ledger_forbid_posted_entry_mutation();
DROP FUNCTION IF EXISTS public.ledger_assert_entry_balanced(uuid);
"""


class Migration(migrations.Migration):
    atomic = False  # DDL triggers ; reverse explicite

    dependencies = [
        ("ledger", "0032_a1_prime_rls_company"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
