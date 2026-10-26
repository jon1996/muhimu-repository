# ARCH-01 — Rapport de préparation / vérification environnement bêta

**Date :** 2026-10-10  
**Périmètre :** stack locale isolée `muhimu-beta` — **aucun déploiement distant**  
**Prérequis :** stack DEV récupérée (voir `ARCH01_DOCKER_RECOVERY_REPORT.md`) ; ACC-01 + SAAS-03 A1′

---

## 1. Verdict

| Périmètre | Verdict |
|---|---|
| Builds images bêta | **GO** |
| Runtime stack bêta isolée | **GO** |
| Suite tests Django (246) sur DB bêta | **GO** |
| ACC-01 + SAAS-03 (ciblés) | **GO** |
| Isolation volumes / secrets vs DEV | **GO** |
| Déploiement serveur distant / prod | **NO-GO** (non autorisé, non effectué) |

### Verdict global ARCH-01 : **GO** (local lab)

SEC-P0-01 et OPS-01 **non démarrés**. Aucun prune. Aucune modification des données DEV.

---

## 2. Phase 1 — Vérification préalable

| Contrôle | Résultat |
|---|---|
| Docker daemon | OK (29.6.1) |
| Stack DEV `muhimuerp` | 6 services UP / healthy (inchangée) |
| Backup PG externe | `backups/postgres/muhimu_dev_20261010_025933.dump` présent |
| Volume DEV | `muhimuerp_postgres_data` |
| Volume bêta | `muhimu-beta_postgres_beta_data` (**distinct**) |
| DB bêta | `muhimu_beta` ≠ DEV `muhimu` |
| Secrets | `.env.beta` (non commité) ≠ `.env` |
| Ports hôte bêta | **18080 / 18443** (8080 occupé sur l’hôte) |
| Espace disque avant | C: **~87,9 Go** libres ; D: **~264 Go** |

### Isolation confirmée
- Projet Compose : `muhimu-beta` vs `muhimuerp`
- Réseau : `beta_internal` (DB/Redis/API non publiés)
- Proxy seul publié
- Arrêt immédiat non requis : **aucun risque d’utiliser la base DEV**

### Builds les plus gourmands
1. `muhimu-beta-web` (Next.js `npm ci` + `npm run build`)
2. `muhimu-beta-console` (idem)
3. `muhimu-beta-api` / `muhimu-beta-platform-api` (Python, cache hit)

### Script `verify_arch01_beta.sh` (inspection avant exécution)
| Opération | Destructif ? |
|---|---|
| `up -d --build --remove-orphans` | Non (projet bêta seulement ; pas de `-v`) |
| Service `migrate` one-shot | Migrations sur **`muhimu_beta` uniquement** |
| `BOOTSTRAP_LOCAL_ACCOUNTS=0` | Pas de bootstrap runtime |
| Suite `manage.py test` | DB de test temporaire sur hôte PG bêta |
| Prune / delete volume / remote | **Absent** |

---

## 3. Phase 2 — Builds progressifs

| # | Image | Exit | Disque C après | DEV intact |
|---|---|---|---|---|
| 1 | `muhimu-beta-api` | 0 | ~87,9 Go | oui |
| 2 | `muhimu-beta-platform-api` | 0 | ~87,9 Go | oui |
| 3 | `muhimu-beta-web` | 0 | ~87,4 Go | oui |
| 4 | `muhimu-beta-console` | 0* | ~85,2 Go | oui |

\* Premier essai console **échoué** : `COPY public` sans dossier `public` → corrigé par `console/public/.gitkeep`, rebuild OK.

Autres images : `nginx:1.27-alpine` pull OK. Aucun ENOSPC. Aucun build parallèle lourd.

---

## 4. Phase 3 — Runtime

### Stack `muhimu-beta` (état final)

| Service | État | Notes |
|---|---|---|
| db | healthy | volume `postgres_beta_data` |
| redis | healthy | |
| migrate | Exited 0 | one-shot, **sans bootstrap** |
| backend | healthy | **Gunicorn**, `DEBUG=False`, rôle `muhimu_app` |
| platform | healthy | **Gunicorn**, rôle `muhimu_platform` |
| frontend | up | `npm run start` (production) |
| console | up | `npm run start` (production) |
| proxy | up | HTTPS self-signed **:18443** |

### Contrôles runtime (recheck post-corrections script)

| Contrôle | Résultat |
|---|---|
| backend `/api/health` | OK |
| `DEBUG=False` | OK |
| ERP DB user `muhimu_app` | OK |
| platform DB user `muhimu_platform` | OK |
| pas de `bootstrap_demo` runtime | OK |
| Gunicorn (pid 1) | OK |
| `muhimu_app` NOSUPERUSER NOBYPASSRLS | OK |
| `muhimu_platform` BYPASSRLS NOSUPERUSER | OK |
| proxy HTTPS `/api/health` | OK |
| `app_bypass_rls()=false` | OK |
| `SET ROLE muhimu_platform` depuis ERP | **DENIED** |
| Cookies Secure / HSTS / nosniff / DENY | OK via proxy |
| Volumes DEV ≠ bêta | OK |

**Recheck :** Passed **10** / Failed **0**

---

## 5. Phase 4 — Tests

| Suite | Résultat |
|---|---|
| Django complète (246) via compose bêta | **OK** (~381 s) |
| ACC-01 + SAAS-03 ciblés (`test_snapshot_concurrency` + `test_isolation` et deps, 51) | **OK** (~313 s) |
| Données financières réelles | **Non utilisées** |

### Sécurité environnement bêta (spot)
- `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
- `SECRET_KEY` ≠ défaut
- `CONN_MAX_AGE=0`
- Frontend/console : pas d’identifiants PG exposés
- RLS policies : **non modifiées** (ARCH-01)

---

## 6. Espace disque

| Moment | C: libre | D: libre |
|---|---|---|
| Avant ARCH-01 reprise | ~87,9 Go | ~264 Go |
| Après builds + runtime + tests | ~84,5 Go | ~256,8 Go |

`docker system df` (après) : images ~11,9 Go ; build cache ~9,1 Go (dont ~2,8 Go reclaimable).  
**Aucun `docker builder prune` / `system prune` exécuté.**

---

## 7. Anomalies rencontrées et corrections

| Anomalie | Impact | Correction |
|---|---|---|
| `console/public` absent | Build console KO | `console/public/.gitkeep` |
| Scripts `.sh` en CRLF | `entrypoint_migrate.sh: no such file` | Conversion LF + `.gitattributes` `*.sh text eol=lf` |
| Port hôte **8080** occupé | Proxy up KO | Ports bêta → **18080/18443** (`.env.beta` + example) |
| Variables `POSTGRES_*` du shell hôte (DEV) interpolées dans compose | Volume bêta initialisé avec DB `muhimu` au lieu de `muhimu_beta` ; auth fail | `db.env_file` only ; create `muhimu_beta` + sync mots de passe **sans** delete volume ; verify n’exporte plus les secrets |
| `ps` absent dans image slim | Faux négatif « gunicorn not found » | Détection via `/proc/1/cmdline` |
| psql rend `false`/`true` | Faux négatif privilèges rôles | `CASE WHEN … 't'/'f'` dans le script |

---

## 8. Risques résiduels

1. Certificats self-signed — avertissement navigateur (attendu lab).  
2. Secrets `.env.beta` locaux — ne pas réutiliser en prod.  
3. Build cache Docker ~9 Go — prune uniquement sur autorisation.  
4. `npm audit` console : vulnérabilités signalées au build (hors scope ARCH-01).  
5. Port 8080 hôte déjà pris — documenter 18080/18443.  
6. Pas de WAF / rate-limit (SEC-P0-01).  
7. Pas de backup automatisé bêta (OPS-01).  
8. Hosts `erp.beta.localhost` / `console.beta.localhost` à résoudre localement (fichier hosts) pour UI navigateur.

---

## 9. Décisions d’architecture (rappel)

| Décision | Choix |
|---|---|
| Séparation env | `docker-compose.yml` (dev) + `docker-compose.beta.yml` |
| Reverse proxy | Nginx + certs self-signed |
| Processus app | Gunicorn (target `production`) |
| Migrations | Service one-shot `migrate` |
| Bootstrap démo | Désactivé en bêta |
| Exposition | Proxy 18080/18443 seulement |

---

## 10. Commandes de référence

```bash
# Certificats lab
sh deploy/beta/generate-certs.sh

# Env
cp .env.beta.example .env.beta   # éditer secrets ; ports 18080/18443

# Démarrer (projet isolé)
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta up -d --build

# Vérifier
sh scripts/verify_arch01_beta.sh

# Arrêter (conserve le volume beta)
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta down
```

**Ne pas** : `down -v`, `docker system prune`, `docker builder prune` sans autorisation.

---

## 11. Hors scope / suite

- SEC-P0-01, OPS-01  
- Certificats publics / DNS  
- Déploiement distant  
- Prune Docker  

En attente d’instructions pour la suite.
