# SAAS-03 V3 / A1′ — Rapport d’implémentation

**Date :** 2026-10-10  
**Environnement :** développement / test Docker uniquement  
**Production :** non déployé  
**Décision :** **GO (dev/test)** — **NO-GO production** tant que OPS-01 (backup/restore) et validation staging ne sont pas faits

---

## 1. Architecture finale

```
┌──────────── ERP (APP_ROLE=erp) ────────────┐
│  Django + muhimu_app (NOSUPERUSER,         │
│  NOBYPASSRLS)                              │
│  TenantMiddleware → GUCs user/org          │
│  RLS : app_user_can_access_company(cid)    │
└────────────────────────────────────────────┘

┌──────── Console (APP_ROLE=platform) ───────┐
│  Django + muhimu_platform (NOSUPERUSER,    │
│  BYPASSRLS) — pas de GUC bypass            │
└────────────────────────────────────────────┘

┌──────── migrate / bootstrap / test ────────┐
│  muhimu (superuser, BYPASSRLS)             │
└────────────────────────────────────────────┘
```

**Menace modèle (explicite) :** les GUC `app.current_user_id` / `app.current_organization_id` ne sont **pas** une preuve cryptographique. A1′ protège contre les **oublis de filtre ORM** sous `muhimu_app`. Une compromission SQL sous ce rôle peut encore forger l’identité GUC (classe B). Le bypass total via `app.bypass_rls` est **fermé**.

---

## 2. Fichiers modifiés

| Fichier | Rôle |
|---|---|
| `backend/apps/tenancy/migrations/0011_a1_prime_platform_role_and_functions.py` | Rôle platform + fonctions DEFINER + policies B/org |
| `backend/apps/ledger/migrations/0032_a1_prime_rls_company.py` | Policies famille A + C + index |
| `backend/apps/platform/migrations/0003_a1_prime_demogrant_policy.py` | DemoGrant sans bypass GUC |
| `backend/apps/tenancy/rls.py` | `bind_tenant_context` / `clear` ; `bypass_rls` no-op |
| `backend/apps/tenancy/middleware.py` | Suppression GUC bypass |
| `backend/apps/tenancy/api.py` | `create_own_organization` sans bypass |
| `backend/config/settings.py` | Connexion `muhimu_platform` si `APP_ROLE=platform` |
| `docker-compose.yml` | Env `POSTGRES_PLATFORM_*` |
| `backend/apps/tenancy/tests/test_isolation.py` | V3 unskipped + S1–S12 |
| `backend/apps/ledger/tests/db.py` (+ autres tests) | Retrait GUC bypass |
| `docs/audit/SAAS03_V3_A1_PRIME_REPORT.md` | Ce rapport |

---

## 3. Migrations ajoutées

1. `tenancy.0011_a1_prime_platform_role_and_functions`  
2. `ledger.0032_a1_prime_rls_company`  
3. `platform.0003_a1_prime_demogrant_policy`  

Appliquées sur la DB Docker `muhimu` (dev). **Non poussées en production.**

---

## 4. Rôles PostgreSQL

| Rôle | Login | Superuser | BYPASSRLS | Usage |
|---|---|---|---|---|
| `muhimu` | oui | oui | oui | migrate, bootstrap, tests Django |
| `muhimu_app` | oui | **non** | **non** | API ERP |
| `muhimu_platform` | oui | **non** | **oui** | Console staff |

Vérifié : `muhimu_app` ne peut pas `SET ROLE muhimu_platform` (test S9).  
Aucun GRANT du rôle platform vers `muhimu_app`.

---

## 5. Politiques RLS

### Fonctions

| Fonction | Security | Notes |
|---|---|---|
| `app_bypass_rls()` | INVOKER | **Toujours `false`** (GUC ignoré) |
| `app_current_user()` / `app_current_org()` | INVOKER | `search_path` fixé ; EXECUTE restreint |
| `app_user_can_access_company(uuid)` | **DEFINER** | Fail closed ; org+user+membership+Access |
| `app_user_is_org_admin(uuid)` | DEFINER | INSERT company |
| `app_user_can_access_consolidation_group(uuid)` | DEFINER | Famille C |

### Famille A (22 tables ledger + officers)

`USING` / `WITH CHECK` : `app_user_can_access_company(company_id)`

### Famille B

- `tenancy_company` : access company / admin org à l’INSERT  
- `tenancy_companyaccess` : admin ou propre ligne  

### Famille C

- `ledger_consolidationgroup` / `member` / `elimination` via `app_user_can_access_consolidation_group`

### Org / membership / audit / demogrant

Politiques réécrites **sans** `app_bypass_rls()` utile (fonction always-false ; rôles privilégiés contournent via attribut PG).

---

## 6. Résultats des tests

Exécutés dans Docker `backend` :

| Suite | Résultat |
|---|---|
| Isolation SAAS-03 + S1–S12 + ACC-01 concurrence | **51/51 OK** |
| Suite complète Django | **246/246 OK** (253 s) |

Dont :

- Test V3 `test_rls_hides_unassigned_company_rows_within_cabinet` **réactivé et OK**  
- S1–S12 OK (classe A + documentation classe B)  
- ACC-01 concurrence OK  
- Consolidation V4 OK  
- Own organization / bootstrap / platform mail / demo grants OK  

---

## 7. Vulnérabilités corrigées

| ID | Avant | Après |
|---|---|---|
| Bypass GUC forgeable | `set_config('app.bypass_rls','on')` ouvrait toute la RLS | Fonction always-false ; bypass = rôle PG uniquement |
| Isolation société cabinet | Filtre app seulement | RLS company-level A1′ |
| Console via même rôle + GUC | Staff posait bypass GUC sous `muhimu_app` | Connexion `muhimu_platform` BYPASSRLS |
| DEFINER non durci | N/A | `search_path`, REVOKE PUBLIC, GRANT ciblé |

---

## 8. Risques résiduels

1. **Forgery `app.current_user_id`** sous compromission `muhimu_app` (classe B — documenté, non « corrigé » par A1′).  
2. Gouvernance du rôle `muhimu_platform` (mots de passe, accès réseau).  
3. Perf EXISTS sous charge (index ajoutés ; mesurer en staging).  
4. Celery futur : doit appeler `bind_tenant_context` (fail closed sinon).  
5. Django admin `/django` sous ERP : nécessite rôle privilégié (plus de GUC bypass).

---

## 9. Plan de rollback

```text
1. migrate reverse ledger.0032 → tenancy.0011 → platform.0003
   (recrée policies org-only + restaure app_bypass_rls GUC)
2. Remettre POSTGRES_APP_USER pour platform dans compose/settings
3. Redéployer code middleware précédent si besoin
4. DROP ROLE muhimu_platform (optionnel)
```

Rollback SQL partiel possible en restaurant les policies `organization_id = app_current_org()` depuis les migrations historiques.

---

## 10. Décision

| Périmètre | Verdict |
|---|---|
| **Dev / test Docker** | **GO** — A1′ implémenté, 246 tests verts |
| **Production** | **NO-GO** — pas d’autorisation de déploiement ; backup/restore + staging requis |

**ARCH-01 non démarré** (conformément à la consigne).

---

## Annexe — Inventaire usages historiques du bypass GUC

| Usage | Traitement A1′ |
|---|---|
| `TenantMiddleware` bypass staff/superuser | Supprimé ; platform = rôle BYPASSRLS |
| `tenancy.rls.bypass_rls()` | No-op documenté |
| `bootstrap_demo` / `sync_pcgo` | Rôle `muhimu` (déjà privilégié) |
| `create_own_organization` | `bind_tenant_context` + membership owner |
| Tests `LedgerDbTestCase` etc. | Rôle test `muhimu` ; GUC retiré |
