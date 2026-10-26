# SAAS-03 V3 — Proposition d’architecture RLS au niveau société

**Statut :** proposition — **aucune migration V3 appliquée**  
**Choix produit :** option A (défense PostgreSQL + contrôles Django)  
**Contrainte :** ne pas appliquer aveuglément `app.current_company_id` à toutes les tables

---

## 1. Inventaire des tables

### Tables ledger / tenancy déjà sous RLS **org** (`organization_id`)

| Table | Isolation société actuelle |
|---|---|
| `ledger_entry`, `ledger_entryline`, `ledger_balancesnapshot` | App only |
| `ledger_account`, `ledger_journal`, `ledger_exercise`, `ledger_accountingperiod` | App only |
| `ledger_sourcedocument`, `ledger_fixedasset`, `ledger_thirdparty`, banque, caisse, FX, CAGE, commitments, ESG, inventory | App only |
| `ledger_consolidation*` | Org-wide (légitime pour owner ; filtré V4 côté app) |
| `tenancy_company`, `tenancy_companyaccess`, `tenancy_companyofficer` | Org RLS |

### Tables **sans** company_id (hors scope V3 company-row)

| Table | Raison |
|---|---|
| `tenancy_organization`, `tenancy_membership` | Traitées en V2 |
| `identity_user` | Identité globale |
| `platform_demogrant` | Par `user_id` |
| `audit_auditlog` | Org (+ actor) ; company optionnelle |

---

## 2. Opérations légitimes multi-sociétés

| Opération | Qui | Besoin DB |
|---|---|---|
| Liste `/companies` | Membre | Plusieurs companies de l’org (filtrées CompanyAccess) |
| Consolidation | Owner / accountant autorisé | Lecture agrégée **plusieurs** companies |
| Owner/admin cabinet | Owner/admin | Toutes les companies de l’org |
| Comptable assigné | Accountant | **Une ou N** companies via CompanyAccess |
| PME | Tout membre | Toutes companies de l’org |
| Platform staff | Staff | Bypass RLS |
| Bootstrap / migrate | Owner DB | Bypass |

**Conclusion :** un simple `company_id = app.current_company_id` **cassera** consolidation et listes multi-sociétés s’il est appliqué à toutes les tables ledger sans mode « multi ».

---

## 3. Pourquoi une session `app.current_company_id` seule est insuffisante

Le rôle `muhimu_app` peut exécuter `set_config('app.current_company_id', …)`.  
Un attaquant SQL (ou bug) pourrait **usurper** un UUID de société.

Donc la variable de session **ne doit jamais être la seule preuve d’autorisation**.  
Elle peut servir de *hint* de contexte UI, mais l’autorisation doit être **dérivée en base** de Membership / CompanyAccess / rôle, via des fonctions `SECURITY DEFINER` contrôlées.

---

## 4. Architecture proposée (recommandée)

### 4.1 Fonctions SQL (SECURITY DEFINER, owner = `muhimu`)

```text
app_current_user()          -- déjà présent
app_current_org()           -- déjà présent
app_bypass_rls()            -- déjà présent

app_user_is_org_admin(org)  -- membership role in (owner, admin)
app_user_org_type(org)      -- sme | cabinet
app_user_can_access_company(company_id)  -- bool
app_user_accessible_company_ids()        -- SETOF uuid (optionnel)
```

Logique `app_user_can_access_company(cid)` :

1. `app_bypass_rls()` → true  
2. Company.organization_id doit = `app_current_org()` (si org posée) **ou** membership actif sur company.organization  
3. Si rôle owner/admin → true  
4. Si org type SME → true  
5. Sinon → EXISTS CompanyAccess(user, company)

Ces fonctions lisent `tenancy_*` en **definer** (bypass RLS des tables lues), avec corps figé — pas de SQL dynamique.

### 4.2 Politiques différenciées par famille de tables

| Famille | Politique USING proposée |
|---|---|
| **A — Données société strictes** (entry, line, snapshot, account, journal, period, exercise, documents, assets, bank, cash, fx, tiers, …) | `app_bypass_rls() OR app_user_can_access_company(company_id)` |
| **B — Tables org multi-sociétés** (`tenancy_company`, consolidation groups/members) | Org membership + (admin OU company accessible pour les lignes company-scoped) |
| **C — Consolidation group header** | Visible si **toutes** les sociétés membres sont accessibles (miroir V4) OU admin org |

**Ne pas** exiger `app.current_company_id` pour la famille A : l’autorisation vient de CompanyAccess/rôle, pas du header HTTP.

### 4.3 Rôle de `app.current_company_id` (optionnel, secondaire)

- Posé par le middleware **après** validation applicative `user_can_access_company`.  
- Utilisé seulement pour :  
  - WITH CHECK à l’INSERT (`company_id = app.current_company_id` **et** `app_user_can_access_company(company_id)`) afin d’éviter d’insérer sous une autre société autorisée par erreur.  
- Jamais utilisé seul dans USING.

### 4.4 Contexte transactionnel / connexions

- Conserver `CONN_MAX_AGE = 0`.  
- Middleware : set user → resolve org → resolve company → set_config ; `finally` clear.  
- Celery (futur) : chaque tâche doit appeler un helper `set_tenant_context(user_id, org_id, company_id|None)` ou échouer fermé.  
- Pas de pool PgBouncer transaction mode sans reset des GUCs.

---

## 5. Alternatives

| Option | Description | Avantages | Inconvénients |
|---|---|---|---|
| **A1 (recommandée)** | `app_user_can_access_company()` SECURITY DEFINER sur tables famille A | Autorisation réelle en DB ; multi-sociétés OK ; header non usurpable | Migration large ; perf à mesurer (EXISTS) |
| **A2** | Session `app.allowed_company_ids` (liste) posée par middleware après calcul Django | Simple USING `company_id = ANY(...)` | Liste forgable par `muhimu_app` → **rejeter** |
| **A3** | RLS company uniquement si `app.current_company_id` set, sinon org-only | Moins de casse consolidation | Mode « org-only » = trou si bug oublie company header |
| **B** | Pas de RLS company ; tests IDOR uniquement | Moins de risque migration | Contre le choix produit option A |

---

## 6. Plan de migration / rollback (quand approuvé)

1. Migration additive : CREATE FUNCTION + REPLACE policies famille A (ledger financiers).  
2. Ne pas toucher consolidation dans la même migration si possible (famille C ensuite).  
3. Rollback : REVERSE SQL restaurant policies org-only actuelles.  
4. Tests : suite isolation + muhimu_app + ACC-01 + consolidation.  
5. Mesure EXPLAIN sur `ledger_entry` filtrée.

**Non destructif :** pas de DROP TABLE / pas de rewrite data.

---

## 7. Conséquences si on appliquait naïvement `company_id = current_company_id`

- Consolidation cassée (besoin multi-company).  
- `/companies` OK (table company).  
- Oubli de header → 0 ligne ledger (fail-closed) mais UX dégradée.  
- Usurpation SQL du GUC → fuite **si** USING ne vérifie pas CompanyAccess.

---

## 8. Décision demandée

Avant toute migration V3, merci de valider :

1. **A1** (fonctions SECURITY DEFINER `app_user_can_access_company`) comme stratégie.  
2. Périmètre v1 des tables famille A (liste ci-dessus).  
3. Consolidation : politique famille C alignée sur V4 applicatif.

Sans cet accord, **aucune migration V3 ne sera appliquée**.
