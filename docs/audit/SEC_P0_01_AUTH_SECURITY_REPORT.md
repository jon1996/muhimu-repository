# SEC-P0-01 — Sécurisation de l’authentification

**Date :** 2026-10-10  
**Périmètre :** ERP + Console (Django 5 / Ninja / Redis) — **aucun déploiement distant**  
**Prérequis :** ACC-01, SAAS-03 A1′, ARCH-01 lab GO

---

## 1. Verdict

| Domaine | Verdict |
|---|---|
| Rate-limit login (IP + email, Redis) | **GO** |
| Sessions / cookies / CSRF / anti-fixation | **GO** |
| Séparation ERP / console + staff gate | **GO** |
| Tests SEC-P0-01 (19) | **GO** |
| Non-régression suite (265 = 246 + 19) | **GO** |
| MFA administrateurs | **Proposition seule** (non implémenté) |
| Reset mot de passe self-service | **Hors scope** (résiduel documenté) |

### Verdict global SEC-P0-01 : **GO**

Ouverture bêta privée : **autorisable** sous réserve des risques résiduels (§8) et sans MFA encore.

---

## 2. Architecture d’authentification observée

| Élément | État |
|---|---|
| Mécanisme | Sessions Django + cookies (pas de JWT) |
| CSRF | Ninja `csrf=True` + cookie lisible JS + header `X-CSRFToken` |
| Cookies ERP | `muhimu_session` / `muhimu_csrf` |
| Cookies console | `muhimu_platform_session` / `muhimu_platform_csrf` |
| Session HttpOnly | Oui |
| Session / CSRF Secure | Oui si HTTPS / `SESSION_COOKIE_SECURE` |
| SameSite | `Lax` (configurable) |
| Console | `is_staff` obligatoire à la connexion + `require_staff` sur endpoints |
| Redis (avant) | Provisionné, **non utilisé** pour auth |
| Rate-limit (avant) | **Absent** |

### Matrice endpoints sensibles

| Méthode | Chemin | Surface | Auth | Notes SEC-P0-01 |
|---|---|---|---|---|
| GET | `/api/health` | ERP+console | Non | Public |
| GET | `/api/csrf` | ERP+console | Non | Public |
| POST | `/api/auth/login` | ERP | Non + CSRF | **Throttle** scope `erp` |
| POST | `/api/auth/login` | Console | Non + CSRF | **Throttle** scope `platform` + staff |
| POST | `/api/auth/logout` | ERP+console | CSRF | Invalide session |
| GET | `/api/auth/me` | ERP | Session | |
| GET | `/api/auth/me` | Console | Session + staff | |
| POST | `/api/auth/password/change` | ERP+console | Session (+ staff console) | Nouveau — `update_session_auth_hash` |
| * | `/api/demo/*`, `/api/tenants`, `/api/users`, `/api/mail/*`, `/api/dashboard` | Console | Session + staff | Déjà gated |
| * | `/django/` | Console process | Admin Django | Staff |
| * | Ledger / orgs / companies | ERP | Session | Hors auth brute-force |

---

## 3. Vulnérabilités détectées (avant correctifs)

| ID | Gravité | Description |
|---|---|---|
| V1 | HIGH | Aucun rate-limit sur `/auth/login` (ERP + console) |
| V2 | HIGH | `_client_ip` faisait confiance aveugle à `X-Forwarded-For` |
| V3 | MEDIUM | Pas de politique explicite `SESSION_COOKIE_AGE` (défaut ~2 semaines) |
| V4 | MEDIUM | Pas d’API changement de mot de passe (rotation session non exercée) |
| V5 | MEDIUM | Pas de MFA staff (SEC-01) |
| V6 | LOW | Pas de reset mot de passe self-service |
| V7 | LOW | Mot de passe temporaire encore renvoyé dans JSON grants démo (préexistant) |

Protections déjà présentes (non redondantes) : messages génériques « Identifiants invalides. », cookies séparés ERP/console, CSRF, `login()` Django (cycle de clé anti-fixation), `is_active`, staff gate console, audit `auth.login` / `platform.login`.

---

## 4. Corrections implémentées

### Rate-limit Redis (fail-closed)

- Module `apps/identity/login_throttle.py` + helper `apps/identity/auth_login.py`
- Compteurs par **email** et par **IP**, scopes séparés `erp` / `platform`
- Lockout **temporaire** uniquement (pas de ban permanent)
- Succès : reset compteur email (IP conservée anti-spray)
- Redis down → **HTTP 503** générique (pas de tentatives illimitées silencieuses)
- Lockout → **HTTP 429** message générique
- Logs : email/IP hashés via compteurs uniquement — **jamais** le mot de passe

### IP client de confiance

- `apps/identity/client_ip.py`
- Par défaut : `REMOTE_ADDR` seul (ignore XFF / X-Real-IP)
- Avec `AUTH_TRUST_PROXY=1` (+ allowlist optionnelle) : privilégie `X-Real-IP` posé par nginx

### Sessions / cookies

- `SESSION_COOKIE_AGE` défaut **12 h** (43200 s)
- Logout = flush session Django
- Changement de mot de passe : `update_session_auth_hash` (session courante conservée, hash aligné)
- Anti-fixation : inchangé — fourni par `django.contrib.auth.login` (`cycle_key`)

### Console / admin

- Même throttle sur login platform
- Endpoints admin restent derrière `require_staff`
- Compte non-staff → 403 (sans incrément brute-force, pour éviter DoS d’un staff via compte ERP connu)

---

## 5. Seuils et configuration

| Paramètre | Défaut | Justification |
|---|---|---|
| `AUTH_LOGIN_MAX_ATTEMPTS_EMAIL` | **5** / 10 min | Standard anti-brute-force compte ; aligné backlog P0 |
| `AUTH_LOGIN_MAX_ATTEMPTS_IP` | **40** / 10 min | Plus haut pour limiter le DoS d’un utilisateur derrière NAT bureau |
| `AUTH_LOGIN_WINDOW_SECONDS` | **600** (10 min) | Fenêtre glissante de comptage |
| `AUTH_LOGIN_LOCKOUT_SECONDS` | **900** (15 min) | Verrouillage temporaire, pas permanent |
| `AUTH_LOGIN_THROTTLE_BACKEND` | `redis` (runtime) / `memory` (tests) | Isolation tests sans Redis partagé |
| `AUTH_TRUST_PROXY` | `0` DEV ; **`1` bêta** | Backend bêta non exposé, derrière nginx |
| `SESSION_COOKIE_AGE` | **43200** | Sessions bêta plus courtes que le défaut Django |

Nginx bêta pose déjà `X-Real-IP` / `X-Forwarded-For` / `X-Forwarded-Proto` (`deploy/beta/nginx.conf`).

---

## 6. Fichiers modifiés / créés

### Créés
- `backend/apps/identity/client_ip.py`
- `backend/apps/identity/login_throttle.py`
- `backend/apps/identity/auth_login.py`
- `backend/apps/identity/tests/test_login_throttle.py`
- `docs/audit/SEC_P0_01_AUTH_SECURITY_REPORT.md`

### Modifiés
- `backend/apps/identity/api.py` — login throttle + password change
- `backend/apps/platform/api.py` — idem console
- `backend/apps/audit/services.py` — IP via `client_ip`
- `backend/config/settings.py` — sessions + knobs SEC-P0-01
- `.env.example`, `.env.beta.example`, `.env.beta` (flags non secrets)

Aucune migration, aucune modification RLS / règles comptables, aucun prune Docker.

---

## 7. Tests exécutés

| Suite | Résultat |
|---|---|
| SEC-P0-01 `apps.identity.tests.test_login_throttle` (19) | **OK** |
| Suite complète Django | **265 OK** (~551 s) |
| Couverture implicite ACC-01 / SAAS-03 | Incluse dans 265 |
| ARCH-01 essentiels (DEV + bêta health, DEBUG=False bêta, throttle redis actif) | **OK** |

### Couverture des 15 exigences

| # | Exigence | Test / preuve |
|---|---|---|
| 1 | Connexion valide | `test_valid_login`, `test_staff_login_ok` |
| 2 | Mot de passe incorrect | `test_wrong_password_generic` |
| 3 | Compte inexistant | `test_unknown_account_generic` |
| 4 | Tentatives répétées | `test_lockout_after_email_failures` |
| 5 | Limite IP | `test_ip_limit_independent_of_email` |
| 6 | Limite identifiant | `test_lockout_after_email_failures` |
| 7 | Expiration fenêtre | `test_window_expiry_allows_retry` |
| 8 | Redis indisponible | `test_redis_unavailable_fail_closed` → 503 |
| 9 | En-têtes IP falsifiés | `test_forged_xff_ignored_without_trusted_proxy` |
| 10 | Déconnexion | `test_logout_invalidates_session` |
| 11 | Session après logout | idem (`/auth/me` 401) |
| 12 | Compte désactivé | `test_disabled_account_generic` |
| 13 | Admin non autorisé | `test_admin_endpoint_requires_staff` |
| 14 | Isolation ERP / console | cookies séparés + `test_non_staff_denied` + `test_erp_session_cookie_name_isolated` |
| 15 | Pas de fuite comptes / mots de passe | messages génériques + `test_no_password_in_audit_metadata` |

---

## 8. Risques résiduels

1. **Pas de MFA staff** — prioritaire avant commercialisation large (voir §9).  
2. **Pas de reset mot de passe self-service** — process manuel / admin pour la bêta privée.  
3. **Sessions Django en DB** — pas d’invalidation globale multi-appareils au change password (session courante OK).  
4. **NAT d’entreprise** — seuil IP 40 ; ajustable via env si faux positifs.  
5. **Temp password dans JSON grants** — surface console staff uniquement ; à retirer (SEC follow-up).  
6. **Fail-closed Redis** — indispo Redis = login 503 (disponibilité vs sécurité : choix assumé).  
7. Backend DEV toujours en `runserver` — hors scope (ARCH-01 bêta utilise Gunicorn).

---

## 9. Recommandation MFA (proposition — non implémentée)

**Pas de réécriture du modèle `User` requise.**  
Proposition séparée (SEC-01) :

| Élément | Proposition |
|---|---|
| Cible | Comptes `is_staff` (console) en priorité |
| Mécanisme | TOTP (RFC 6238) + codes de secours |
| Schéma | Tables additives `StaffMfaDevice`, `StaffMfaBackupCode` (FK User) |
| Flux | Login password OK → challenge MFA → session « fully authenticated » |
| UX | Écran console `/login/mfa` ; enrollment obligatoire staff |
| Effort | M — sans changer RLS ni comptabilité |
| Dépendance | Bibliothèque TOTP éprouvée (ex. `pyotp`) + QR enrollment |

**Attendre autorisation explicite avant implémentation MFA.**

---

## 10. Commandes utiles

```bash
# Tests SEC seuls
python manage.py test apps.identity.tests.test_login_throttle --keepdb

# Suite complète
python manage.py test --keepdb
```

Variables documentées dans `.env.example` / `.env.beta.example`.

---

## 11. Suite

- **OPS-01** : non démarré (attente autorisation).  
- **SEC-01 MFA** : proposition prête, implémentation sur autorisation.  
- Déploiement distant : **interdit** / non effectué.
