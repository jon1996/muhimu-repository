# Plan détaillé de correction des problèmes P0

**Statut :** proposition uniquement — **aucun code métier modifié** dans cette phase.  
**Objectif :** sécuriser MUHIMU avant tests avec comptables / auditeurs (données fictives).

---

## Ordre recommandé des corrections

| Ordre | ID | Raison de priorité |
|---|---|---|
| 1 | **ACC-01** | Risque d’intégrité des soldes (cœur produit) |
| 2 | **SAAS-03** | Preuve d’isolation clients avant tout accès externe |
| 3 | **ARCH-01** | Environnement pilote stable et non « bootstrap auto » |
| 4 | **SEC-P0-01** | Protection des comptes testeurs |
| 5 | **OPS-01** | Capacité de récupération avant ouverture |
| 6 | **SYSCO-01** | Crédibilité métier auprès des EC (peut démarrer en parallèle dès J1) |

**Parallélisation possible :** SYSCO-01 (revue humaine) en parallèle de 1–5.  
**Dépendance :** benches de charge **après** ACC-01.

Effort total estimé (ingénierie, hors revue EC) : **~5–8 jours-personne**.

---

## P0-1 — ACC-01 : course critique sur `BalanceSnapshot`

### Cause exacte

Dans `apply_posted_lines`, chaque ligne postée :

1. charge (ou crée) un `BalanceSnapshot` ;
2. fait `snapshot.mov_debit += line.debit` (et crédit) en Python ;
3. `save()`.

Deux validations concurrentes sur le même `(period, account)` peuvent lire la même valeur puis écraser mutuellement leurs increments → **perte de mouvements**.

La numérotation de journal est déjà protégée (`select_for_update` sur `JournalSequence`), mais **pas** les snapshots.

### Fichiers concernés

- `backend/apps/ledger/services/balance.py` — `apply_posted_lines`, `_ensure_snapshot`
- Appelant : `backend/apps/ledger/services/posting.py` — `post_entry` (déjà `@transaction.atomic`)
- Indirect : `opening.py` (écrit aussi des snapshots)

### Conséquences possibles

- Balance générale ≠ grand-livre
- Bilan / CR / TFT faux
- Clôture sur soldes erronés
- Erreur **silencieuse** (pas d’exception)

### Solution technique recommandée

1. Dans la transaction de `post_entry`, pour chaque compte touché :
   - `BalanceSnapshot.objects.select_for_update().get_or_create(...)`  
   - ou mise à jour atomique :
     ```python
     BalanceSnapshot.objects.filter(...).update(
         mov_debit=F("mov_debit") + line.debit,
         mov_credit=F("mov_credit") + line.credit,
     )
     ```
2. Si création nécessaire : verrouiller un verrou de période (`select_for_update` sur `AccountingPeriod`) avant `get_or_create` pour éviter les doublons de course sur unique `(period, account)`.
3. Option défense en profondeur : commande `reconcile_snapshots(company, period)` comparant SUM(lignes posted) vs snapshots.

### Tests automatisés nécessaires

| Test | Description |
|---|---|
| `test_concurrent_posts_same_account` | N threads/`TransactionTestCase` postent sur 411 ; `mov_debit` == somme exacte |
| `test_snapshot_matches_posted_lines` | Après série de posts/reversals, snapshot == agrégat SQL |
| `test_opening_then_post_consistency` | AN + mouvements : close_debit cohérent |

Utiliser `TransactionTestCase` (pas `TestCase`) pour la concurrence réelle.

### Risques de régression

- Deadlocks si ordre de verrouillage comptes non déterministe → **trier les account_id** avant lock.
- Perf légèrement réduite sous charge (acceptable vs corruption).
- `_ensure_snapshot` qui copie les ouvertures : à ne pas exécuter deux fois de façon divergente.

### Critère de done

Tests concurrence verts + revue code posting/opening + pas de baisse des 195 tests existants.

---

## P0-2 — SAAS-03 : tests d’isolation RLS / multi-tenant

### Cause exacte

Les politiques RLS filtrent sur `organization_id = app_current_org()`. Les tests actuels activent `app.bypass_rls = on` (`LedgerDbTestCase`) et **ne vérifient jamais** qu’un utilisateur d’une org ne voit pas l’autre. L’isolation société cabinet repose sur le middleware applicatif, également peu testée en négatif.

### Fichiers concernés

- `backend/apps/tenancy/middleware.py`
- `backend/apps/tenancy/access.py`
- `backend/apps/tenancy/rls.py`
- Migrations `*_rls*.py` (ledger, tenancy, platform, audit)
- Nouveau : `backend/apps/tenancy/tests/test_rls_isolation.py` (à créer)
- Nouveau : `backend/apps/tenancy/tests/test_company_access.py` (à créer)

### Conséquences possibles

- Fuite d’écritures / pièces / PDF entre clients SaaS
- Non-conformité grave pour cabinets / auditeurs
- Perte de confiance irréversible

### Solution technique recommandée

1. Écrire une suite **sans bypass** (ou avec bascule explicite) :
   - créer org A / org B, users, memberships ;
   - poser `set_config` comme le middleware ;
   - assert QuerySet Entry/Account vides cross-org ;
   - assert API 403/404 cross-org via client Django.
2. Cas cabinet :
   - user accountant sans `CompanyAccess` sur société Beta → refus ;
   - owner voit Alpha + Beta.
3. Cas staff platform : bypass attendu **et** audit log.
4. (Option P1) renforcer RLS avec `company_id` pour tables ledger — hors scope P0 strict si tests applicatifs solides.

### Tests automatisés nécessaires

| Test | Attendu |
|---|---|
| `test_rls_blocks_other_org_entries` | 0 lignes |
| `test_api_cannot_read_foreign_company` | 403/404 |
| `test_cabinet_assignment_required` | 403 sans access |
| `test_sme_member_sees_all_companies` | OK |
| `test_demo_grant_hides_demo_org` | aligné `user_can_access_organization` |

### Risques de régression

- Tests fragiles si ordre middleware change.
- Faux positifs si bypass laissé « on » entre tests → `tearDown` obligatoire.
- Perf CI : migrations RLS déjà lourdes (acceptable).

### Critère de done

Suite isolation verte en CI ; documentée dans `TEST_RUN_REPORT.md`.

---

## P0-3 — ARCH-01 : runtime pilote

### Cause exacte

`docker-compose.yml` service `backend` :

```text
migrate && bootstrap_demo && runserver
```

Inadapté à des testeurs externes : reseed, DEBUG, pas de process manager prod, comptes locaux potentiels.

### Fichiers concernés

- `docker-compose.yml`
- éventuellement `backend/Dockerfile`, nouveau `docker-compose.beta.yml` / `compose.prod.yml`
- `README.md` (doc exploitation — P1 si besoin)

### Conséquences possibles

- Données pilotes écrasées / reseedées
- Comptes `@muhimu.local` exposés si mal configuré
- Instabilité `runserver` sous usage multi-users

### Solution technique recommandée

1. Profile `beta` :
   - `gunicorn config.wsgi:application`
   - migrate **manuel** ou entrypoint one-shot séparé
   - **pas** de `bootstrap_demo` automatique
2. Variables forcées : `DJANGO_DEBUG=0`, `BOOTSTRAP_LOCAL_ACCOUNTS=0`, secrets forts.
3. Frontends buildés (`next start`) plutôt que `npm run dev` pour le pilote.
4. Healthchecks conservés.

### Tests automatisés nécessaires

| Contrôle | Type |
|---|---|
| Smoke : `/api/health` 200 | script CI |
| `DEBUG is False` en settings beta | test settings / assert env |
| Bootstrap local accounts absents | test bootstrap déjà existant — réutiliser |

### Risques de régression

- Dev local cassé si on modifie le compose par défaut → **garder** compose dev, ajouter profile beta.
- Oubli de migrate manuel → checklist ops.

### Critère de done

Une instance pilote démarre sans bootstrap ; login staff/testeurs documenté ; README section « Bêta ».

---

## P0-4 — SEC-P0-01 : rate-limit authentification

### Cause exacte

`identity/api.py` authentifie email/mot de passe sans limitation de tentatives ni lockout.

### Fichiers concernés

- `backend/apps/identity/api.py`
- `backend/config/settings.py`
- éventuellement Redis (`REDIS_URL` déjà présent)
- tests : `backend/apps/identity/tests/test_login_throttle.py` (à créer)

### Conséquences possibles

- Brute-force des comptes pilotes / staff
- Prise de contrôle d’une org démo → pollution ou exfiltration

### Solution technique recommandée

1. Limiter par IP + email (ex. 5 échecs / 10 min → 429).
2. Implémentation simple : compteur Redis ou cache Django ; ou `django-axes` si dépendance acceptée (**à valider** avant ajout).
3. Message d’erreur générique (ne pas révéler si l’email existe) — déjà partiellement le cas.
4. Journaliser les lockouts dans `AuditLog`.

### Tests automatisés nécessaires

| Test | Attendu |
|---|---|
| `test_login_lockout_after_n_failures` | 429 |
| `test_lockout_expires` | succès après fenêtre |
| `test_success_resets_counter` | OK |

### Risques de régression

- Faux positifs derrière NAT d’entreprise → whitelist IP bureau / seuil ajustable.
- Tests CI flaky si cache partagé → cache locmem dédié tests.

### Critère de done

Lockout démontré + tests verts + paramétrage documenté.

---

## P0-5 — OPS-01 : sauvegardes et restauration

### Cause exacte

Aucune procédure versionnée de backup/restore, ni preuve de drill. Volume Docker `postgres_data` ≠ stratégie de reprise.

### Fichiers concernés (à créer, pas de code métier)

- `docs/ops/BACKUP_RESTORE.md` (recommandé)
- scripts éventuels `scripts/backup.sh` / `restore.sh` (hors app)
- checklist : `BETA_LAUNCH_CHECKLIST.md` section B/C

### Conséquences possibles

- Perte totale des écritures pilotes
- Impossibilité de revenir après migration ratée
- Non-recevable pour un cabinet

### Solution technique recommandée

1. Backup logique quotidien : `pg_dump` (custom format) + archive `MEDIA_ROOT`.
2. Rétention : 7 journaliers + 4 hebdo (ajuster).
3. Drill mensuel : restore sur instance jetable → `manage.py check` + login + ouverture balance société démo.
4. Documenter RTO/RPO cibles (ex. RPO 24 h, RTO 4 h pour bêta).
5. Ne **jamais** considérer un volume Docker seul comme backup.

### Tests / preuves nécessaires

| Preuve | Description |
|---|---|
| Drill signé | Date, opérateur, durée, OK/KO |
| Checksum | dump restauré lisible |
| Smoke comptable | 1 écriture + balance après restore |

Pas nécessairement dans `manage.py test` — preuve ops obligatoire.

### Risques de régression

- Scripts restore mal utilisés sur la mauvaise instance → garde-fous (`confirm` + hostname).
- Secrets dans les dumps → stockage chiffré / accès restreint.

### Critère de done

Au moins **un** restore réussi documenté avant invitation des EC.

---

## P0-6 — SYSCO-01 : validation expert-comptable

### Cause exacte

Le mapping SN (`sn_map.py`) et les tests unitaires prouvent une **cohérence logicielle**, pas la conformité au PCGO / AUDCIF. Les pilotes EC rejetteront des états non revus.

### Fichiers concernés (lecture / éventuels correctifs après avis)

- `backend/apps/ledger/services/sn_map.py`
- `backend/apps/ledger/services/smt_map.py`
- `backend/apps/ledger/services/statements.py`
- `backend/apps/ledger/services/closing.py`
- `docs/ledger.md`
- Jeux de données fictifs (seed démo ou fixtures dédiées)

### Conséquences possibles

- Perte de crédibilité
- Correctifs urgents en plein pilote
- Décision NO-GO métier

### Solution technique recommandée

1. Préparer 2 dossiers fictifs (PME commerce XOF, SARL services CDF).
2. Générer liasse PDF + balance + grand-livre.
3. Revue structurée par EC (checklist postes bilan, SIG, TFT, notes minimales).
4. Tracer chaque écart → ticket P0/P1 avec correctif + test unitaire de non-régression.
5. Produire un PV court « validé pour bêta sous réserves… ».

### Tests automatisés nécessaires

- Pour chaque correctif de mapping : cas dans `test_sn_map.py` (pattern déjà en place).
- Pas de substitut au PV humain.

### Risques de régression

- Changer un préfixe de compte peut casser d’autres postes → suite sn_map obligatoire.
- Divergence SMT vs SN selon `accounting_regime`.

### Critère de done

PV EC archivé dans `docs/audit/` (ou espace juridique) + tests sn_map toujours verts.

---

## Plan de sprint suggéré (sans démarrer le code ici)

| Jour | Travaux |
|---|---|
| J1 | ACC-01 implémentation + tests concurrence ; envoi pack liasse à EC (SYSCO-01) |
| J2 | SAAS-03 suite isolation ; début ARCH-01 profile beta |
| J3 | SEC-P0-01 ; finaliser ARCH-01 ; smoke instance pilote |
| J4 | OPS-01 scripts + premier drill restore |
| J5 | Intégration retours EC ; re-run 195+ nouveaux tests ; mise à jour checklist |

**Go bêta fermée** uniquement si les 6 P0 sont **done** selon critères ci-dessus.

---

## Hors scope immédiat (rappel P1, ne pas mélanger)

- CHECK SQL équilibre (ACC-03) — fortement recommandé juste après ACC-01
- MFA, Celery, export portabilité, import écritures, onboarding UX

Ces items restent dans `ISSUES_BACKLOG.md` P1.
