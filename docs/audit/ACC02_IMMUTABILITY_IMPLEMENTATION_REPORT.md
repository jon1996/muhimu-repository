# ACC-02 — Rapport d’implémentation (immutabilité POSTED)

**Date :** 2026-10-13  
**Lot autorisé :** L1 ACC-02 uniquement  
**Hors scope (non démarrés) :** ACC-03, CLOSE-01, PDF-CLAIM, migrations SQL

**Verdict :** **GO** (protection applicative) · risque SQL direct documenté → suite optionnelle triggers (autorisation séparée)

---

## 1. Matrice champs / opérations

### Modèles concernés

| Modèle | Rôle |
|---|---|
| `Entry` | En-tête d’écriture |
| `EntryLine` | Lignes débit/crédit |

### Champs immuables après `POSTED` (substance comptable)

**Entry :** `organization`, `company`, `exercise`, `period`, `journal`, `number`, `number_display`, `accounting_date`, `value_date`, `description`, `document_ref`, `status`, `source`, `idempotency_key`, `reversed_entry`, `posted_at`, `posted_by` (+ tout UPDATE générique).

**EntryLine :** `organization`, `company`, `entry`, `account`, `cage_section`, `label`, `debit`, `credit`, `currency_code`, `foreign_amount`, `fx_rate`, `position`.

### Champs d’annotation autorisés (EntryLine uniquement)

| Champ | Usage |
|---|---|
| `due_on` | Échéance auxiliaire (`set_line_due`) |
| `lettering` | Lettrage / délettrage |
| `bank_pointage` | Pointage bancaire |
| `third_party` / `third_party_id` | Rattachement tiers (lettrage) |

Constante : `ENTRY_LINE_ANNOTATION_FIELDS` dans `apps/ledger/immutability.py`.

### Opérations autorisées

| Opération | POSTED |
|---|---|
| `post_entry` (`save(allow_posted_write=True)`) | Transition DRAFT→POSTED |
| `reverse_entry` | Nouvelle écriture (origine intacte) |
| Annotations whitelist via `QuerySet.update` / `save` annotation-only | Oui |
| `QuerySet.update` / `bulk_update` substance | **Refusé** |
| `bulk_create` de lignes sur entrée POSTED | **Refusé** |
| `delete` écriture/ligne POSTED | **Refusé** |
| SQL direct `UPDATE`/`DELETE` | **Non bloqué** (risque résiduel) |

---

## 2. Protections appliquées

| Couche | Mécanisme |
|---|---|
| `EntryQuerySet` | `update` / `bulk_update` / `delete` refusent les POSTED ; interdit `status=posted` via `update` |
| `EntryLineQuerySet` | `update`/`bulk_update` : whitelist annotations ; `bulk_create`/`delete` bloqués si parent POSTED |
| `Entry.save` / `EntryLine.save` | Inchangé + `EntryLine.save` autorise changements **uniquement** annotation |
| `Entry.delete` / `EntryLine.delete` | Bloquent POSTED |
| `_replace_lines` | Garde explicite si `status == POSTED` |
| Django Admin | Readonly + pas de delete/add lignes sur POSTED |

**Fichiers modifiés**

- `backend/apps/ledger/immutability.py` (**nouveau**)
- `backend/apps/ledger/models.py`
- `backend/apps/ledger/services/posting.py`
- `backend/apps/ledger/services/lettering.py` (docstring)
- `backend/apps/ledger/admin.py`
- `backend/apps/ledger/tests/test_immutability.py` (**nouveau**)
- `backend/apps/ledger/tests/test_due_on.py`

**Documents**

- `docs/audit/ACC02_SQL_TRIGGERS_DRAFT.sql` — brouillon **non appliqué**
- ce rapport

---

## 3. Chemins de contournement identifiés

| Chemin | Statut après L1 |
|---|---|
| `Model.save()` substance | Bloqué |
| `QuerySet.update()` | Bloqué (sauf annotations ligne) |
| `bulk_update()` | Bloqué substance |
| `bulk_create` lignes sur POSTED | Bloqué |
| Related manager `entry.lines.update(...)` | Bloqué (même QuerySet) |
| `_replace_lines` | Bloqué si POSTED |
| API update/delete brouillon | Inchangé (déjà sûr) |
| `reverse_entry` | Conservé |
| Django Admin | Durci |
| **SQL direct** (`cursor.execute`) | **Non bloqué** — test documentaire `test_sql_direct_still_bypasses_orm` |
| Rôle superuser / BYPASSRLS ops | Hors threat model app |
| Managers historiques migrations | Non concernés (pas de migration L1) |

---

## 4. Tests ajoutés / adaptés

**Nouveau :** `apps.ledger.tests.test_immutability` — montants, comptes, société, dates, lignes, `update`, `bulk_update`, annotations, lettrage, pointage service, échéances, contrepassation, isolation tenant, SQL direct documenté.

**Adapté :** `test_due_on` — plus de contournement `Entry.objects.update(status=POSTED)` ; passage par `post_entry` ; échéance via save annotation autorisée.

---

## 5. Non-régression

| Suite | Résultat |
|---|---|
| ACC-02 (`test_immutability` + `test_due_on`) | **OK** |
| ACC-01 (`test_snapshot_concurrency`) | **OK** |
| SAAS-03 (`apps.tenancy.tests.test_isolation`) | **OK** (47) |
| Suite `manage.py test apps` | **288 OK** (~538 s) |

Base : `docker compose exec -T backend python manage.py test … --keepdb`  
Aucun test désactivé ou supprimé pour masquer un échec.  
(265 historiques + tests ACC-02 / suites déjà enrichies depuis OPS-01 → **288**.)

---

## 6. Risques résiduels

1. **SQL direct** et outils hors ORM peuvent encore altérer les montants — démontré par test isolé.  
2. Protection **applicative uniquement** — pas de trigger PostgreSQL (volontaire, en attente d’autorisation).  
3. Whitelist annotations : élargir uniquement après revue (pas de `label` / `cage_section`).  
4. `allow_posted_write` sur `Entry.save` reste requis pour `post_entry` — usage à garder restreint.

---

## 7. Triggers PostgreSQL

Brouillon : `docs/audit/ACC02_SQL_TRIGGERS_DRAFT.sql`  
**Non appliqué.** Aligné avec le plan L2 ACC-03 (équilibre) ou un lot « ACC-02 SQL » dédié.

**Demande d’autorisation séparée** avant toute migration DDL.

---

## 8. Verdict

| Critère | Statut |
|---|---|
| Modification substance POSTED via ORM refusée | Oui |
| Annotations lettrage / pointage / échéance | Oui |
| Contrepassation | Oui |
| Isolation tenant préservée | Oui |
| Non-régression 288 | Oui |
| Garantie contre SQL direct | Non (documenté) |

### **GO** pour clôturer L1 ACC-02

Prochaine décision attendue : autoriser ou non **L2 ACC-03** (et/ou triggers SQL ACC-02).
