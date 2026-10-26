-- SUPERSEDE : implémenté dans ledger.0033_acc03_sql_integrity
-- Voir docs/audit/ACC03_SQL_INTEGRITY_REPORT.md
-- Ce fichier reste une archive du brouillon ACC-02.
--
-- ACC-02 / suite ACC-03 — BROUILLON (historique)
-- Autorisation product owner requise avant migration Django / exécution.
-- Objectif : bloquer UPDATE SQL des colonnes substance sur lignes/écritures POSTED.
-- Ne remplace pas la protection ORM livrée en L1.

-- Exemple (PostgreSQL) — à adapter aux noms réels de tables Django :
--   ledger_entry, ledger_entryline

/*
CREATE OR REPLACE FUNCTION ledger_forbid_posted_entry_update()
RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'posted' THEN
    RAISE EXCEPTION 'Écriture validée immuable (ACC-02 SQL)';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_entry_immutable
  BEFORE UPDATE ON ledger_entry
  FOR EACH ROW
  EXECUTE FUNCTION ledger_forbid_posted_entry_update();

CREATE OR REPLACE FUNCTION ledger_forbid_posted_line_substance()
RETURNS trigger AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM ledger_entry e WHERE e.id = OLD.entry_id AND e.status = 'posted'
  ) THEN
    IF NEW.debit IS DISTINCT FROM OLD.debit
       OR NEW.credit IS DISTINCT FROM OLD.credit
       OR NEW.account_id IS DISTINCT FROM OLD.account_id
       OR NEW.company_id IS DISTINCT FROM OLD.company_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.entry_id IS DISTINCT FROM OLD.entry_id
       OR NEW.label IS DISTINCT FROM OLD.label
       OR NEW.position IS DISTINCT FROM OLD.position
       OR NEW.currency_code IS DISTINCT FROM OLD.currency_code
       OR NEW.foreign_amount IS DISTINCT FROM OLD.foreign_amount
       OR NEW.fx_rate IS DISTINCT FROM OLD.fx_rate
       OR NEW.cage_section_id IS DISTINCT FROM OLD.cage_section_id
    THEN
      RAISE EXCEPTION 'Ligne validée immuable (ACC-02 SQL)';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ledger_entryline_annotations_only
  BEFORE UPDATE ON ledger_entryline
  FOR EACH ROW
  EXECUTE FUNCTION ledger_forbid_posted_line_substance();
*/

-- Whitelist SQL autorisée sur entryline POSTED :
--   due_on, lettering, bank_pointage, third_party_id
