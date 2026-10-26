# SEC-SESSION-01 — Déploiement bêta locale (`muhimu-beta`)

**Date :** 2026-10-15  
**Autorisation :** GO écrit conditionnel utilisateur (bêta locale uniquement — pas VPS, pas testeurs)  
**Référence :** `SEC_SESSION01_REPORT.md`, `BETA_UAT02_REPORT.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | Politique session **active** sur `muhimu-beta` ; données fictives et contrôles SQL **préservés** ; login/logout, idle (simulation), BETA-SCOPE, balance API OK. **Scénarios `run_beta_test01_scenarios` non rejoués** (ORM bloquée par RLS sous `muhimu_app` — voir §4). **Ouverture testeurs : STOP** — en attente de votre GO écrit. |

---

## Phase 1 — Précontrôles

| # | Contrôle | Résultat |
|---|----------|----------|
| 1 | Cible **uniquement** `muhimu-beta` (`docker compose -p muhimu-beta`) | **OK** — aucun `docker compose` DEV / frappe modifié |
| 2 | Autres stacks opérationnelles | **OK** — `muhimuerp-db/redis` healthy ; frappe inchangé |
| 3 | Sauvegarde bêta restaurable | **OK** — `backups/postgres/muhimu_beta_uat02_pre.dump` (~363 KB) ; **pré-déploiement** `muhimu_beta_sec_session01_pre.dump` (~369 KB, 2026-10-15) |
| 4 | Fichiers / variables touchés | **OK** — voir §3 ; **aucun secret** dans ce rapport |
| 5 | Migration DB requise | **OK — aucune** (SEC-SESSION-01 = middleware + session Django + front) |
| 6 | Redis + auth throttle | **OK** — `REDIS_URL=redis://redis:6379/0`, `AUTH_LOGIN_THROTTLE_BACKEND=redis`, rate-limit actif (inchangé) |

**Arrêt si échec :** N/A — précontrôles satisfaisants.

---

## Phase 2 — Vérification sécurité (logique + preuves)

| Exigence | Vérification | Résultat |
|----------|--------------|----------|
| Plafond 12 h non prolongé par requêtes | `_muhimu_auth_at` fixé au login ; activité ne met à jour que `_muhimu_last_activity_at` | **OK** (code + tests DEV) |
| Idle 30 min serveur | `SESSION_IDLE_TIMEOUT_SECONDS=1800` actif en conteneur | **OK** |
| Polling ne prolonge pas | `/api/auth/me`, `/api/auth/session` en no-touch ; smoke `touch_same=True` | **OK** |
| En-tête `X-Muhimu-Session-Activity: background` | Ne prolonge pas l’idle (tests DEV `test_background_header_*`) | **OK** — n’**autorise pas** de contourner l’expiration |
| Multi-onglets après expiration | Simulation idle +1900 s → `/api/auth/me` **401** + `X-Muhimu-Session-Expired: idle` | **OK** (sans raccourcir les délais bêta) |
| Logout invalide session | API **200** puis `/api/auth/me` **401** | **OK** |
| Front sans données sensibles post-expiration | Purge React Query + redirect login (code déployé `muhimu-beta-web`) ; pas de stockage comptable local | **OK** (non audité navigateur complet) |
| Pas de perte silencieuse saisies | `UnsavedWorkProvider` + modale ; câblage écran par écran partiel | **CONDITIONAL** (infra OK, formulaires métier à enrichir) |

**Tests idle/absolu en environnement isolé (délais raccourcis) :**  
`docker compose run --rm --no-deps backend python manage.py test apps.identity.tests.test_session_policy` → **13/13 OK** (stack **DEV**, base `test_muhimu` — **pas** de modification des délais bêta démo).

---

## Phase 3 — Déploiement bêta locale

| Action | Détail |
|--------|--------|
| Variables `.env.beta` | `SESSION_POLICY_ENABLED=1`, `SESSION_IDLE_TIMEOUT_SECONDS=1800`, `SESSION_ABSOLUTE_TIMEOUT_SECONDS=43200`, `SESSION_EXPIRE_AT_BROWSER_CLOSE=1`, `SESSION_IDLE_WARN_BEFORE_SECONDS=300`, `SESSION_COOKIE_AGE=43200` (conservé) |
| Images reconstruites | **`muhimu-beta-api`**, **`muhimu-beta-platform-api`**, **`muhimu-beta-web`** |
| Services recréés | `backend`, `platform`, `frontend` (`--no-deps` — **pas** de job `migrate` relancé) |
| Non reconstruit | `console`, `proxy`, `db`, `redis` |
| Volumes / données | **Préservés** (`postgres_beta_data`, `beta_media`, `beta_static`) |
| Bootstrap | **Aucun** `bootstrap_demo` |

### Paramètres effectifs (conteneur `muhimu-beta-backend-1`)

```text
POLICY True | IDLE 1800 | ABS 43200 | BROWSER_CLOSE True
REDIS redis://redis:6379/0 | THROTTLE redis True
```

### Incident résolu

| Incident | Cause | Correction |
|----------|-------|------------|
| Crash loop backend/platform (`entrypoint_web.sh`) | CRLF Windows → `set -eu` illégal sous `sh` | `Dockerfile` : `sed` CRLF ; `docker-compose.beta.yml` : `command: ["sh", "scripts/entrypoint_web.sh"]` ; scripts réécrits LF |

### Fichiers modifiés (dépôt)

| Fichier | Rôle |
|---------|------|
| `.env.beta` | Variables SEC-SESSION-01 (**non versionné**) |
| `.env.beta.example` | Documentation variables session |
| `docker-compose.beta.yml` | Commande entrypoint bêta |
| `backend/Dockerfile` | Normalisation CRLF scripts (builds futurs) |
| `frontend/app/login/page.tsx` | Suspense `useSearchParams` (build prod Next.js) |

**Non modifié :** `.env` DEV, `docker-compose.yml`, volumes, RLS, migrations.

---

## Phase 4 — Vérifications post-déploiement

| # | Contrôle | Résultat |
|---|----------|----------|
| 1 | Connexion / déconnexion API | **OK** (owner `beta-test-01`) |
| 2 | Expiration idle (simulation +31 min, **délais prod 30 min**) | **OK** — 401 `idle` |
| 3 | Limite absolue | **Non simulée sur bêta** (12 h) — couverte tests DEV |
| 4 | Redirect front après expiration | **Code déployé** ; validation navigateur manuelle recommandée |
| 5 | Saisies non enregistrées | **Infra** déployée ; **CONDITIONAL** |
| 6 | Balance / grand livre | **`GET /api/ledger/balance` → 200** (2 lignes) ; GL nécessite `account_id` (endpoint documenté) |
| 7 | BETA-SCOPE | **OK** — `restrict_mode=true`, flags consolidation/class9/esg/escompte **false** |
| 8 | Triggers ACC-03 | **4/4** : `trg_ledger_entry_forbid_posted_mutation`, `trg_ledger_entryline_forbid_posted_substance`, `trg_ledger_entry_posted_balance`, `trg_ledger_entryline_balanced_deferred` |
| 9 | RLS / rôles PG | **OK** — `muhimu`, `muhimu_app`, `muhimu_platform` inchangés |
| 10 | Données fictives | **OK** — org `beta-test-01` (cabinet) ; Σ débit = Σ crédit posted : Fleuve **123 000 000** / Niari **250 000** XAF |
| 11 | DEV / autres stacks | **OK** — pas de rebuild/restart DEV backend |

### Non exécuté (contrainte RLS)

| Commande | Motif |
|----------|--------|
| `run_beta_test01_scenarios --confirm-target` | `Organization.DoesNotExist` sous **`muhimu_app`** (RLS) — contournement owner **non autorisé** dans ce déploiement |

**Contournement retenu :** sondes API authentifiées (même rôle runtime que la production bêta).

---

## Phase 5 — Risques résiduels

| ID | Risque | Gravité |
|----|--------|---------|
| R1 | Scénarios automatisés 18/18 non rejoués post-deploy | Faible — smoke API + intégrité SQL |
| R2 | Validation navigateur SessionGuard / message login | Faible — checklist UAT session |
| R3 | `setHasUnsavedWork` pas généralisé à tous les écrans | Moyen — UX expiration |
| R4 | Build Windows CRLF — mitigation Dockerfile + compose bêta | Faible |

---

## Restrictions respectées

Pas de VPS, testeurs, migration ajoutée, changement RLS/SYSCOHADA, prune, suppression volume, modification stack DEV, délais session raccourcis sur bêta démo.

---

**SEC-SESSION-01 bêta locale : CONDITIONAL GO.**  
**Invitation testeurs : STOP — en attente de votre autorisation écrite.**
