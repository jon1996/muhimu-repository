# SAAS-03 — Rapport de corrections (V1, V2, V4) et proposition V3

**Date :** 2026-10-10  
**Déploiement :** aucun  
**Données production :** non modifiées  
**Règles SYSCOHADA :** non modifiées  
**ARCH-01 :** non démarré  

---

## 1. Synthèse

| Item | Statut |
|---|---|
| **V1** Révocation CompanyAccess | **Implémenté** |
| **V2** RLS organization / membership | **Implémenté** |
| **V3** RLS company-level | **Design seulement** — en attente validation (`SAAS03_V3_RLS_DESIGN.md`) |
| **V4** Consolidation / CompanyAccess | **Implémenté** |
| Tests | **233** découverts · **232** OK · **1** skipped (V3) · **0** FAIL |

**Décision partielle :** **CONDITIONAL GO** pour V1/V2/V4.  
**V3 :** **NO-GO** jusqu’à accord sur l’architecture A1.

---

## 2. Modifications effectuées

### V1 — Révocation

| Fichier | Changement |
|---|---|
| `backend/apps/tenancy/api.py` | `DELETE /api/companies/{company_id}/access/{access_id}` |

Comportement :

- `require_admin` uniquement  
- Vérifie org + société + access_id  
- Supprime `CompanyAccess`  
- `record_audit` (`company.access.revoke`)  
- Effet session : pas de cache d’accès — refus dès la requête suivante (middleware re-évalue)

### V2 — RLS org / membership

| Fichier | Changement |
|---|---|
| `backend/apps/tenancy/migrations/0010_rls_organization_membership.py` | ENABLE + FORCE RLS |

Politiques :

- **membership** : `user_id = app_current_user()` OU `organization_id = app_current_org()` OU bypass  
- **organization** : org courante OU EXISTS membership actif pour l’utilisateur OU bypass  
- **INSERT organization** : `app_current_user() IS NOT NULL` (création de dossier)  
- Réutilise `app_current_user()` (platform.0002)

Rollback : REVERSE SQL de la migration 0010.

### V4 — Consolidation

| Fichier | Changement |
|---|---|
| `backend/apps/ledger/services/consolidation.py` | `user_can_access_group`, filtres list/panel/pdf/create/add_member |
| `backend/apps/ledger/api.py` | Passage `user` + `membership` ; assert sur mutations |

Règle : un périmètre n’est visible / éditable que si **toutes** ses sociétés membres sont dans `companies_queryset_for`.

### V3 — non appliqué

Voir [`SAAS03_V3_RLS_DESIGN.md`](./SAAS03_V3_RLS_DESIGN.md) — stratégie recommandée **A1** (`app_user_can_access_company` SECURITY DEFINER), sans GUC company seul.

---

## 3. Preuves de tests

**Commande :**

```bash
docker compose exec -T backend python manage.py test \
  apps.tenancy.tests.test_isolation \
  apps.ledger.tests.test_snapshot_concurrency \
  apps --verbosity=1
```

**Environnement :** conteneur Docker, base `test_*` créée/détruite.  
**Log :** `_test_run_saas03_fix.log`

| Suite | Résultat |
|---|---|
| Isolation SAAS-03 (+ consolidation V4) | OK (1 skipped = V3) |
| ACC-01 concurrence snapshots | OK |
| Suite historique apps | OK |
| **Total** | **Ran 233 · OK (skipped=1)** |

### Détail

| Catégorie | Statut |
|---|---|
| Réussis | 232 |
| Échoués | 0 |
| Ignorés | 1 — `test_rls_hides_unassigned_company_rows_within_cabinet` (V3 pending) |
| Non exécutés | Tests de charge / pentest (hors scope) |

### Contournements couverts (échantillonnage)

- Cross-org API IDOR écritures / PDF / documents — OK  
- Cabinet C2 via header / id — OK  
- Révocation API + refus immédiat — OK  
- RLS `muhimu_app` : org A ≠ org B ; enum orgs sans contexte = 0 — OK  
- Consolidation mixte C1+C2 refusée au comptable C1 — OK  

---

## 4. Risques résiduels

| Risque | Niveau | Mitigation |
|---|---|---|
| Pas encore de RLS company (V3) | HIGH résiduel | Controles app + tests IDOR ; design A1 en attente |
| `SECURITY DEFINER` mal écrit (futur V3) | — | Revue obligatoire avant merge |
| Staff platform bypass RLS | MEDIUM | Process ops / MFA (P1) |
| Celery futur sans contexte tenant | MEDIUM | Helper obligatoire au branchement |
| Tests Django sous superuser `muhimu` | LOW | Tests RLS dédiés `muhimu_app` maintenus |

---

## 5. Décision GO / NO-GO

| Domaine | Décision |
|---|---|
| V1 révocation | **GO** |
| V2 enum organisations | **GO** |
| V4 consolidation | **GO** |
| V3 RLS société | **NO-GO** (attente validation design A1) |
| SAAS-03 global | **CONDITIONAL GO** — bêta possible côté API isolation org/cabinet **après** accord V3 si défense DB exigée avant pilotes |

---

## 6. Prochaine étape demandée

Valider ou amender [`SAAS03_V3_RLS_DESIGN.md`](./SAAS03_V3_RLS_DESIGN.md) (recommandation **A1**).

Après accord : migration V3 non destructive + désactivation du `@skip` + re-run 233+.
