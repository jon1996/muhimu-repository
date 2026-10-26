# SAAS-03 V3 — Revue de sécurité approfondie du design A1

**Document revu :** `SAAS03_V3_RLS_DESIGN.md`  
**Date :** 2026-10-10  
**Périmètre :** analyse uniquement — **aucune migration V3, aucune politique RLS, aucun code métier modifié**  
**Recommandation finale :** **A1 À MODIFIER** (voir §10)

---

## Synthèse exécutive

L’idée A1 (`app_user_can_access_company()` en `SECURITY DEFINER` dérivant l’autorisation de Membership / CompanyAccess) est **la bonne direction** pour une défense en profondeur multi-sociétés **sans** casser consolidation / listes.

Toutefois, le design actuel est **incomplet et partiellement dangereux** s’il est implémenté tel quel, car :

1. L’identité SQL repose sur des **GUC forgeables** par `muhimu_app` (`app.current_user_id`).  
2. Le **bypass RLS est aussi un GUC** (`app.bypass_rls`) que `muhimu_app` peut activer — cela **annule toute la RLS** dès qu’un acteur exécute du SQL sous ce rôle (SQLi, console psql volée, etc.).  
3. Les exigences `SECURITY DEFINER` (`search_path`, `EXECUTE`, owner) ne sont **pas spécifiées** dans le design.  
4. Les politiques SELECT/INSERT/UPDATE/DELETE et l’inventaire exhaustif des tables ne sont qu’esquissés.

**Verdict :** ne pas migrer A1 brut → **A1 durci (A1′)** décrit ci-dessous, puis ré-autorisation avant implémentation.

---

## 1. Identité utilisateur

### 1.1 Comment PostgreSQL « connaît » l’utilisateur ?

**Aujourd’hui (et dans A1 proposé) :**

| Couche | Mécanisme |
|---|---|
| Authentification réelle | Session Django (`SessionAuth`) après login |
| Pont vers PostgreSQL | `TenantMiddleware` → `set_config('app.current_user_id', <uuid>, false)` |
| Lecture SQL | `app_current_user()` = `current_setting('app.current_user_id')::uuid` |

**Preuve code :** `tenancy/middleware.py` L88–95 ; fonctions existantes owner=`muhimu`, **SECURITY INVOKER** (pas DEFINER), sans `search_path` fixé.

PostgreSQL **ne vérifie pas** que cet UUID correspond à une session HTTP. Il croit le GUC.

### 1.2 Vérification de l’identité

| Question | Réponse |
|---|---|
| Le GUC est-il signé / HMAC ? | **Non** |
| Est-il lié au rôle PG de connexion ? | **Non** — même rôle `muhimu_app` pour tous |
| Django re-valide-t-il à chaque requête ? | **Oui** (session cookie) — mais uniquement côté app |
| A1 vérifie-t-il Membership pour le user GUC ? | **Oui** (dans la fonction proposée) — mais sur un user_id **potentiellement forgé** |

### 1.3 Usurpation d’identité via SQL

**Oui, possible** pour tout client connecté en `muhimu_app` :

```sql
SELECT set_config('app.current_user_id', '<uuid-victime>', false);
SELECT set_config('app.current_organization_id', '<org>', false);
-- Puis SELECT sur ledger_* : A1 autoriserait selon les droits de la victime
```

De plus, **pire encore avec le design actuel de bypass** :

```sql
SELECT set_config('app.bypass_rls', 'on', false);
-- Toutes les politiques USING (app_bypass_rls() OR ...) deviennent vraies
```

Ce trou **préexiste** à V3 (toutes les policies org actuelles). A1 **l’hérite** et ne doit pas l’aggraver en le documentant comme « sûr ».

### 1.4 Empêcher les contournements par SQL arbitraire

| Mesure | Effet | Obligatoire pour A1′ |
|---|---|---|
| Supprimer le GUC `app.bypass_rls` | Bypass uniquement via rôle PG `BYPASSRLS` / superuser | **Oui** |
| Rôle plateforme distinct avec `BYPASSRLS` | Staff/console sans GUC forgeable | **Oui** |
| Menace modèle explicite | A1′ = défense contre bugs ORM, **pas** contre compromission de `muhimu_app` | **Oui** |
| Réduire surface SQL (pas de raw SQL user, least privilege) | Limite SQLi | Oui (ops) |
| Rôles PG par utilisateur | Fort mais coût énorme | Hors scope v1 |

**Conclusion identité :** A1 ne peut **pas** promettre « impossible d’usurper via SQL » tant que user_id est un GUC. Il peut promettre : « si le middleware pose le bon user_id, un oubli de filtre `company=` ne fuit plus vers une autre société du même cabinet ».

---

## 2. SECURITY DEFINER

### 2.1 État actuel des fonctions `app_*`

| Fonction | Owner | SECURITY | search_path | EXECUTE |
|---|---|---|---|---|
| `app_bypass_rls` | `muhimu` | **INVOKER** | défaut | non restreint (catalogue) |
| `app_current_org` | `muhimu` | **INVOKER** | défaut | idem |
| `app_current_user` | `muhimu` | **INVOKER** | défaut | idem |

`muhimu` : `rolsuper=t`, `rolbypassrls=t`.  
`muhimu_app` : ni superuser, ni BYPASSRLS.

### 2.2 Exigences manquantes dans le design A1 (à imposer)

Pour **chaque** fonction DEFINER (`app_user_can_access_company`, helpers) :

```sql
CREATE OR REPLACE FUNCTION app_user_can_access_company(p_company_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$ ... $$;

ALTER FUNCTION app_user_can_access_company(uuid) OWNER TO muhimu;
REVOKE ALL ON FUNCTION app_user_can_access_company(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_user_can_access_company(uuid) TO muhimu_app;
-- (et rôle plateforme si besoin)
```

| Contrôle | Pourquoi |
|---|---|
| `SECURITY DEFINER` + owner `muhimu` | Lecture Membership/CompanyAccess sans récursion RLS |
| `SET search_path = pg_catalog, public` | Empêche hijack par objet malveillant dans search_path |
| `REVOKE PUBLIC` / `GRANT` ciblé | Limite qui peut appeler la fonction |
| Corps SQL figé, pas de dynamique | Pas d’injection dans la fonction |
| **Ne pas** honorer `app.bypass_rls` GUC dans la fonction | Voir §2.4 |

### 2.3 Contournement involontaire d’autres politiques RLS

Oui, risque structurel : DEFINER owner=`muhimu` (BYPASSRLS) **lit** `tenancy_membership` / `tenancy_companyaccess` / `tenancy_company` en ignorant leur RLS.

C’est **nécessaire** pour éviter la récursion, mais :

- La fonction ne doit **retourner qu’un booléen** (ou des UUID autorisés), jamais exposer des lignes riches.  
- Pas de fonction DEFINER générique type `run_as_admin(sql)`.  
- Tests : s’assurer qu’un appel direct ne dump pas d’autres tables.

### 2.4 Interaction fatale avec `app_bypass_rls()` GUC

Le design A1 step 1 dit : `app_bypass_rls() → true`.  
Si cela reste basé sur le GUC, **toute la chaîne A1 est inutile** face à `set_config('app.bypass_rls','on')`.

**Modification obligatoire (A1′) :**

- Retirer le GUC bypass des politiques runtime ERP.  
- Bypass = connexion sous un rôle PostgreSQL ayant `BYPASSRLS` (ex. `muhimu_platform` pour la console, `muhimu` pour migrate).  
- `muhimu_app` : **jamais** de bypass, ni GUC ni attribut.

---

## 3. Permissions des entreprises

### 3.1 Matrice cible (alignée Django actuel + A1′)

| Cas | Règle SQL dans `app_user_can_access_company(cid)` |
|---|---|
| Pas de `app_current_user()` | **false** (fail closed) |
| Company inexistante / inactive | **false** |
| Pas de membership actif `(user, company.org)` | **false** |
| `app_current_org()` posé et ≠ `company.organization_id` | **false** (préserve isolation org) |
| Rôle membership `owner` / `admin` | **true** |
| Org type `sme` | **true** (toutes sociétés de l’org) |
| Org type `cabinet` | **true** ssi `CompanyAccess(user, company)` |
| Révocation Access | **immédiat** à la TX suivante (plus de ligne Access → false) |

### 3.2 Accès multi-sociétés

A1′ **autorise** naturellement plusieurs sociétés (pas de contrainte `company_id = current_company_id` en USING).  
Consolidation / liste companies restent possibles.

### 3.3 Usurpation header HTTP `X-Company-Id`

Middleware Django refuse déjà si `user_can_access_company` est faux.  
Avec A1′ USING basé sur Access/rôle (pas sur le GUC company), un header forgé **ne suffit pas** en SQL pour lire une société non autorisée — **tant que** `current_user_id` n’est pas forgé.

---

## 4. Intégration Django

### 4.1 Par requête / transaction

| Sujet | État actuel | Exigence A1′ |
|---|---|---|
| Init contexte | Middleware après auth | Inchangé : user → org → company (app) |
| Clear | `finally` clear GUCs | Conserver ; ajouter clear company GUC si introduit |
| `CONN_MAX_AGE` | `0` | **Conserver** (critique) |
| `ATOMIC_REQUESTS` | `False` | OK ; posting utilise `@transaction.atomic` |
| GUC `is_local` | `set_config(..., false)` = session-level | Préférer `true` (transaction-local) **dans** `atomic` si on unifie — sinon clear `finally` obligatoire |

**Recommandation A1′ :** passer les `set_config` critiques en **`is_local=true`** lorsque la vue est dans une transaction, **ou** documenter que `CONN_MAX_AGE=0` + clear `finally` est le contrat non négociable.

### 4.2 Tâches asynchrones / management

| Canal | Risque | Contrat A1′ |
|---|---|---|
| Celery (futur) | Worker sans GUC → 0 ligne ou mauvais user | Helper obligatoire `bind_tenant(user_id, org_id)` ; fail closed |
| `bootstrap_demo`, migrate | Doit tout voir | Rôle `muhimu` (déjà privilégié) |
| `runserver`/`gunicorn` ERP | `muhimu_app` | Jamais bypass GUC |
| Console platform | Staff | Rôle PG `muhimu_platform` **BYPASSRLS** (changement Django settings APP_ROLE) — **changement d’archi à valider** |

### 4.3 Compatibilité transactions atomiques (ACC-01)

`select_for_update` période + `F()` snapshots restent valides.  
RLS company n’empêche pas le verrou si le user a accès à la société de l’écriture.  
**Risque :** double contrôle Access à chaque ligne — perf ; index `(company_id)`, `(user_id, company_id)` sur CompanyAccess.

---

## 5. Politiques RLS

### 5.1 Inventaire exhaustif proposé

#### Famille A — société stricte (`company_id` NOT NULL)

Politique unique (remplace org-only) :

```text
USING  (app_user_can_access_company(company_id))
WITH CHECK (app_user_can_access_company(company_id))
```

Tables :

1. `ledger_account`  
2. `ledger_accountingperiod`  
3. `ledger_balancesnapshot`  
4. `ledger_bankstatement`  
5. `ledger_bankstatementline`  
6. `ledger_cagereflection`  
7. `ledger_cagesection`  
8. `ledger_cashcount`  
9. `ledger_commitment`  
10. `ledger_depreciationcharge`  
11. `ledger_entry`  
12. `ledger_entryline`  
13. `ledger_esgreport`  
14. `ledger_exercise`  
15. `ledger_fixedasset`  
16. `ledger_fxrate`  
17. `ledger_inventorycampaign`  
18. `ledger_inventoryline`  
19. `ledger_journal`  
20. `ledger_journalsequence`  
21. `ledger_sourcedocument`  
22. `ledger_thirdparty`  
23. `tenancy_companyofficer` (déjà org ; renforcer company)

#### Famille B — référentiel org / multi-sociétés

| Table | USING proposé |
|---|---|
| `tenancy_company` | membership actif sur org **et** (admin/SME **ou** Access **ou** liste) — aligné `companies_queryset_for` |
| `tenancy_companyaccess` | admin org **ou** sa propre ligne (`user_id = app_current_user()`) |

#### Famille C — consolidation (phase 2 migration)

| Table | USING proposé |
|---|---|
| `ledger_consolidationgroup` | admin org **ou** toutes les sociétés membres accessibles (sous-requête) |
| `ledger_consolidationmember` | idem via group |
| `ledger_consolidationelimination` | idem via group |

**Ne pas** livrer famille A sans décision explicite sur C (sinon consolidation owner OK via admin ; accountant limité déjà filtré V4 app).

### 5.2 SELECT / INSERT / UPDATE / DELETE

Une seule policy PostgreSQL couvre les 4 commandes si USING + WITH CHECK sont définis (comportement PG).  
Pour INSERT ledger : WITH CHECK `app_user_can_access_company(company_id)` empêche d’écrire sous une société non autorisée même si l’ORM se trompe de `company_id`.

### 5.3 Récursion

Évitée si DEFINER lit tenancy en tant que `muhimu` (BYPASSRLS).  
**Interdit :** policy sur membership qui appelle `app_user_can_access_company` qui relit membership sous INVOKER.

### 5.4 Fail closed / isolation org

- User NULL → false.  
- Org GUC posé et ≠ company.org → false (**renforce** l’isolation org, à conserver).  
- Sans org GUC mais membership valide : design A1 original permettait l’accès ; **A1′ recommandé : exiger org GUC pour famille A** (fail closed plus strict, cohérent avec API `require_company` / headers).

---

## 6. Compatibilité comptable

| Domaine | Impact A1′ | Action de validation |
|---|---|---|
| Posting / ACC-01 | OK si user a Access sur la société | Rejouer tests concurrence |
| Clôture / opening | OK (même company) | `test_opening`, `test_closing` |
| Balance / GL / PDF | OK | isolation + pdf tests |
| Consolidation autorisée | OK multi-company via Access/admin | tests V4 |
| Consolidation refusée | DB + app | tests 403 |
| Cage reflect / FX auto | Poste sous même company | tests cage/fx |
| Commandes bootstrap | Rôle `muhimu` | smoke bootstrap |

**Risque de verrouillage légitime :** membership inactif, oubli CompanyAccess, org header manquant si A1′ exige org GUC.

---

## 7. Migration et rollback

### 7.1 Préconditions

1. V1/V2/V4 déjà en place (fait).  
2. Accord écrit sur A1′ (ce document).  
3. Décider : suppression GUC bypass + rôle `muhimu_platform` (changement settings).  
4. Fenêtre maintenance courte (REWRITE policies = locks ACCESS EXCLUSIVE brefs sur ALTER POLICY).  
5. Backup DB + drill restore (OPS-01).

### 7.2 Migration non destructive (esquissée, **non appliquée**)

Ordre :

1. Créer fonctions DEFINER durcies.  
2. Remplacer policies famille A (DROP POLICY + CREATE).  
3. Ajuster `tenancy_company` / access (famille B).  
4. (Option) famille C consolidation.  
5. Migrer console vers rôle BYPASSRLS ; retirer GUC bypass du middleware ERP.

Rollback REVERSE : recréer policies `organization_id = app_current_org()` actuelles + DROP nouvelles fonctions.

### 7.3 Risques de lock-out

| Scénario | Symptôme | Mitigation |
|---|---|---|
| Fonction bugée → toujours false | API vide 404/listes vides | Rollback migration ; feature flag SQL |
| Org GUC non posé | Fail closed | Middleware inchangé doit poser org |
| Platform sans nouveau rôle | Console cassée | Migrer settings avant cutover policies |
| Perf EXISTS | Timeouts | Index Access ; EXPLAIN avant prod |

---

## 8. Design SQL détaillé proposé (A1′ — à valider, non appliqué)

```sql
-- Identité : toujours INVOKER, lecture GUC (menace modèle documentée)
-- Bypass : SUPPRIMÉ en GUC pour muhimu_app

CREATE OR REPLACE FUNCTION app_user_can_access_company(p_company_id uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_user uuid := app_current_user();
  v_org  uuid := app_current_org();
  v_company_org uuid;
  v_company_active boolean;
  v_role text;
  v_org_type text;
BEGIN
  IF p_company_id IS NULL OR v_user IS NULL OR v_org IS NULL THEN
    RETURN false;
  END IF;

  SELECT c.organization_id, c.is_active
    INTO v_company_org, v_company_active
  FROM tenancy_company c
  WHERE c.id = p_company_id;

  IF NOT FOUND OR v_company_active IS NOT TRUE THEN
    RETURN false;
  END IF;

  IF v_company_org <> v_org THEN
    RETURN false;  -- isolation organisationnelle
  END IF;

  SELECT m.role, o.type
    INTO v_role, v_org_type
  FROM tenancy_membership m
  JOIN tenancy_organization o ON o.id = m.organization_id
  WHERE m.organization_id = v_org
    AND m.user_id = v_user
    AND m.is_active IS TRUE;

  IF NOT FOUND THEN
    RETURN false;
  END IF;

  IF v_role IN ('owner', 'admin') THEN
    RETURN true;
  END IF;

  IF v_org_type = 'sme' THEN
    RETURN true;
  END IF;

  RETURN EXISTS (
    SELECT 1 FROM tenancy_companyaccess a
    WHERE a.company_id = p_company_id
      AND a.user_id = v_user
      AND a.organization_id = v_org
  );
END;
$$;

REVOKE ALL ON FUNCTION app_user_can_access_company(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_user_can_access_company(uuid) TO muhimu_app;
```

Exemple policy famille A :

```sql
DROP POLICY IF EXISTS ledger_entry_isolation ON ledger_entry;
CREATE POLICY ledger_entry_isolation ON ledger_entry
  FOR ALL
  USING (app_user_can_access_company(company_id))
  WITH CHECK (app_user_can_access_company(company_id));
```

---

## 9. Changements Django nécessaires (A1′ — non appliqués)

| Changement | Pourquoi |
|---|---|
| Retirer `set_config('app.bypass_rls', ...)` du middleware ERP | Fermer le bypass forgeable |
| Introduire rôle PG `muhimu_platform` (BYPASSRLS) pour `APP_ROLE=platform` | Console staff |
| Helper `bind_tenant_context` / `clear_tenant_context` unique | Celery + commandes |
| Ne **pas** s’appuyer sur `app.current_company_id` pour USING | Déjà dans A1 ; confirmer |
| Tests muhimu_app : usurpation user_id, bypass GUC absent, Access révoqué, PME, cabinet, consolidation | Matrice §11 |

---

## 10. Rôles et privilèges PostgreSQL

| Rôle | Login | BYPASSRLS | Usage |
|---|---|---|---|
| `muhimu` | oui | oui (superuser) | migrate, bootstrap |
| `muhimu_app` | oui | **non** | API ERP runtime |
| `muhimu_platform` (**nouveau**, recommandé) | oui | **oui** (sans superuser si possible) | Console staff |

Privilèges `muhimu_app` : DML tables app + `EXECUTE` sur fonctions `app_*` nécessaires.  
**Pas** de `BYPASSRLS`. **Pas** de capacité à « devenir » un autre rôle.

---

## 11. Scénarios de tests de sécurité (à exécuter après implémentation)

| ID | Scénario | Attendu |
|---|---|---|
| S1 | `muhimu_app`, user A, org A, SELECT entries B | 0 |
| S2 | Comptable cabinet, Access C1 only, SELECT C2 | 0 |
| S3 | Après DELETE Access, SELECT C1 | 0 |
| S4 | PME member, SELECT toutes societies org | >0 autorisées |
| S5 | `set_config bypass on` **si retiré** | sans effet / impossible |
| S6 | `set_config user_id=victime` | **documenté** : accès victime si SQLi (limite modèle) |
| S7 | INSERT entry company non autorisée | rejet WITH CHECK |
| S8 | Consolidation groupe C1+C2 en accountant C1 | refus app + idéalement DB |
| S9 | Owner consolidation multi | OK |
| S10 | ACC-01 concurrence | OK |
| S11 | Opening / close / PDF | OK |
| S12 | Connexion sans user/org GUC | 0 lignes famille A |

---

## 12. Alternatives à A1

| Option | Verdict revue |
|---|---|
| **A1 brut** (design actuel) | **À rejeter tel quel** (bypass GUC + DEFINER non durci) |
| **A1′ durci** (ce document) | **Retenir** sous réserve validation produit |
| **A2** liste companies en GUC | **Rejeter** (forgeable) |
| **A3** company GUC optionnel sinon org | **Rejeter** pour bêta (trou si header oublié) |
| **B** pas de RLS company | Acceptable seulement si V3 abandonné volontairement |
| **Rôles PG par tenant** | Plus fort, coût ops prohibitif pour v1 |

---

## 13. Risques résiduels même avec A1′

1. Compromission du rôle `muhimu_app` + forgery de `current_user_id` → accès aux données de la victime.  
2. Staff / rôle platform BYPASSRLS mal gouverné.  
3. Perf des EXISTS sous charge (à mesurer).  
4. Décalage temporaire app V4 vs policy consolidation famille C si phase 2 retardée.  
5. Celery mal câblé → déni de service (0 ligne) plutôt que fuite (fail closed).

---

## 14. Recommandation argumentée

# **A1 À MODIFIER**

**Pourquoi pas APPROUVABLE tel quel**

- Bypass RLS via GUC rend A1 cosmétique contre un acteur SQL.  
- DEFINER sans `search_path` / `REVOKE EXECUTE` / menace modèle = dette sécurité.  
- Inventaire et policies INSERT/UPDATE/DELETE insuffisamment figés.

**Pourquoi pas À REJETER**

- La dérivation d’autorisation depuis Membership/CompanyAccess en base est correcte.  
- Évite l’écueil `current_company_id` seul.  
- Compatible multi-sociétés, PME, cabinets, consolidation.

**Conditions pour passer à APPROUVABLE (A1′)**

1. Supprimer le bypass GUC ; rôles PG distincts.  
2. Spécifier DEFINER durci (`search_path`, EXECUTE, owner).  
3. Exiger `app_current_org()` + membership actif dans la fonction.  
4. Figurer l’inventaire famille A (+ décision B/C).  
5. Documenter explicitement le **modèle de menace** (défense ORM ≠ anti-SQLi total).  
6. Plan de tests S1–S12 + rollback.

---

**Aucune migration V3 n’a été appliquée. Aucun code métier modifié.**

En attente de votre décision :  
- valider **A1′** pour implémentation, ou  
- demander une autre orientation (B, etc.).
