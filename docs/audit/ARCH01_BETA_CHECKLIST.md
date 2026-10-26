# ARCH-01 — Checklist bêta / staging

Cocher uniquement après vérification effective (commande ou observation).

## Préparation

- [ ] `.env.beta` créé depuis `.env.beta.example` (secrets non commités)
- [ ] `DJANGO_SECRET_KEY` ≠ `dev-only-change-me`
- [ ] `DJANGO_DEBUG=0`
- [ ] `BOOTSTRAP_LOCAL_ACCOUNTS=0`
- [ ] Mots de passe PG owner / app / platform **distincts**
- [ ] Certificats self-signed générés (`deploy/beta/certs/`)
- [ ] Volume `postgres_beta_data` distinct du volume dev

## Build & runtime

- [ ] `docker compose … build` images `production` OK
- [ ] Service `migrate` termine avec succès (sans `bootstrap_demo`)
- [ ] Backend healthy (`/api/health`)
- [ ] Platform healthy (`/api/health`)
- [ ] Processus **Gunicorn** (pas `runserver`)
- [ ] Frontend `next start` (pas `next dev`)
- [ ] Console `next start`

## Sécurité applicative

- [ ] `settings.DEBUG is False`
- [ ] ERP connecté en `muhimu_app`
- [ ] Platform connectée en `muhimu_platform`
- [ ] `muhimu_app` : NOSUPERUSER, NOBYPASSRLS
- [ ] `app_bypass_rls()` = false
- [ ] Cookies Secure activés (env / DEBUG=False)
- [ ] `ALLOWED_HOSTS` / `FRONTEND_ORIGINS` HTTPS bêta
- [ ] Ports DB/Redis/API **non** publiés sur l’hôte

## Proxy

- [ ] HTTP → HTTPS redirect
- [ ] `https://erp.beta.localhost:8443/api/health` OK (cert self-signed)
- [ ] Console joignable sur `console.beta.localhost`

## Non-régression

- [ ] Suite Django **246** tests OK
- [ ] Migrations appliquées sur DB bêta sans toucher `postgres_data` (dev)
- [ ] RLS / ACC-01 non régressés (couverts par la suite)

## Interdits (ne pas cocher comme faits)

- [ ] ~~Déploiement serveur distant~~ — interdit
- [ ] ~~Certificats / secrets de production~~ — interdits
- [ ] ~~SEC-P0-01 / OPS-01~~ — hors scope
