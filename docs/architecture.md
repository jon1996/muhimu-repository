# Architecture Muhimu ERP

SaaS cloud multi-tenant : ERP Comptabilité / FinTech orienté SYSCOHADA (zone OHADA).

## Décisions

- Backend : Django 5 + Django Ninja (OpenAPI, sessions cookie httpOnly).
- Frontend : Next.js App Router + TypeScript + Tailwind + shadcn/ui.
- Base : PostgreSQL 16. Cache / files d'attente : Redis 7 (Celery plus tard).
- Isolation : schéma partagé + `organization_id` / `company_id` + **Row Level Security**.
- Rôle PostgreSQL runtime : `muhimu_app` (pas superuser, pas `BYPASSRLS`). Les migrations restent sur le propriétaire.
- Pas de schema-par-tenant : un cabinet gère beaucoup de sociétés.

## Niveaux de tenancy

1. **Organization** — client facturé (PME ou cabinet).
2. **Company** — personne morale / dossier SYSCOHADA.
3. **Exercise** — exercice comptable (après lecture de l'acte uniforme).

Rôles : `owner`, `admin`, `accountant`, `auditor`, `viewer`.

- PME : tout membre accède aux sociétés de l'organisation.
- Cabinet : `owner` / `admin` voient tout ; les autres uniquement les sociétés **assignées** (`CompanyAccess`).

## Runtime

Deux images API (même Dockerfile, `APP_ROLE` différent) et deux images web :

- **ERP** (`APP_ROLE=erp`) : `config.urls`, cookies `muhimu_session` / `muhimu_csrf`. Pas d'admin Django.
- **Console SaaS** (`APP_ROLE=platform`) : `config.platform_urls`, cookies `muhimu_platform_session` / `muhimu_platform_csrf`. Staff uniquement. Django admin sous `/django/`. RLS contourné pour l'équipe.

Les accès sandbox sont des `DemoGrant` : sans grant actif, les organisations `is_demo` n'apparaissent pas dans `/auth/me`.

- Chemin court (API) : auth, CRUD, saisie. Soldes à précalculer plus tard (jamais sommer tout l'historique).
- Chemin lourd (Celery, pas encore branché) : états, exports, imports, webhooks.
- Écritures validées immuables : contrepassation uniquement (moteur `ledger` à concevoir).
- `CONN_MAX_AGE = 0` tant que le contexte RLS est posé sur la session PostgreSQL.

## En-têtes tenant

Le frontend authentifié envoie :

- `X-Organization-Slug`
- `X-Company-Id` (optionnel, contexte société active)
- `X-CSRFToken` sur les mutations

## Compte démo

`python manage.py bootstrap_demo`

**Local** (`BOOTSTRAP_LOCAL_ACCOUNTS=1` ou `DJANGO_DEBUG=1`) :

- ERP : `demo@muhimu.local` / `Demo1234!` (grant démo PME + cabinet)
- Console : `ops@muhimu.local` / `Ops1234!` (staff, pas d'accès démo produit)

**Production** (`BOOTSTRAP_LOCAL_ACCOUNTS=0`) : pas de comptes `@muhimu.local`. Console : `STAFF_EMAIL` (ex. `jp@muhimu.tech`). Expéditeur : Private Email `jp@muhimu.tech`.
