# SEC-SESSION-01 — Durcissement gestion des sessions

**Date :** 2026-10-15  
**Périmètre :** code DEV / tests (`muhimuerp`) — **bêta non modifiée** (pas de redéploiement, pas de changement `.env.beta` sans autorisation)

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **GO (DEV/test)** | Politique implémentée, tests dédiés OK, non-régression login throttle OK. **Application bêta : NO-GO** en attente de votre autorisation écrite. |

---

## Phase 1 — Audit (état initial)

| Zone | Constat |
|------|---------|
| Backend Django | Sessions **DB** (`django.contrib.sessions`), pas de store Redis pour sessions. Redis réservé au throttle login. |
| Cookies | `muhimu_session` / `muhimu_platform_session`, `HttpOnly`, `SameSite` configurable, `Secure` si non-DEBUG. |
| Durée cookie | `SESSION_COOKIE_AGE=43200` (12 h) ; **pas** de sliding (`SESSION_SAVE_EVERY_REQUEST=False`). |
| Fermeture navigateur | `SESSION_EXPIRE_AT_BROWSER_CLOSE=False` en bêta (`.env.beta`) — sessions longues observées en UAT. |
| Inactivité | **Aucun** idle timeout serveur avant SEC-SESSION-01. |
| Auth | `SessionAuth()` Ninja, login Django `login()` (cycle anti-fixation), logout `logout()`. |
| Frontend | 401 sur `/api/auth/me` → redirect `/login` ; pas d’avertissement pré-expiration ni purge centralisée du cache. |
| CSRF | Mutations via jeton `/api/csrf` ; cookie CSRF distinct, 7 j. |
| Proxy bêta | Terminaison TLS loopback ; cookies domaine standard. |

**Distinction idle vs absolu :** deux horodatages en session (`_muhimu_auth_at` fixe à la connexion, `_muhimu_last_activity_at` mis à jour seulement sur **activité éligible**). Le plafond absolu compare `now - auth_at` ; l’idle compare `now - last_activity`. L’activité ne repousse **pas** `auth_at`.

---

## Phase 2 — Implémentation serveur

### Paramètres (`backend/config/settings.py`)

| Variable | Défaut DEV | Rôle |
|----------|------------|------|
| `SESSION_POLICY_ENABLED` | `1` | Coupe-feu global |
| `SESSION_IDLE_TIMEOUT_SECONDS` | `1800` (30 min) | Expiration inactivité |
| `SESSION_ABSOLUTE_TIMEOUT_SECONDS` | `SESSION_COOKIE_AGE` (12 h) | Plafond depuis login |
| `SESSION_IDLE_WARN_BEFORE_SECONDS` | `300` | Alerte front (5 min) |
| `SESSION_EXPIRE_AT_BROWSER_CLOSE` | **`True`** (nouveau défaut code) | Cookie session navigateur |
| `SESSION_IDLE_NO_TOUCH_PREFIXES` | `/api/auth/me`, `/api/auth/session`, `/api/csrf`, `/api/health` | Pas de refresh idle |

### Règles d’activité

- Requêtes **non authentifiées** : ignorées.
- **GET/POST…** authentifiés : refresh idle **sauf** préfixes ci-dessus.
- En-tête **`X-Muhimu-Session-Activity: background`** : pas de refresh (polling contrôlé).
- Expiration : `logout()` + `session.flush()` ; réponses 401 portent `X-Muhimu-Session-Expired: idle|absolute`.

### Fichiers

| Fichier | Rôle |
|---------|------|
| `apps/identity/session_policy.py` | Horodatages, règles, payload statut |
| `apps/identity/middleware.py` | `SessionPolicyMiddleware` |
| `apps/identity/apps.py` | Signal `user_logged_in` → stamp |
| `apps/identity/api.py` | `GET /api/auth/session` (métadonnées, no-touch) |

---

## Phase 3 — Frontend

| Fichier | Comportement |
|---------|--------------|
| `lib/session-events.ts` | Événement global, messages FR |
| `lib/api.ts` | 401 → événement + en-tête expiration |
| `components/session-guard.tsx` | Poll `/api/auth/session` (background), alerte 5 min, redirect login |
| `components/unsaved-work-context.tsx` | Flag « travail non enregistré » (pas de données comptables en stockage) |
| `app/app/[orgSlug]/layout.tsx` | Intégration guard + provider |
| `app/login/page.tsx` | Message query `message=` après expiration |
| `components/app-shell.tsx` | 401 : purge React Query + redirect explicite |

**Limites front :** l’avertissement repose sur l’horloge serveur exposée par `/api/auth/session` ; pas de persistance des brouillons comptables côté navigateur (volontaire).

---

## Phase 4 — Tests

Fichier : `apps/identity/tests/test_session_policy.py`

| # | Scénario | Résultat |
|---|----------|----------|
| 1 | Idle 30 min (60 s en test) | OK |
| 2 | Activité légitime avant idle | OK |
| 3 | Absolu 12 h malgré activité | OK |
| 4 | Logout manuel | OK |
| 5 | Second onglet (même cookie) | OK |
| 6 | Refus après expiration + en-tête | OK |
| 7 | Header background / auth/me no-touch | OK |
| 8 | CSRF public sans session auth | OK |
| 9 | Isolation utilisateurs | OK |
| 10 | Non-régression `test_login_throttle` | OK |

**Exécution (2026-10-15) :**

```text
docker compose run --rm --no-deps backend python manage.py test \
  apps.identity.tests.test_session_policy apps.identity.tests.test_login_throttle
→ 32 tests, 1 échec corrigé (policy disabled), puis 32/32 OK
```

Suite complète DEV (2026-10-15) : **`359 OK`** (~644 s, `docker compose run --rm --no-deps backend python manage.py test`).

---

## Limites connues

| ID | Sujet |
|----|-------|
| L1 | Sessions stockées en **PostgreSQL** — invalidation immédiate OK, pas de cluster Redis session. |
| L2 | **Bêta** : tant que `.env.beta` n’active pas les nouveaux défauts / redeploy, comportement UAT inchangé. |
| L3 | `SESSION_EXPIRE_AT_BROWSER_CLOSE=True` par défaut dans le **code** : les environnements avec `.env` explicite `=0` restent inchangés. |
| L4 | Formulaires métier n’appellent pas encore `setHasUnsavedWork(true)` partout — infrastructure prête, câblage écran par écran à poursuivre. |
| L5 | Console platform : même middleware ; pas de `SessionGuard` Next dédié console dans ce lot. |

---

## Restrictions respectées

Pas de déploiement bêta, migration, RLS, données comptables bêta, prune, invitation testeurs.

---

## Prochaine étape (sur votre GO)

1. Mettre à jour `.env.beta` : `SESSION_EXPIRE_AT_BROWSER_CLOSE=1`, conserver `SESSION_COOKIE_AGE=43200`, ajouter `SESSION_IDLE_TIMEOUT_SECONDS=1800` si override explicite souhaité.  
2. Rebuild / restart stack **bêta** uniquement après autorisation.  
3. Rejouer checklist UAT session (multi-onglets, idle, logout).
