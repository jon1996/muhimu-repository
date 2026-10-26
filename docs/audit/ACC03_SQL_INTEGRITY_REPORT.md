# ACC-03 — Rapport d’intégrité SQL PostgreSQL

**Date :** 2026-10-13  
**Lot :** L2 ACC-03  
**Environnement de preuve :** PostgreSQL 16 temporaire `muhimu-acc03` (port 5440)  
**DEV / bêta :** **non migrés** (vérifié : 0 ligne `0033_acc03` / 0 trigger `trg_ledger_*` sur DB DEV)

**Verdict :** **GO** pour la migration préparée et validée en labo isolé — **application DEV/bêta en attente d’autorisation explicite**.

---

## 1. Architecture retenue

### Propriétés protégées

1. **Équilibre** : une écriture `posted` a toujours `SUM(debit) = SUM(credit)` et un total non nul.  
2. **Immutabilité SQL** : montants, comptes, dates, société/organisation, labels, etc. non modifiables / non supprimables en SQL sur POSTED.  
3. **Annotations** autorisées sur lignes POSTED : `due_on`, `lettering`, `bank_pointage`, `third_party_id`.  
4. **Contrepassation** : nouvelle écriture uniquement ; l’origine reste intacte (SQL + ORM).

### Mécanismes PostgreSQL

| Objet | Type | Rôle |
|---|---|---|
| `ledger_assert_entry_balanced(uuid)` | FUNCTION | Contrôle ΣD=ΣC (numeric 19,2) |
| `trg_ledger_entry_forbid_posted_mutation` | BEFORE UPDATE/DELETE | Entry POSTED immuable |
| `trg_ledger_entryline_forbid_posted_substance` | BEFORE INSERT/UPDATE/DELETE | Substance bloquée ; annotations OK |
| `trg_ledger_entry_posted_balance` | AFTER INSERT/UPDATE OF status (**immédiat**) | Contrôle à la comptabilisation |
| `trg_ledger_entryline_balanced_deferred` | CONSTRAINT TRIGGER **DEFERRABLE INITIALLY DEFERRED** | Filet en fin de transaction |

### Choix IMMEDIATE + DEFERRABLE

- **IMMEDIATE** sur `status → posted` : compatible avec `post_entry` (lignes déjà présentes) et avec `TestCase` (pas besoin d’attendre COMMIT).  
- **DEFERRABLE** sur lignes : filet si plusieurs mutations de montants dans la même transaction avant commit (les drafts non postés sont ignorés par la fonction).  
- **Aucun GUC** de contournement (`app.allow_posted`, etc.) — exigence respectée.  
- **RLS inchangée** : aucune politique modifiée.

### Concurrence

- Les lignes POSTED ne peuvent pas être altérées (BEFORE immédiat) → impossible de déséquilibrer une écriture validée par UPDATE SQL concurrent (test 16, 4 threads).  
- Le passage POSTED déséquilibré est refusé immédiatement (AFTER status).  
- Isolation par défaut PostgreSQL (`READ COMMITTED`) suffisante avec ces triggers ; pas de besoin de `SERIALIZABLE` pour les scénarios couverts.

---

## 2. SQL et migrations préparés

| Livrable | Chemin |
|---|---|
| Migration Django | `backend/apps/ledger/migrations/0033_acc03_sql_integrity.py` |
| Compose labo | `docker-compose.acc03-integrity.yml` (projet `muhimu-acc03`) |
| Volume labo | `muhimu_acc03_pgdata` (**conservé**, `down` sans `-v`) |
| Brouillon historique | `docs/audit/ACC02_SQL_TRIGGERS_DRAFT.sql` (supersédé par 0033) |
| Tests | `backend/apps/ledger/tests/test_sql_integrity.py` |
| ACC-02 adapté | `test_immutability.test_sql_direct_amount_blocked_by_acc03` |

**Reverse SQL** inclus dans la migration (`DROP TRIGGER` / `DROP FUNCTION`).

---

## 3. Démonstration SQL direct

Sur la base labo ACC-03 (tests `test_04` … `test_07`) :

| Tentative SQL | Résultat |
|---|---|
| `UPDATE ledger_entryline SET debit=…` (POSTED) | **Refusé** (`ACC-03: … immuable`) |
| `DELETE` ligne POSTED | **Refusé** |
| `DELETE` écriture POSTED | **Refusé** |
| `UPDATE` `company_id` Entry POSTED | **Refusé** |
| `UPDATE` annotations (`due_on`, `lettering`, `bank_pointage`) | **Accepté** |
| `UPDATE status='posted'` sur brouillon déséquilibré | **Refusé** (équilibre) |

---

## 4. Tests de concurrence

`test_16_concurrent_sql_cannot_unbalance_posted` : 4 threads / connexions distinctes tentent un `UPDATE` montant sur ligne POSTED → tous bloqués ; solde inchangé.

---

## 5. Non-régression (base isolée uniquement)

Commandes (projet `muhimu-acc03`, image `muhimu-erp-api`, **pas** le service DEV) :

```text
docker compose -p muhimu-acc03 -f docker-compose.acc03-integrity.yml up -d
docker compose -p muhimu-acc03 -f docker-compose.acc03-integrity.yml --profile test run --rm test_runner python manage.py migrate --noinput
docker compose -p muhimu-acc03 -f docker-compose.acc03-integrity.yml --profile test run --rm test_runner python manage.py test …
```

| Suite | Résultat |
|---|---|
| ACC-03 (`test_sql_integrity`) + ACC-02 + ACC-01 | **54 OK** |
| Suite complète `apps` (+ isolation déjà incluse) | **309 OK** (~480 s) |

Aucun test désactivé.  
**DEV `muhimu` :** migration 0033 **absente** ; triggers ACC-03 **absents**.

---

## 6. Performance

`test_21_post_performance_smoke` : 15 `post_entry` < 30 s (garde-fou).  
Surcoût attendu : 1 trigger BEFORE + 1 AFTER status par validation ; annotations inchangées (pas de re-check d’équilibre sur `UPDATE OF` hors débit/crédit/entry_id pour le deferred).  
Pas de régression observée sur la suite 309.

---

## 7. Risques résiduels

| Risque | Niveau | Note |
|---|---|---|
| Superuser peut `DISABLE TRIGGER` | Faible | Hors threat model app `muhimu_app` |
| Données DEV déjà POSTED déséquilibrées avant migrate | À scanner | Script read-only recommandé avant apply |
| `TestCase` + seul DEFERRABLE | Mitigé | Contrôle IMMEDIATE sur status couvre `post_entry` |
| Volume labo `muhimu_acc03_pgdata` | Ops | Conservé ; suppression seulement sur autorisation |

---

## 8. Procédure de déploiement (après autorisation)

1. Sauvegarde OPS (`pg_dump -Fc`) de la cible.  
2. Scan read-only : écritures `posted` avec ΣD≠ΣC (doit être vide).  
3. Fenêtre courte : `python manage.py migrate ledger 0033_acc03_sql_integrity`.  
4. Vérifier 4 triggers `trg_ledger_*`.  
5. Smoke : post équilibré, annotation lettrage, tentative SQL montant → refus.  
6. **Ne pas** combiner avec CLOSE-01 / PDF-CLAIM dans la même fenêtre sans plan dédié.

Ordre recommandé : **DEV lab contrôlé** → bêta → (plus tard) prod.

---

## 9. Procédure de rollback

```bash
python manage.py migrate ledger 0032_a1_prime_rls_company
```

Exécute le SQL reverse (drop triggers/functions).  
Réversible sans perte de données métier.  
Ré-appliquer ACC-02 ORM reste en place (indépendant).

Plan vérifié en labo : `migrate ledger 0032 --plan` → unapply `0033_acc03_sql_integrity`.

---

## 10. Matrice de couverture des exigences

| # | Exigence | Test / preuve |
|---|---|---|
| 1 | Équilibrée acceptée | `test_01` |
| 2 | Déséquilibrée refusée (app) | `test_02` |
| 3 | DRAFT→POSTED déséquilibré SQL | `test_03`, `test_14` |
| 4 | SQL montant POSTED | `test_04` + ACC-02 |
| 5 | SQL delete ligne | `test_05` |
| 6 | SQL delete écriture | `test_06` |
| 7 | Changement société | `test_07` |
| 8–11 | Annotations / lettrage / pointage / échéance | `test_08`–`11` |
| 12 | Contrepassation | `test_12` |
| 13–15 | Import TX / rollback | `test_13`–`15` |
| 16 | Concurrence | `test_16` |
| 17 | RLS préservée | `test_17` |
| 18 | Rollback migration | `--plan` + SQL reverse |
| + | Cascade draft | `test_19` |
| + | Triggers présents | `test_18` |

---

## 11. Verdict

| Critère | Statut |
|---|---|
| Intégrité équilibre POSTED (PG) | Oui |
| Immutabilité SQL substance | Oui |
| Annotations / reverse | Oui |
| RLS non modifiée | Oui |
| DEV/bêta non migrés | Oui |
| Non-régression 309 | Oui |
| Prêt apply DEV/bêta | **Non** — attendre autorisation |

### **GO** (labo isolé) — **NO-GO apply** tant que non autorisé sur DEV/bêta

CLOSE-01 et PDF-CLAIM non démarrés.
