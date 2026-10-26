# BETA-FINAL-READINESS-01 — État de la bêta avant décision d’ouverture testeurs

**Date :** 2026-10-15  
**Périmètre :** stack locale **`muhimu-beta`** uniquement  
**Références :** `SEC_SESSION01_BETA_DEPLOY_REPORT.md`, `BETA_UAT02_REPORT.md`, `SEC_SESSION01_REPORT.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO (préparation)** | Bêta **techniquement saine** (données fictives, ACC-03, BETA-SCOPE, sessions, PDF). **Ouverture testeurs externes : NO-GO** tant que les conditions obligatoires §6 ne sont pas remplies et sans votre **GO écrit**. |

---

## 1. Anomalie `run_beta_test01_scenarios` / RLS

### Symptôme

Sous le runtime bêta (`POSTGRES_APP_USER=muhimu_app`), la commande échoue avec :

`Organization.DoesNotExist` pour `slug=beta-test-01`, alors que l’org existe (visible en SQL owner `muhimu`).

### Cause racine (confirmée)

| Facteur | Détail |
|---------|--------|
| **Rôle PostgreSQL** | Le backend bêta utilise **`muhimu_app`** (NOBYPASSRLS) — comportement **attendu** en production. |
| **Politique `tenancy_organization`** | Visible si `app.current_user_id` correspond à un **membership actif**, ou si `id = app.current_organization_id` (migration `0010_rls_organization_membership`). |
| **Commandes Django** | **Ne passent pas** par `TenantMiddleware` : les GUC `app.current_user_id` / `app.current_organization_id` restent **vides** par défaut. |
| **Runner** | `_org_company()` appelait `Organization.objects.get(slug=…)` **avant** toute requête HTTP → ORM filtré à **zé ligne**. |
| **Requêtes HTTP** | Login + en-têtes `X-Organization-Slug` / `X-Company-Id` → middleware pose le contexte → ORM et API **OK** (preuves post SEC-SESSION-01). |
| **Provisioning** | `provision_beta_test01` s’exécutait historiquement sous rôle **owner** (`muhimu`) — masquait l’écart runner / runtime. |

**Ce n’est pas** un défaut de provisioning ni une perte de données ; c’est un **écart de contexte tenant** entre management commands et pipeline HTTP.

### Correction proposée (dépôt — sans changer les policies RLS)

Fichiers ajoutés / modifiés :

| Fichier | Rôle |
|---------|------|
| `apps/identity/beta_test01/runner_rls.py` | `tenant_context(user_id=owner, organization_id=…)` — **même mécanisme** que le middleware, sans BYPASSRLS |
| `apps/identity/beta_test01/scenarios.py` | `_org_company()` délégué à `org_and_companies_for_runner()` |
| `apps/identity/beta_test01/uat_probe.py` | Idem pour sondes read-only |

**Non fait dans cette phase :** rebuild image **`muhimu-beta-api`** → le conteneur bêta **en cours** n’embarque pas encore ce patch ; `run_beta_uat01_probes` y échoue encore avec l’ancien code. **Aucun contournement** par rôle `muhimu` n’a été utilisé.

**Validation recommandée (sur votre GO) :** rebuild ciblé API bêta + `run_beta_uat01_probes --confirm-target` (read-only) ; **ne pas** relancer les 18 scénarios mutants sans décision explicite.

---

## 2. Données comptables (lecture seule — SQL owner + API `muhimu_app`)

### Organisation / sociétés

| Élément | Valeur |
|---------|--------|
| Org | `beta-test-01`, type **cabinet**, `is_demo=true`, `setup_data=beta-test-01` |
| Sociétés | **SARL Fleuve Congo**, **SARL Niari Logistique** — XAF, régime **normal** |

### Exercices

| Société | Année | Statut | Clôture |
|---------|-------|--------|---------|
| Fleuve | **2025** | **closed** | `closed_on=2026-10-14` |
| Fleuve | **2026** | open | — |
| Niari | **2026** | open | — |

*(Niari : pas d’exercice 2025 en base — attendu si périmètre demo limité à 2026.)*

### Écritures et équilibre (lignes)

| Société | Statut | Écritures (lignes) | Σ débit | Σ crédit |
|---------|--------|-------------------|---------|----------|
| Fleuve | posted | 31 | 123 000 000 | 123 000 000 |
| Fleuve | draft | 16 | 8 000 | 8 000 |
| Niari | posted | 2 | 250 000 | 250 000 |

### ACC-03

**4/4** triggers actifs :

- `trg_ledger_entry_forbid_posted_mutation`
- `trg_ledger_entryline_forbid_posted_substance`
- `trg_ledger_entry_posted_balance`
- `trg_ledger_entryline_balanced_deferred`

### BETA-SCOPE & PDF (API authentifiée owner, read-only)

| Contrôle | Résultat |
|----------|----------|
| `GET /api/ledger/beta-scope` | `restrict_mode=true`, features **false** |
| `GET /api/ledger/consolidation` | **403** |
| `GET /api/ledger/books/pdf?kind=balance` | **200** `application/pdf`, mention **« DOCUMENT DE TEST » / DONNEES FICTIVES** présente |
| `GET /api/ledger/balance` | **200** (2 lignes) — contrôle post-deploy SEC-SESSION-01 |

**Non exécuté :** `run_beta_test01_scenarios` (écritures) — conformément à votre consigne.

---

## 3. Sessions — contrôles exécutés vs automatisés

| Exigence | Exécuté sur bêta live | Couverture automatisée DEV |
|----------|----------------------|----------------------------|
| Idle **30 min** (paramètre) | **OK** — settings conteneur `1800` | `test_session_policy` |
| Absolu **12 h** | **OK** — `43200` | `test_session_policy` |
| Logout invalide session | **OK** — API shell | `test_logout_*` |
| Cookie sécurisé | **OK** — `SESSION_COOKIE_SECURE=True`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=True` | settings tests |
| CSRF | **OK** — mutations via jeton ; login/logout testés | suite identity |
| Pas de prolongation polling | **OK** — `/api/auth/me` no-touch (smoke) | `test_auth_me_does_not_refresh_idle`, header background |
| Multi-onglet après idle | **OK** — simulation +1900 s → **401 idle** | `test_second_tab_*` |
| Front post-expiration | **Code déployé** (`SessionGuard`, purge cache) | — **validation navigateur manuelle restante** |
| Saisies non enregistrées | **Infra** (`UnsavedWorkProvider`) | — **câblage écrans partiel** |

---

## 4. Accès externes — comparaison (sans déploiement)

### A. Laboratoire local privé (`127.0.0.1:18443`, cert self-signed)

| Dimension | Évaluation |
|-----------|------------|
| **Sécurité réseau** | Forte **si** loopback / VPN site-à-site ; **inadapté** à des experts **à distance** sans tunnel |
| **HTTPS / certificats** | Self-signed (`erp.beta.localhost`) — friction onboarding, pas de confiance publique |
| **MFA admin** | Non intégré ERP ; console séparée — à renforcer ops |
| **Comptes** | `BETA_TEST01_*` + rotation manuelle ; pas de self-service |
| **Sauvegardes** | Dumps locaux (`muhimu_beta_*`, `sec_session01_pre`) — **ops manuelle** |
| **Supervision** | Logs conteneurs / Django — pas de SIEM |
| **Coûts** | Faible (matériel existant) |
| **Risques** | Machine hôte = SPOF ; fuite cert/password ; pas de SLA |

### B. Bêta distante dédiée (VPS isolé, séparée DEV et prod future)

| Dimension | Évaluation |
|-----------|------------|
| **Sécurité réseau** | VPC / firewall, **pas** d’exposition PostgreSQL ; accès **VPN** (WireGuard/Tailscale) ou **IP allowlist** + WAF léger |
| **HTTPS / certificats** | **Let’s Encrypt** ou cert org sur FQDN dédié (`beta.muhimu…`) |
| **MFA admin** | MFA sur console hébergeur + comptes staff ; accès SSH clés |
| **Comptes** | Provisioning contrôlé, rotation, révocation centralisée |
| **Sauvegardes** | Snapshots DB chiffrés, rétention documentée, test restore |
| **Supervision** | Healthchecks, alertes disque/CPU, agrégation logs |
| **Coûts** | VPS + temps ops (modeste pour petit panel) |
| **Risques** | Surface Internet si mal configuré ; coût erreur config |

### Recommandation (petit groupe d’experts-comptables distants)

**Privilégier B** : environnement **dédié**, reachable via **VPN zero-trust** ou bastion, TLS public sur reverse proxy, **jamais** le labo loopback local comme cible principale.  
**A** reste utile pour **UAT interne** sur poste dev, pas pour testeurs externes répartis géographiquement.

---

## 5. État réel de la bêta (synthèse)

| Domaine | État |
|---------|------|
| Stack | `muhimu-beta` healthy (proxy loopback, SEC-SESSION-01 actif) |
| Données fictives | Intègres, équilibre posted OK |
| RLS / rôles PG | Inchangés (`muhimu_app` runtime) |
| Runner métier | **Patch RLS prêt dans le dépôt** ; **image bêta à rebuild** pour validation commande |
| Testeurs | **NO-GO** |

---

## 6. Conditions obligatoires avant ouverture testeurs

1. **GO écrit** explicite ouverture testeurs (hors scope technique seul).  
2. **Rebuild** `muhimu-beta-api` avec `runner_rls.py` + **`run_beta_uat01_probes --confirm-target` OK** sur bêta.  
3. **Checklist navigateur** session (idle message, logout multi-onglet, login après expiration) — `UAT_NAVIGATEUR_CHECKLIST.md`.  
4. **Architecture d’accès B** (VPN + HTTPS + distribution credentials hors Git).  
5. **Procédure incident** (restore dump, contact ops, pas de données réelles).  
6. **Charte testeur** : données fictives, PDF non certifiés, pas de production client.  
7. **Rate-limit login** Redis vérifié sous charge légère (optionnel mais recommandé).

---

## 7. Risques résiduels

| ID | Risque | Gravité |
|----|--------|---------|
| R1 | Runner non validé sur image bêta courante | Moyen |
| R2 | SessionGuard / unsaved work non audités navigateur | Moyen |
| R3 | Accès local loopback inadapté aux testeurs distants | Élevé si option A seule |
| R4 | Self-signed TLS friction / erreurs utilisateur | Faible–moyen |
| R5 | Brouillons draft Fleuve (16 lignes) — bruit demo | Faible |

---

## Restrictions respectées

Aucun déploiement distant, ouverture testeurs, migration, changement RLS/SYSCOHADA, mutation comptable, prune, modification stack DEV, scénarios écrivants relancés.

---

**BETA-FINAL-READINESS-01 : CONDITIONAL GO (préparation).**  
**Testeurs externes : NO-GO — en attente de votre autorisation écrite et des conditions §6.**
