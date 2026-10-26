# BETA-DEPLOY-01 — Rapport de mise à jour contrôlée (stack bêta locale)

**Date déploiement :** 2026-10-14 (nuit)  
**Date clôture vérification :** 2026-10-14 (contrôles non destructifs, sans nouvelle migration ni relance des 346 tests)  
**Opérateur :** agent Cursor (lab local)  
**Cible unique :** projet Docker **`muhimu-beta`** (`docker-compose.beta.yml`, `.env.beta`) — **aucun** VPS, **aucune** modification stack **DEV** (`muhimuerp`) ni données DEV  
**Références relues :** `BETA_READINESS_REPORT.md`, `BETA_FEATURE_SCOPE.md`, `BETA_DEPLOYMENT_PLAN.md`, `BETA_SCOPE_IMPLEMENTATION_REPORT.md`, `ACC03_DEV_MIGRATION_REPORT.md`, `PDF_CLAIM_REMEDIATION_REPORT.md`

---

## Verdict final

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | **BETA-DEPLOY-01** : objectifs techniques de déploiement bêta locale **atteints** (preuves §10). **Ouverture testeurs : NO-GO** jusqu’à provisioning + fumée métier + votre autorisation écrite (§13). |

### Preuves principales (instantané clôture)

| # | Preuve | Résultat |
|---|--------|----------|
| P1 | `ledger.0033_acc03_sql_integrity` sur `muhimu_beta` | **Présente** (`django_migrations`) |
| P2 | Triggers ACC-03 | **4/4** actifs |
| P3 | RLS + rôles PG | **Inchangés** (`relrowsecurity=true` ; `muhimu_app` sans BYPASSRLS) |
| P4 | Images bêta API / web / platform | **Rebuild ~7 h** ; conteneurs **Up (healthy)** sur `muhimu-beta-api` / `muhimu-beta-web` / `muhimu-beta-platform-api` |
| P5 | BETA-SCOPE runtime | `DEBUG=False`, `BETA_SCOPE_RESTRICT=True`, toutes features **False** |
| P6 | PDF-CLAIM | Module présent ; titre **`DOCUMENT DE TEST - DONNEES FICTIVES`** |
| P7 | Disponibilité | `GET /api/health` → **200** ; frontend racine → **307** |
| P8 | Données bêta | **0** écriture, **0** orphelin (inchangé vs pré-deploy) |
| P9 | DEV | Stack up ; **0033** sur `muhimu` ; **5** exercices (lecture seule) — non touché par le deploy bêta |
| P10 | Non-régression code (référence produit) | **`Ran 346 tests in 785.789s — OK`** (DEV, exécution isolée retenue ; cf. §11) |

**Interdictions respectées :** pas de déploiement Internet ; pas de `docker prune` / `down -v` ; volumes DEV et bêta conservés ; aucune modification des politiques RLS ; aucun bootstrap démo sur bêta ; aucune charge de jeux fictifs ; aucune déclaration de certification ; **aucune** opération supplémentaire (migrate / restore / deploy) lors de la clôture.

---

## 1. Vérifications préalables (lecture plans + cible)

| Contrôle | Résultat |
|----------|----------|
| Cible = bêta locale uniquement | **OK** — commandes limitées à `-p muhimu-beta` + répétition `muhimu-ops-restore` |
| Images attendues (ACC-02, ACC-03/0033, CLOSE-01, PDF-CLAIM, BETA-SCOPE-01) | **OK** — rebuild **`muhimu-beta-api`** / **`muhimu-beta-web`** / **`muhimu-beta-platform-api`** depuis le dépôt courant |
| `DEBUG=0` / `DJANGO_DEBUG=0` | **OK** (runtime backend bêta) |
| `BETA_SCOPE_RESTRICT=1` | **OK** (`.env.beta`) |
| Aucun `BETA_FEATURES_*=1` | **OK** — features toutes **False** au runtime |
| Fonctions exclues désactivées | **OK** — payload `beta-scope` cohérent |
| Protection API indépendante du frontend | **OK** — garde `require_beta_feature()` sur routes consolidation / class9 / CAGE / ESG / escompte preview |
| Escompte : refus explicite (non silence) | **OK en code** — `require_escompte_allowed_for_entry()` avant `post` / `reverse` ; test `test_post_escompte_entry_forbidden_not_silent` |

---

## 2. Sauvegardes et précontrôles

### 2.1 Sauvegardes réalisées

| Artefact | Chemin | Taille | Vérification |
|----------|--------|--------|--------------|
| Dump PostgreSQL (custom) | `backups/postgres/muhimu_beta_20261014_deploy01.dump` | 233 418 octets | SHA-256 **`8B98DA012A0612EC83CB659645CBC80DC8D29C123EA52E4FF329381D1DE4B32C`** (`*.sha256`) ; `pg_restore -l` **543 entrées TOC**, `dbname: muhimu_beta` |
| Rôles (stub export) | `backups/postgres/muhimu_beta_20261014_deploy01_roles.sql` | — | Copie de référence (restauration complète = dump + rôles si besoin) |
| Médias | `backups/media/muhimu_beta_20261014_deploy01_media.tgz` | 166 923 octets | Archive présente et lisible |
| Config | `.env.beta` | — | **Hors git** — copie manuelle recommandée côté ops (non versionnée) |

**Note :** tentative antérieure `muhimu_beta_20261014_035115.dump` = fichier **vide** (hash SHA-256 de chaîne vide) — **non utilisée** pour le déploiement.

### 2.2 Précontrôles base bêta (lecture seule, avant migrate prod bêta)

| Contrôle | Avant deploy | Après deploy |
|----------|--------------|--------------|
| Migration ledger max | **0032** | **0033_acc03_sql_integrity** |
| Triggers ACC-03 | **0** | **4** (noms conformes au plan) |
| Écritures POSTED | **0** | **0** |
| Lignes orphelines | **0** | **0** |
| RLS `ledger_entry` / `ledger_entryline` / `tenancy_company` | **true** | **inchangé** |
| `muhimu_app.rolbypassrls` | **false** | **false** |

### 2.3 Volumes et stacks

| Volume / stack | Statut |
|----------------|--------|
| `muhimu-beta_postgres_beta_data` | **Préservé** |
| `muhimu-beta_beta_media` / `beta_static` | **Préservés** |
| `muhimuerp_postgres_data` et stack DEV | **Non modifiés** (DEV toujours up, runserver) |
| Autres stacks (frappe, acc03, ops-restore) | **Non impactées** par le `up` bêta |

**Décision préalable :** aucune anomalie bloquante sur intégrité ledger / RLS → poursuite autorisée.

---

## 3. Répétition isolée (restaurabilité)

| Étape | Résultat |
|-------|----------|
| Projet | **`muhimu-ops-restore`** (`docker-compose.ops-restore.yml`, port hôte **5439**) |
| Restauration | Dump **`muhimu_beta_20261014_deploy01`** → base **`muhimu_restore`** |
| Migration | **`ledger.0033_acc03_sql_integrity`** appliquée sur la copie |
| Triggers | **4** présents sur `muhimu_restore` (re-vérifié 2026-10-14) |
| Rollback | Procédure documentée `BETA_DEPLOYMENT_PLAN.md` §10 — restore dump pré-migrate + media ; drill ACC-03 DEV (`ACC03_DEV_MIGRATION_REPORT.md`) comme référence |

**Incident rehearsal :** mot de passe TCP `muhimu` sur le cluster restore — contournement labo via `ALTER USER` en local trust avant migrate one-shot. **N’affecte pas** le cluster bêta production locale.

---

## 4. Mise à jour bêta locale (exécutée)

### 4.1 Configuration

- `.env.beta` : **`BETA_SCOPE_RESTRICT=1`**, **`BOOTSTRAP_LOCAL_ACCOUNTS=0`**, **`DJANGO_DEBUG=0`**
- Aucune variable `BETA_FEATURES_*=1`

### 4.2 Durcissement Compose (bêta uniquement)

Fichier **`docker-compose.beta.yml`** : suppression des substitutions `${POSTGRES_*}` / `${POSTGRES_APP_*}` dans les blocs `environment` de **migrate / backend / platform** — les identifiants proviennent **uniquement** de `.env.beta` (corrige la pollution par variables `POSTGRES_*` du shell Windows hôte, incident ci-dessous).

### 4.3 Images et services

| Service | Image | Action |
|---------|-------|--------|
| backend | `muhimu-beta-api` | Rebuild **no-cache**, redémarrage |
| frontend | `muhimu-beta-web` | Rebuild (correctif TS `beta-scope-gate.tsx`) |
| platform | `muhimu-beta-platform-api` | Rebuild |
| console | `muhimu-beta-console` | **Non rebuild** (image ~4 j ; périmètre BETA-SCOPE principalement ERP) |
| proxy | `nginx:1.27-alpine` | Redémarré avec stack |
| db / redis | inchangés | Volumes **non** recréés |

### 4.4 Migrations

- **`ledger.0033_acc03_sql_integrity`** appliquée sur **`muhimu_beta`**
- Re-vérification post-deploy : **`docker compose … run --rm migrate`** → *No migrations to apply* (service migrate **OK** après durcissement Compose)

### 4.5 Incidents et résolutions

| Incident | Impact | Résolution |
|----------|--------|------------|
| Variables `POSTGRES_*` hôte (ex. `muhimu_acc03`) injectées dans le backend bêta | Backend **unhealthy**, mauvaise base | Nettoyage env hôte + `up` avec `--env-file .env.beta` uniquement ; durcissement compose |
| Échec initial du one-shot migrate (substitution mot de passe / DB) | Migrate compose en échec | Migrate explicite avec `--env-file` ; puis correction compose |
| `depends_on: migrate` bloquant | Services non démarrés | Démarrage **`up -d --no-deps`** backend/platform/frontend après migrate manuel réussi ; état final **healthy** |
| Script bash backup référencé OPS | Non exécutable sur hôte sans bash | Dump via **`docker exec` / `pg_dump`** + `docker cp` |

---

## 5. État runtime post-déploiement

| Indicateur | Valeur |
|------------|--------|
| `DEBUG` | **False** |
| `BETA_SCOPE_RESTRICT` | **True** |
| `BETA_FEATURES` | consolidation / class9_cage / esg / escompte → **False** |
| `pdf_disclaimers.py` | **Présent** ; titre **`DOCUMENT DE TEST - DONNEES FICTIVES`** |
| Proxy | `https://127.0.0.1:18443/api/health` → **200** `{"status":"ok"}` |
| Frontend (racine) | **307** (redirection attendue) |
| `GET /api/ledger/beta-scope` sans session | **401** |
| Données métier | **0** org, **0** société, **0** utilisateur (base vide — charte respectée) |

---

## 6. Tests de fumée (plan §7 — au moment du deploy)

| # | Test | Résultat | Commentaire |
|---|------|----------|-------------|
| 1 | API / frontend disponibles | **OK** | Health 200 ; frontend répond |
| 2 | Auth / logout | **NON EXÉCUTÉ (N/A)** | Aucun compte en base — pas de bootstrap auto |
| 3 | Isolation sociétés | **NON EXÉCUTÉ (N/A)** | Pas de tenants |
| 4 | Saisie + validation | **NON EXÉCUTÉ (N/A)** | Idem |
| 5 | Balance / grand livre | **NON EXÉCUTÉ (N/A)** | Idem |
| 6 | Restrictions UI/API | **PARTIEL** | 401 non auth ; garde-fous **couverture automatisée DEV** (`test_beta_scope`, 13 scénarios dont escompte 403) |
| 7 | PDF + avertissements | **PARTIEL** | Module + titre disclaimer présents en image ; pas de PDF bout-en-bout sans société/exercice |
| 8 | Quatre triggers ACC-03 | **OK** | Requête directe `muhimu_beta` |
| 9 | Rôles PG + RLS | **OK** | Spot-check identique au précontrôle |
| 10 | Absence mutation données inattendue | **OK** | Toujours 0 écritures ; empreinte fonctionnelle vide inchangée |

**Tests automatisés DEV (non-régression déploiement) :**

- Validation produit **BETA-SCOPE-01 : 345 tests OK**.
- Ajout **BETA-DEPLOY-01** : refus escompte explicite + **`test_post_escompte_entry_forbidden_not_silent`** → suite attendue **346** tests.
- **Référence retenue (produit) :** **`Ran 346 tests in 785.789s — OK`** sur DEV (2026-10-14), exécution **isolée** après conflits d’orchestration (§11). **Aucune relance** des 346 tests lors de la clôture BETA-DEPLOY-01.

---

## 7. État DEV vs bêta (instantané post-op)

| Dimension | DEV (`muhimuerp`) | Bêta (`muhimu-beta`) |
|-----------|-------------------|----------------------|
| Code | Volume monté (dev) | Images production rebuild |
| DEBUG | Typ. debug local | **0** |
| Bootstrap démo | Activé (DEV) | **0** |
| Ledger migrate | **0033** (préexistant DEV) | **0033** (appliqué ce deploy) |
| Triggers ACC-03 | 4 | **4** |
| BETA-SCOPE restrict | Typ. off en dev | **on** |
| Données | Jeux locaux | **Vide** (volontaire) |

---

## 8. Retour arrière

| Scénario | Action validée en labo |
|----------|------------------------|
| Échec post-migrate | Restaurer **`muhimu_beta_20261014_deploy01.dump`** + media tgz sur volume bêta **sans** `-v` |
| Bug code | Redéployer tag/image antérieure (conserver SHA pré-deploy) |
| Répétition | Cluster **`muhimu-ops-restore`** conserve une copie migrée pour contrôle |

**Ne pas** improviser de restore destructif sans snapshot ci-dessus.

---

## 9. Synthèse incidents (déploiement)

- Pollution env Windows **`POSTGRES_*`** → mitigée par compose + procédure `--env-file`.  
- Backup bash indisponible → dump manuel Docker.  
- Dump vide **`035115`** → rejeté.  
- Base bêta vide → fumée métier reportée (pas un échec deploy technique).

---

## 10. Clôture vérification (2026-10-14 — non destructif)

Contrôles exécutés **sans** migration, restore, suppression de volume, ni relance de la suite 346.

### 10.1 Sessions de tests / orchestration

| Contrôle | Méthode | Résultat |
|----------|---------|----------|
| Processus `manage.py test` | `docker top` sur conteneurs `muhimu*` | **Aucun** processus de test actif |
| Processus backend DEV | `docker top muhimuerp-backend-1` | **`manage.py runserver` uniquement** (pas de test) |
| Base `test_muhimu` | `pg_database` + `pg_stat_activity` sur cluster DEV | Base **absente** ; **0** session — état cohérent avec destruction post-suite OK (Django) |
| Action corrective | — | **Aucune** terminaison de connexion ni `DROP` (identité non ambiguë : base déjà absente) |

### 10.2 Stack bêta (recontrôle)

| Contrôle | Résultat |
|----------|----------|
| Migration **0033** | **OK** (ligne `0033_acc03_sql_integrity`) |
| **4** triggers ACC-03 | **OK** (noms plan déploiement) |
| RLS `ledger_entry`, `ledger_entryline`, `tenancy_company` | **true** |
| Rôles `muhimu` / `muhimu_app` / `muhimu_platform` | **Inchangés** (`muhimu_app.rolbypassrls = false`) |
| Intégrité données | **0** écriture ; **0** ligne orpheline |
| Runtime Django | `DEBUG=False`, `BETA_SCOPE_RESTRICT=True`, features toutes **False** |
| PDF-CLAIM | Fichier + constante titre disclaimer **OK** |
| API | Health **200** ; `/api/ledger/beta-scope` et `/api/ledger/consolidation` sans auth → **401** (attendu) |
| Frontend BETA-SCOPE + PDF-CLAIM UI | Bundle Next.js contient **`/api/ledger/beta-scope`**, **`isNavPathAllowed`**, bandeau **« Bêta privée — données fictives uniquement »** (grep artefact `.next`, conteneur `muhimu-beta-frontend-1`) |
| Services | 7 conteneurs bêta **Up** ; backend/platform **healthy** |

### 10.3 DEV et autres stacks

| Contrôle | Résultat |
|----------|----------|
| DEV `muhimuerp` | 6 services **Up** ; backend **healthy** ; image dev inchangée (volume monté) |
| DEV DB `muhimu` | **0033** présente ; **5** exercices (non modifié par ce chantier) |
| Volumes Docker | `muhimu-beta_postgres_beta_data`, `muhimuerp_postgres_data`, etc. **présents** (liste `docker volume`) |

---

## 11. Incident orchestration tests DEV (867262 / 867265)

| Exécution | Code sortie | Cause observée | Erreur applicative masquée ? |
|-----------|-------------|----------------|------------------------------|
| 867262 | 1 | `test_muhimu` verrouillée / supprimée par exécution parallèle | **Non** — échec création/recréation **base de test** uniquement |
| 867265 | 1 | Idem (`OperationalError` / `ProgrammingError` sur `test_muhimu`) | **Non** |
| Référence retenue | 0 | **`Ran 346 tests in 785.789s — OK`** (run isolé, post-conflit) | Couvre ACC-02/03, CLOSE-01, PDF-CLAIM, BETA-SCOPE, escompte 403 |

**Conclusion :** conflit **d’orchestration** (sessions PostgreSQL concurrentes sur `test_muhimu`), pas d’indice d’échec de test masqué dans les traces disponibles. La clôture **ne relance pas** la suite (décision produit).

---

## 12. Matrice synthèse (exécuté / réussi / non fait / risques)

| Domaine | Opération exécutée (deploy) | Contrôle réussi (clôture) | Non effectué | Risque résiduel |
|---------|----------------------------|---------------------------|--------------|-----------------|
| Backup bêta | Dump + media + SHA | Fichiers présents sur disque | Copie `.env.beta` archivée ops | Restauration full non rejouée sur bêta live |
| Migrate 0033 bêta | Oui | Reconfirmé SQL | — | Faible |
| Rebuild images | API, web, platform | IDs + conteneurs actifs | Console **non** rebuild | Console hors périmètre ERP si testeurs console |
| BETA-SCOPE API | Déployé | Settings + 401 routes | 403 avec session sur bêta (0 user) | Faible (couvert par tests DEV) |
| BETA-SCOPE UI | Déployé | Preuve bundle `.next` | Navigation manuelle connectée | Moyen jusqu’à provisioning |
| PDF-CLAIM | Déployé | Module + UI bandeau | PDF liasse téléchargé sur bêta | Moyen jusqu’à jeu fictif |
| Fumée auth / métier | — | — | F2–F7 plan §7 | **Bloquant testeurs** (base vide) |
| Tests 346 | 1× OK (référence) | Pas de re-run clôture | — | Faible si référence acceptée |
| DEV / autres stacks | Non touchés | Spot-check OK | Audit exhaustif multi-stack | Faible |

---

## 13. Conditions avant ouverture testeurs (STOP inchangé)

1. **Autorisation écrite** du responsable — **en attente**.  
2. **346/346 OK** — **satisfait** (référence 785,789 s).  
3. **Provisioning** org / sociétés / comptes **fictifs** — **non fait**.  
4. Fumée **F2–F7** sur bêta avec comptes — **non fait**.  
5. Rebuild **console** si périmètre testeurs inclut console — **à décider**.  
6. Charte testeurs (PDF non certifiés, `BETA_FEATURE_SCOPE.md`) — **à communiquer**.

---

**Statut final BETA-DEPLOY-01 : CONDITIONAL GO** (déploiement et contrôles techniques bêta locale **validés**).  
**Ouverture testeurs : STOP — en attente de votre validation explicite.**
