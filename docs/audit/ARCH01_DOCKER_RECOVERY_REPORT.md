# ARCH-01 — Rapport restauration contrôlée stack DEV

**Date :** 2026-10-10  
**Périmètre :** stack `muhimuerp` uniquement (pas Frappe, pas bêta)  
**Aucun prune, aucun `-v`, aucun build, aucun déploiement**

---

## Phase 1 — Identification

| Élément | Valeur |
|---|---|
| Compose | `d:\muhimu\muhimu ERP\docker-compose.yml` |
| Projet Docker | `muhimuerp` |
| Services | `db`, `redis`, `backend`, `frontend`, `platform`, `console` |
| Volume PG | `postgres_data` → **`muhimuerp_postgres_data`** (existant, non recréé) |
| DB attendue | `muhimu` (POSTGRES_DB) |
| `.env` | présent (DEBUG=1, BOOTSTRAP_LOCAL_ACCOUNTS=1) |

### Point bloquant — backend (résolu option B)

La commande d’origine du conteneur incluait `migrate && bootstrap_demo`.  
**Option B autorisée** : override temporaire `docker-compose.runserver-only.yml` (Compose principal inchangé).

---

## Phase 2 — Conteneurs

| Conteneur | Statut |
|---|---|
| `muhimuerp-db-1` | **Up (healthy)** — postgres:16-alpine, port 5433 |
| `muhimuerp-redis-1` | **Up (healthy)** — redis:7-alpine, port 6379 |
| `muhimuerp-backend-1` | **Up (healthy)** — `runserver` seul (override) |
| `muhimuerp-frontend-1` | **Up** — Next.js :3001 |
| `muhimuerp-console-1` | **Up** — Next.js :3002 |
| `muhimuerp-platform-1` | **Up (healthy)** — `runserver`, rôle `muhimu_platform` |

Stack Frappe : non touchée.

---

## Phase 3 — PostgreSQL (lecture seule)

| Contrôle | Résultat |
|---|---|
| Healthy | **oui** |
| Version | **16.15** |
| Bases | `muhimu`, `postgres`, `test_muhimu` |
| Tables public | **42** |
| Tables clés | organization, company, membership, ledger_entry **présentes** |
| Organisations | demo-cabinet, demo-pme, muhimu, sarl-test-identite (4) |
| Sociétés | 5 (Alpha, Beta, Horizon, muhimu technologi, SARL Test Identité) |
| Écritures | 10 |
| Users | 3 |
| Rôle `muhimu_app` | NOSUPERUSER, **NOBYPASSRLS**, login |
| Rôle `muhimu_platform` | NOSUPERUSER, **BYPASSRLS**, login |
| Politiques RLS | **32** tables FORCE RLS |
| `app_bypass_rls()` | **false** |
| `app_user_can_access_company` | présente |

**Données intactes** — aucune écriture SQL effectuée.

---

## Phase 4 — Application (option B)

### Commandes exécutées

```bash
# 1) Override temporaire créé : docker-compose.runserver-only.yml
#    command: python manage.py runserver 0.0.0.0:8000

# 2) Démarrage backend uniquement (recréation conteneur, pas de volume, pas de build)
docker compose -p muhimuerp \
  -f docker-compose.yml \
  -f docker-compose.runserver-only.yml \
  up -d --no-build backend
```

### Résultats

| Contrôle | Résultat |
|---|---|
| Cmd conteneur | `["python","manage.py","runserver","0.0.0.0:8000"]` |
| `/api/health` | **200** `{"status":"ok"}` |
| DEBUG | True (dev) |
| DB user runtime | **`muhimu_app`** (NOSUPERUSER, NOBYPASSRLS) |
| DB name | `muhimu` |
| `CONN_MAX_AGE` | 0 |
| Migrations non appliquées | **Aucune** (toutes `[X]`, y compris A1′ 0011/0032/0003) |
| Orgs visibles sans GUC tenant | **0** (fail closed RLS — attendu) |
| `app_bypass_rls()` | false |
| Logs | runserver OK, health 200, pas d’erreur critique |
| migrate / bootstrap | **Non exécutés** |

---

## Phase 4b — Frontend + console (restauration)

### Inspection préalable

| Service | Image | Commande | Ports | Volumes | Init data ? |
|---|---|---|---|---|---|
| frontend | `muhimu-erp-web` | `npm install && npm run dev …` | 3001→3000 | bind `./frontend` + `muhimuerp_frontend_node_modules` | Non (pas migrate/bootstrap) |
| console | `muhimu-platform-web` | `npm install && npm run dev …` | 3002→3000 | bind `./console` + `muhimuerp_console_node_modules` | Non |
| platform | `muhimu-platform-api` | `runserver` seul | 8002→8000 | bind `./backend` | **Non démarré** (inspection seule) |

### Commandes exécutées

```bash
docker compose -p muhimuerp -f docker-compose.yml up -d --no-build --no-recreate --no-deps frontend
docker compose -p muhimuerp -f docker-compose.yml up -d --no-build --no-recreate --no-deps console
# --no-deps : ne démarre PAS platform (console dépendrait sinon de platform healthy)
```

### Résultats HTTP

| URL | Résultat |
|---|---|
| `http://127.0.0.1:3001/` | **200** (via redirect login) |
| `http://127.0.0.1:3001/api/health` | **200** `{"status":"ok"}` (rewrite → backend) |
| `http://127.0.0.1:3002/` | **200** (console UI) |
| `http://127.0.0.1:3002/api/health` | **500** — attendu : `API_INTERNAL_URL=http://platform:8000` et platform **arrêté** |

### Logs
- Frontend : Next.js Ready, `GET /login 200`, pas d’erreur critique.  
- Console : Next.js Ready, `GET /console 200`, pas d’erreur critique.

### État volumes
- `muhimuerp_postgres_data` : intact (non touché)  
- `muhimuerp_frontend_node_modules` / `console_node_modules` : réutilisés (`npm install` au start, sans rebuild image)

---

## Phase 4c — Platform (inspection puis démarrage autorisé)

### Inspection préalable (avant démarrage)

| Élément | Valeur |
|---|---|
| Statut pré-démarrage | **Exited** (volontaire) |
| Commande | `python manage.py runserver 0.0.0.0:8000` — **pas** de migrate/bootstrap dans la CMD |
| `APP_ROLE` | `platform` |
| Rôle PG runtime (settings) | si non-privilégié + `APP_ROLE=platform` → **`POSTGRES_PLATFORM_USER` (`muhimu_platform`)** |
| ERP (`APP_ROLE=erp`) | **`muhimu_app`** — connexion séparée, pas de BYPASSRLS |
| `muhimu_platform` | NOSUPERUSER, **BYPASSRLS** (console staff) |
| Env `BOOTSTRAP_LOCAL_ACCOUNTS` | présent dans compose, **non exécuté** tant que `bootstrap_demo` n’est pas lancé |
| Dépendances compose | backend healthy + db healthy (déjà OK) |

### Séparation ERP / platform
- Requêtes ERP ordinaires → conteneur `backend` → rôle **`muhimu_app`**.  
- Console SaaS → conteneur `platform` → rôle **`muhimu_platform`**.  
- Les deux ne partagent pas le même rôle PG au runtime.

### Démarrage platform (autorisé)

```bash
docker compose -p muhimuerp -f docker-compose.yml up -d --no-build --no-recreate --no-deps platform
```

Conteneur **réutilisé** (pas de Recreate). Aucune migration / bootstrap.

| Contrôle | Résultat |
|---|---|
| Conteneur | **healthy** |
| `http://127.0.0.1:8002/api/health` | **200** `{"status":"ok","role":"platform"}` |
| `APP_ROLE` | `platform` |
| Rôle SQL session | **`muhimu_platform`** |
| `rolsuper` / `rolbypassrls` | false / **true** |
| Orgs visibles (BYPASSRLS) | 4 |
| Logs | runserver OK, health 200, pas d’erreur critique |

### Séparation des privilèges (confirmée)

| Canal | Rôle PG | BYPASSRLS |
|---|---|---|
| ERP `backend` | `muhimu_app` | **non** |
| Console API `platform` | `muhimu_platform` | **oui** |

- Connexions distinctes (conteneurs / users PG séparés).  
- Frontend / console navigateur : **aucune** variable d’env `POSTGRES_*` / `PASSWORD` / `SECRET` exposée.  
- Depuis ERP (`muhimu_app`) : `SET ROLE muhimu_platform` → **refusé** (`ProgrammingError`).  
- Secrets : non affichés dans ce rapport.

### Console après platform

| URL | Résultat |
|---|---|
| `http://127.0.0.1:3002/` | **200** |
| `http://127.0.0.1:3002/api/health` | **200** `{"status":"ok","role":"platform"}` |

---

## Phase 5 — Sauvegarde

| Élément | Valeur |
|---|---|
| Fichier | `d:\muhimu\muhimu ERP\backups\postgres\muhimu_dev_20261010_025933.dump` |
| Format | Custom (`-Fc`), gzip |
| Taille | **537 386 octets** (non vide) |
| `pg_dump` exit | **0** |
| `pg_restore -l` | **553 lignes** TOC (543 entries), DB 16.15 |
| ACL fichier | héritage retiré, lecture restreinte au user Windows courant |
| Emplacement | **D:** (hors VHDX Docker) |

**Note :** dump non testé en restauration réelle (pas de restore).

---

## Espace disque (stack DEV complète)

| Disque | Libre |
|---|---|
| C: | ~87,9 Go |
| D: | ~264,3 Go |

### Volumes
- `muhimuerp_postgres_data` : **intact**  
- Dump externe : `backups/postgres/muhimu_dev_20261010_025933.dump`  
- Aucun volume créé/supprimé lors du démarrage platform

---

## Verdict restauration DEV

# **GO — stack DEV MUHIMU Accounting récupérée**

| Service | Port | État |
|---|---|---|
| db | 5433 | healthy (PG 16.15) |
| redis | 6379 | healthy |
| backend (ERP) | 8001 | healthy — `muhimu_app` |
| platform | 8002 | healthy — `muhimu_platform` |
| frontend | 3001 | up — API health OK |
| console | 3002 | up — API health OK via platform |

### Anomalies résiduelles (non bloquantes)
1. Compose principal backend contient encore `migrate && bootstrap` ; en DEV on utilise l’override `docker-compose.runserver-only.yml`.  
2. `runserver` (dev only) — hors scope bêta Gunicorn.  
3. Builds ARCH-01 / `verify_arch01_beta.sh` / prune : **non démarrés**.

### Prochaine étape (autorisation requise)
Reprise ARCH-01 (builds bêta / `verify_arch01_beta.sh`) ou durcissement Compose (commandes runserver sans migrate par défaut).
