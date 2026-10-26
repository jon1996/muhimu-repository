# ACC-01 — Correction concurrence `BalanceSnapshot`

**Date :** 2026-10-10  
**Statut :** implémenté et validé par tests  
**Déploiement :** aucun  
**Données production :** non modifiées

---

## 1. Avant

### Comportement

`apply_posted_lines` faisait pour chaque ligne :

1. `get_or_create` du snapshot `(period, account)` ;
2. `snapshot.mov_debit += line.debit` en Python ;
3. `save()`.

### Cause du bug

Read-modify-write non atomique. Deux validations concurrentes (journaux distincts → `JournalSequence` non partagé) pouvaient :

- lire le même `mov_*` ;
- écrire chacune un increment partiel ;
- **perdre** l’un des mouvements.

Course à la création : deux `INSERT` simultanés sur `(period, account)` → `IntegrityError` non géré proprement (ou double logique d’ouverture incohérente).

### Impact potentiel

Balance / grand-livre / états financiers faux, sans exception visible.

---

## 2. Après

### Fichiers modifiés

| Fichier | Rôle |
|---|---|
| `backend/apps/ledger/services/balance.py` | Correction ACC-01 |
| `backend/apps/ledger/tests/test_snapshot_concurrency.py` | Tests concurrence réelle (nouveau) |
| `docs/audit/ACC01_FIX_REPORT.md` | Ce rapport |

### Mécanisme

1. **`select_for_update()` sur `AccountingPeriod`** — sérialise création/maj des snapshots d’une période (ordre de verrou : séquence journal déjà prise dans `post_entry`, puis période → pas de deadlock circulaire).
2. **Agrégation des lignes par `account_id`** (tri déterministe) — un seul update par compte et par pièce.
3. **Création sous savepoint** + reprise sur `IntegrityError` + `select_for_update`.
4. **Increments `F("mov_debit") + debit`** — atomicité SQL même hors verrou période (défense en profondeur).
5. Filtre `company_id` / `organization_id` sur l’`update` — pas de mise à jour cross-tenant par id orphelin.
6. Helper `posted_movement_totals` — vérité terrain `SUM(lignes posted)` pour assertions.

### Non modifié

- Règles SYSCOHADA / mapping SN
- `posting.py` (hors appel existant)
- `opening.py` (chemin setup, hors scope ACC-01)
- Schéma / migrations

---

## 3. Tests

### Nouveaux (`TransactionTestCase` + threads + connexions PG distinctes)

| Test | Scénario |
|---|---|
| `test_concurrent_first_snapshot_creation_no_lost_updates` | 8 posts parallèles, 1ʳᵉ création snapshot |
| `test_concurrent_posts_on_existing_snapshot_accumulate` | 12 posts après seed |
| `test_concurrent_mixed_accounts_preserve_double_entry_totals` | 10 posts, 4 comptes, équilibre D=C |
| `test_opening_carried_when_first_concurrent_posts_hit_new_period` | Ouvertures N-1 + concurrence mois N |

Chaque test compare `snapshot.mov_*` à `SUM(EntryLine)` des écritures validées.

**Important :** un journal distinct par worker (`J00`…`J15`) pour ne pas masquer la course derrière `JournalSequence.select_for_update`.

### Exécution (Docker, base `test_muhimu` isolée)

```text
Commande : docker compose exec -T backend python manage.py test apps.ledger.tests.test_snapshot_concurrency apps --verbosity=2
Résultat : Ran 199 tests in 156.450s — OK
Échecs   : 0
Ignorés  : 0
```

| Suite | Avant ACC-01 | Après ACC-01 |
|---|---|---|
| Tests existants | 195 OK | 195 OK (régression : aucune) |
| Nouveaux concurrence | — | 4 OK |
| **Total** | 195 | **199 OK** |

Log : `docs/audit/_test_run_acc01.log`

---

## 4. Risques résiduels

| Risque | Niveau | Commentaire |
|---|---|---|
| Contention sur période sous très forte charge multi-journaux | Faible / acceptable | Sérialise les maj snapshot d’une période ; intégrité prioritaire |
| `opening.py` seed décembre encore en RMW | Faible | Hors chemin de validation concurrente typique ; P1 éventuel |
| Drift historique si bug futur hors `apply_posted_lines` | Faible | Pas de job de réconciliation automatique (ACC-05 P1) |
| Deadlocks | Non observé | Ordre verrous stable : séquence journal → période |

---

## 5. Décision

**ACC-01 peut être considéré comme corrigé** sous réserve de votre validation.

Prochaine étape prévue (sur confirmation) : **SAAS-03** — tests d’isolation RLS.
