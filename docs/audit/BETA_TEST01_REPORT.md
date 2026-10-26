# BETA-TEST-01 — Données fictives et validation fonctionnelle (bêta locale)

**Date :** 2026-10-14  
**Cible :** stack **`muhimu-beta`** / base **`muhimu_beta`** uniquement  
**Références :** `BETA_DEPLOY01_REPORT.md`, `BETA_FEATURE_SCOPE.md`, `BETA_TEST01_CREDENTIALS.example.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | Jeu fictif provisionné, **17/18 → 18/18** scénarios automatisés OK après ajustement modèle cabinet ; **ouverture testeurs : NO-GO** sans votre autorisation écrite. |

---

## Phase 1 — Inventaire (présenté avant / pendant provisioning)

### Mécanismes existants inspectés

| Mécanisme | Rôle | Usage BETA-TEST-01 |
|-----------|------|---------------------|
| `bootstrap_demo` | Sandbox multi-org (PME + cabinet), comptes `@muhimu.local` si `BOOTSTRAP_LOCAL_ACCOUNTS=1` | **Non utilisé** (bêta : `BOOTSTRAP_LOCAL_ACCOUNTS=0`, risque retrait comptes + pas idempotent cible) |
| `ensure_company_ledger` | PCGO + journaux + exercice civil | **Utilisé** |
| `DemoGrant` | Accès org `is_demo` via ERP | **Ajouté** pour chaque compte test (obligatoire `user_can_access_organization`) |
| RLS A1′ | `bypass_rls()` = no-op ; écritures privilégiées via rôle PG **`muhimu`** | Provisioning / scénarios via **`POSTGRES_APP_USER=$POSTGRES_USER`** (one-shot, documenté) |

### Objets à provisionner (jeu fictif OHADA)

| Objet | Identifiant | Détail |
|-------|-------------|--------|
| Organisation | `slug=beta-test-01`, `setup_data=beta-test-01`, `is_demo=true` | Cabinet fictif (2 dossiers clients PME Congo **CG / XAF**) |
| Société A | **SARL Fleuve Congo** | Dossier principal — opérations 2026 + clôture **2025** |
| Société B | **SARL Niari Logistique** | Dossier isolation (accès restreint) |
| Exercices | 2026 (ops), 2025 (clôture labo) | Par société / société A |
| Journaux | PCGO (`OD`, `AC`, …) | 7 journaux / société |
| Tiers | `CLI-FICT-01`, `FOU-FICT-01` | Clients / fournisseurs fictifs |
| Écritures seed | Vente **1 000 000 XAF** (411/701) ; isolation **250 000 XAF** ; seed clôture 2025 | Idempotent si déjà présentes |
| Comptes test | Voir `BETA_TEST01_CREDENTIALS.example.md` | **Sans mots de passe** dans ce rapport |

### Opérations prévues (scénarios 1–14)

Configuration société (déjà amorcée), plan PCGO, journaux, saisie équilibrée / refus déséquilibre, validation, immutabilité POSTED, grand livre, balance, PDF + disclaimer, permissions rôles, isolation dossiers, API BETA-SCOPE, clôture 2025 (affectation + AN).

### Nettoyage

| Action | Commande | Portée |
|--------|----------|--------|
| Purge sandbox | `python manage.py provision_beta_test01 --confirm-target --purge` (rôle **`muhimu`**) | **Uniquement** org `beta-test-01` (cascade ORM) |
| Restauration complète | `pg_restore` backup pré-test | Volume bêta, sans `-v` |

**Sauvegarde pré-provisioning :** `backups/postgres/muhimu_beta_20261014_test01_pre.dump` (~241 KB) + référence deploy01 `muhimu_beta_20261014_deploy01.dump`.

---

## Phase 2 — Provisioning exécuté

| Élément | Résultat |
|---------|----------|
| Cible confirmée | `muhimu_beta`, 0 org avant → **1 org demo** après |
| Commande | `provision_beta_test01 --confirm-target` |
| Idempotence | `get_or_create` + skip écritures si exercice déjà peuplé |
| RLS | Écritures sous rôle propriétaire PG (pas de changement de politique) |
| DEV | **Non touché** |
| Code ajouté | `apps/identity/beta_test01/*`, commandes `provision_beta_test01`, `run_beta_test01_scenarios` |

**Mot de passe initial :** `BETA_TEST01_DEFAULT_PASSWORD` ou défaut documenté dans la commande — voir fichier credentials **local** (non versionné).

---

## Phase 3 — Scénarios (automatisés)

Exécution : `run_beta_test01_scenarios --confirm-target` (Client Django + services métier).

| ID | Scénario | Attendu | Obtenu | OK |
|----|----------|---------|--------|-----|
| S01 | Org + sociétés | demo, 2 sociétés CG/XAF | 2 sociétés | ✅ |
| S02 | Plan PCGO | >100 comptes | 1396 | ✅ |
| S03 | Journaux | ≥4 | 7 | ✅ |
| S04 | Brouillon équilibré | 2 lignes | 2 | ✅ |
| S05 | Déséquilibre | rejet | HttpError | ✅ |
| S06 | Validation | POSTED | posted | ✅ |
| S07 | POSTED immuable | DELETE → 409 | 409 | ✅ |
| S08 | Grand livre | 200 | 200 | ✅ |
| S09 | Balance | D=C | D=C (mouvements période test) | ✅ |
| S10 | PDF disclaimer | 200 + bannière test | 200 + titre PDF-CLAIM | ✅ |
| S11 | Viewer | post → 403 | 403 | ✅ |
| S12 | Isolation dossiers | owner Niari OK ; isol pas Fleuve | 200 / 403 | ✅ (org **CABINET** + `CompanyAccess`) |
| S13 | BETA-SCOPE API | consolidation 403 ; flags false | 403 + scope | ✅ |
| S14 | Clôture 2025 | CLOSED, net 200 000 XAF | closed (déjà exécuté en run précédent) | ✅ |

**Montants de référence :**

- Vente seed Fleuve : **1 000 000 XAF** (411 / 701).  
- Vente Niari : **250 000 XAF**.  
- Résultat clôture 2025 (seed charges/produits) : **200 000 XAF** bénéfice.  
- Balance période M5 (test +50 000) : mouvements **100 000** D/C (période, pas YTD complet).

---

## Phase 4 — Contrôles sécurité

| ID | Contrôle | Résultat |
|----|----------|----------|
| SEC01 | 4 triggers ACC-03 | ✅ |
| SEC02 | RLS `ledger_entry` | ✅ |
| SEC03 | Escompte POST → 403 | ✅ |
| SEC04 | Pas de `reopen_exercise` (R0+R2) | ✅ |
| — | BETA-SCOPE consolidation / flags | ✅ (S13) |
| — | Exposition Internet | **Non** — proxy localhost **18443** uniquement |
| — | Autres org (future) | Aucune purge hors `beta-test-01` |

---

## Anomalies et limitations

| Item | Gravité | Détail |
|------|---------|--------|
| Org SME vs isolation | **Résolu** | En org **SME**, tous les membres voient toutes les sociétés → bascule **CABINET** fictif pour S12 |
| `bootstrap_demo` | Info | Inadapté bêta (`BOOTSTRAP=0`, multi-org, grants) |
| Scénarios via `testserver` | Info | `ALLOWED_HOSTS` + throttle désactivés **dans la commande** uniquement |
| Balance S9 | Info | Assertion sur **mouvements de période**, pas sur le million seed seul |
| Ouverture testeurs | **Bloquant** | Autorisation écrite + communication credentials + charte PDF |

---

## État stacks

| Stack | État |
|-------|------|
| **muhimu-beta** | Données fictives **beta-test-01** ; services inchangés (rebuild API pour commandes) |
| **muhimuerp (DEV)** | **Inchangé** |
| Migrations / RLS / volumes | **Inchangés** |

---

## Commandes ops (bêta)

```bash
# Provisioning (rôle propriétaire PG)
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta \
  run --rm --no-deps backend sh -c \
  'export POSTGRES_APP_USER=$POSTGRES_USER POSTGRES_APP_PASSWORD=$POSTGRES_PASSWORD; \
   python manage.py provision_beta_test01 --confirm-target'

# Scénarios
docker compose ... run --rm --no-deps backend sh -c '...; python manage.py run_beta_test01_scenarios --confirm-target'

# Purge ciblée
docker compose ... run --rm --no-deps backend sh -c '...; python manage.py provision_beta_test01 --confirm-target --purge'
```

---

**BETA-TEST-01 : CONDITIONAL GO** pour validation labo avec comptes fictifs.  
**Ouverture aux testeurs : STOP — en attente de votre validation explicite.**
