# SAAS-03 — Rapport d’isolation multi-tenant (phase audit + tests)

**Date :** 2026-10-10  
**Statut initial (audit) :** NO-GO — voir correctifs dans `SAAS03_FIX_REPORT.md`  
**Mise à jour :** V1/V2/V4 implémentés ; V3 en attente de design (`SAAS03_V3_RLS_DESIGN.md`)  
**Tests :** `apps/tenancy/tests/test_isolation.py`  
**Log :** `_test_run_saas03.log`

---

## 1. Architecture multi-tenant observée

| Couche | Mécanisme |
|---|---|
| Identité | Session cookie ERP (`SessionAuth` Django Ninja) |
| Contexte | En-têtes `X-Organization-Slug`, `X-Company-Id` |
| Middleware | `TenantMiddleware` → Membership + `user_can_access_company` + `set_config` RLS |
| AuthZ API | `require_membership` / `require_company` / `require_writer` / `require_admin` |
| Isolation DB | RLS PostgreSQL `organization_id = app_current_org()` + `FORCE` |
| Rôle runtime | `muhimu_app` (`NOSUPERUSER`, `NOBYPASSRLS`) |
| Isolation société | **Applicative seulement** (`CompanyAccess` pour cabinets) |

**Tables avec RLS (échantillon) :** `ledger_*` financiers, `tenancy_company`, `tenancy_companyaccess`, `audit_auditlog`, `platform_demogrant`.

**Tables sans RLS :** `tenancy_organization`, `tenancy_membership`, `identity_user` (constaté).

**Console platform :** staff → `bypass_rls=on` (volontaire).

---

## 2. Matrice des autorisations (observée)

| Rôle | Org SME | Cabinet (sociétés) | Écriture ledger | Audit logs | Grant CompanyAccess |
|---|---|---|---|---|---|
| owner / admin | toutes sociétés | toutes | oui | oui | oui |
| accountant | toutes sociétés | **assignées seulement** | oui | non | non |
| auditor | toutes / assignées* | assignées* | lecture | oui | non |
| viewer | idem | assignées* | lecture | non | non |

\* SME : tout membre voit toutes les sociétés de l’org. Cabinet : non-admin → `CompanyAccess`.

---

## 3. Chemins d’accès aux données financières (inventaire)

| Chemin | Contrôle principal |
|---|---|
| `/api/ledger/entries*` | `require_company` + filtre `company=` |
| Balance / grand-livre / états / PDF | idem |
| Documents `/ledger/documents/{id}/file` | filtre `company=` |
| Immobilisations, banque, caisse, FX | filtre `company=` |
| Consolidation | **org-level** (`require_membership`) — pas de filtre CompanyAccess |
| `/api/companies`, access grant | membership + admin pour grant |
| Admin Django `/django/` | superuser / staff platform + bypass RLS |
| Media URL Django | pas de route `media/` dans `urls.py` ERP (download via API) |

---

## 4. Tests réalisés et résultats

**Commande :**  
`docker compose exec -T backend python manage.py test apps.tenancy.tests.test_isolation --verbosity=2`

| Résultat | Nombre |
|---|---|
| Total | **29** |
| Réussis | **25** |
| Échoués | **4** (exigences sécurité non satisfaites) |
| Ignorés | **0** |

### Ce qui est validé (OK)

- Utilisateur org A ne liste pas org B.
- Spoofing slug org B / company B → 400/403.
- IDOR écriture / document cross-org → 404.
- PDF états / livres refusés hors contexte.
- Comptable cabinet : liste seulement C1 ; C2 inaccessible via header / ID / PDF.
- Révocation ORM de `CompanyAccess` bloque immédiatement l’API.
- Owner cabinet voit C1+C2.
- Accès légitimes A et C1 OK.
- RLS org : `muhimu_app` + contexte A ne voit pas les écritures B.
- Sans contexte org : 0 ligne `ledger_entry`.
- Rôle `muhimu_app` sans `BYPASSRLS` ; `FORCE RLS` sur `ledger_entry`.

### Échecs = vulnérabilités / gaps

Voir section 5.

---

## 5. Vulnérabilités découvertes

### SAAS-03-V1 — Pas d’endpoint de révocation `CompanyAccess`
- **Gravité :** HIGH  
- **Cause :** `POST .../access` existe ; `DELETE .../access/{id}` absent  
- **Fichier :** `backend/apps/tenancy/api.py`  
- **Reproduction :** `test_owner_can_revoke_access_via_api` → HTTP 404  
- **Conséquence :** impossible de révoquer proprement un accès cabinet via l’API produit (contournement admin/ORM uniquement)  
- **Correction recommandée :** endpoint DELETE admin + audit `company.access.revoke`

### SAAS-03-V2 — RLS absente sur `tenancy_organization` / `tenancy_membership`
- **Gravité :** HIGH  
- **Cause :** aucune politique RLS sur ces tables  
- **Fichiers :** migrations `tenancy` (pas de RLS org/membership)  
- **Reproduction :** `test_organization_and_membership_tables_have_rls` ; `test_app_role_cannot_enumerate_organizations_without_context` (count=3)  
- **Conséquence :** le rôle applicatif peut énumérer organisations (et vraisemblablement memberships) hors contexte tenant  
- **Correction recommandée :** activer RLS (+ politiques adaptées memberships par `user_id` / org)

### SAAS-03-V3 — RLS n’isole pas les sociétés au sein d’une organisation
- **Gravité :** HIGH (défense en profondeur)  
- **Cause :** politiques `organization_id = app_current_org()` uniquement  
- **Fichiers :** `ledger/migrations/0002_rls.py` et suivantes  
- **Reproduction :** `test_rls_hides_unassigned_company_rows_within_cabinet` (1 ligne C2 visible)  
- **Conséquence :** si un bug applicatif oublie le filtre `company=`, la DB ne protège pas C2 d’un contexte cabinet  
- **Correction recommandée :**  
  - option A : `app.current_company_id` + politiques company pour tables ledger ;  
  - option B : accepter le risque avec revue systématique + tests IDOR (moins sûr)

### SAAS-03-V4 — Consolidation org-wide sans contrôle CompanyAccess *(revue code, non encore en test dédié)*
- **Gravité :** MEDIUM  
- **Cause :** `list_consolidation` / PDF : `require_membership` seulement  
- **Fichier :** `backend/apps/ledger/api.py` (~2058–2159)  
- **Conséquence :** un accountant limité à C1 pourrait lire des agrégats incluant C2 si un groupe existe  
- **Correction recommandée :** filtrer membres/groupes selon sociétés accessibles ; refuser PDF si membre hors périmètre

### SAAS-03-V5 — Staff platform bypasse RLS *(accepté avec réserve)*
- **Gravité :** MEDIUM (risque ops)  
- **Cause :** `TenantMiddleware` bypass si `APP_ROLE=platform` et `is_staff`  
- **Fichier :** `tenancy/middleware.py`  
- **Correction recommandée :** journaliser toutes les lectures sensibles ; MFA staff ; comptes staff limités

---

## 6. Corrections nécessaires (en attente d’autorisation)

Ordre suggéré :

1. **V1** — DELETE `CompanyAccess` + tests  
2. **V2** — RLS sur organization / membership (+ identity si pertinent)  
3. **V3** — décider A (RLS company) ou B (gel applicatif + tests élargis)  
4. **V4** — garde consolidation / CompanyAccess  
5. Re-run isolation (29) + suite complète (199+) + ACC-01

**Aucune de ces corrections n’a été appliquée.**

---

## 7. Risques résiduels (même après correctifs prévus)

- Superuser PostgreSQL `muhimu` contourne RLS (normal pour migrations).  
- Celery / jobs futurs devront reposer le contexte RLS.  
- Fichiers media sur disque : chemins `documents/{company_id}/` — sécuriser le stockage objet plus tard.  
- Tests Django tournent en superuser : les tests RLS dédiés via `muhimu_app` restent obligatoires en CI.

---

## 8. Décision SAAS-03

| Critère | État |
|---|---|
| Isolation API inter-organisations | **OK** (tests verts) |
| Isolation API inter-sociétés cabinet | **OK** (tests verts) |
| Révocation d’accès API | **NOK** (V1) |
| RLS org sur ledger | **OK** |
| RLS company / tables identité | **NOK** (V2, V3) |
| Défense en profondeur DB | **Insuffisante** |

### **NO-GO** pour clôturer SAAS-03

La couche API est globalement saine pour les scénarios IDOR testés, mais les gaps RLS et l’absence de révocation API empêchent un GO sécurité SaaS.

---

## Prochaine étape

**Autorisation demandée** pour implémenter les correctifs V1–V4 (sans déployer, sans démarrer ARCH-01).

Après correctifs : re-run isolation + suite 199+ + mise à jour de ce rapport en **CONDITIONAL GO / GO**.
