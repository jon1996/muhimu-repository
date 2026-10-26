# Revue d’architecture — MUHIMU Accounting

**Stack réelle :** Django 5.2 + Django Ninja · Next.js (ERP + console) · PostgreSQL 16 · Redis 7  
**Apps backend :** `identity`, `tenancy`, `ledger`, `audit`, `platform`

---

## 1. Organisation

```
muhimu ERP/
├── backend/          # API unique, APP_ROLE=erp|platform
├── frontend/         # UI produit (port 3001)
├── console/          # Console SaaS ops (port 3002)
├── docs/             # architecture.md, ledger.md, audit/
└── docker-compose.yml
```

Deux runtimes API partagent le même code et la même base :

| Surface | `APP_ROLE` | Cookies | Admin Django |
|---|---|---|---|
| ERP | `erp` | `muhimu_session` / `muhimu_csrf` | Non |
| Console | `platform` | `muhimu_platform_*` | Oui (`/django/`) |

## 2. Séparation des couches

| Couche | Emplacement | Commentaire |
|---|---|---|
| Modèles | `apps/*/models.py` | Clair, UUID, `organization` + `company` |
| Services métier | `apps/ledger/services/*` | Posting, balance, états, clôture… |
| API | `apps/*/api.py` | Django Ninja ; `ledger/api.py` monolithique |
| AuthZ | `apps/tenancy/access.py` + middleware | Rôles writer/admin |
| UI | Next.js App Router | Pages par domaine comptable |

**Point d’attention :** `ledger/api.py` (~2 000+ lignes, ~93 routes) concentre trop de responsabilités — risque de régression à l’extension ERP.

## 3. Tenancy

- Schéma partagé (pas de schema-par-tenant).
- RLS : `organization_id = app_current_org()` (+ bypass staff/superuser).
- Isolation **société** : applicative (`X-Company-Id`, `CompanyAccess` pour cabinets).
- `CONN_MAX_AGE = 0` pour éviter la fuite de variables RLS entre requêtes.

## 4. Dépendances et versions

Voir `backend/requirements.txt` :

- Django 5.2.5, django-ninja 1.4.3, psycopg 3.2.9, redis 6.4.0, reportlab, pillow, gunicorn.

Frontend : Next.js (lockfiles présents). Celery **non branché** malgré Redis.

## 5. Migrations / patches

- `ledger` : 32 migrations (dont nombreuses RLS table par table).
- Qualité acceptable ; RLS répétée (pattern SQL dupliqué).
- Bootstrap démo via management command — ne doit pas tourner en prod.

## 6. Gestion d’erreurs, logs, secrets

- Erreurs API souvent `HttpError` texte FR — cohérent mais sans codes structurés.
- `AuditLog` pour actions sensibles (couverture à inventarier).
- Secrets via `.env` (gitignoré) ; défauts faibles si `DJANGO_DEBUG=1`.

## 7. Code obsolète / non terminé

- Peu de TODO/FIXME critiques.
- Celery / files lourdes : conçu mais non implémenté.
- Pas de module Frappe/ERPNext résiduel.

## 8. Maintenabilité / extensibilité ERP

| Module futur | Réutilisation recommandée |
|---|---|
| Facturation / achats / ventes | Poster uniquement via `create_draft` / `post_entry` |
| Trésorerie | Étendre `bank_rec` / `cash` existants |
| Stocks | `InventoryCampaign` déjà amorcé |
| RH / paie | Nouveau domaine → écritures OD automatiques |
| Analytique | Classe 9 / CAGE déjà présent |

**Risque de couplage :** logique métier trop présente dans `api.py` ; extraire des services/événements avant d’ajouter des modules.

## 9. Risques architecture (résumé)

| ID | Gravité | Description |
|---|---|---|
| ARCH-01 | HIGH | Compose : `runserver` + migrate + `bootstrap_demo` |
| ARCH-02 | HIGH | Pas de workers async |
| ARCH-03 | MEDIUM | Pas de contrainte SQL d’équilibre des pièces |
| ARCH-04 | MEDIUM | `api.py` ledger monolithique |
| ARCH-05 | LOW | Secrets / DEBUG par défaut en local |

## 10. Recommandations de refactorisation (hors implémentation immédiate)

1. Runtime prod : gunicorn + migrate contrôlé + pas de bootstrap.
2. Découper `ledger/api.py` par sous-routers (posting, books, statements, treasury…).
3. Introduire file Celery pour PDF/exports/imports.
4. Ajouter CHECK SQL / trigger d’équilibre.
5. Contrats d’événements `entry.posted` pour modules futurs.
