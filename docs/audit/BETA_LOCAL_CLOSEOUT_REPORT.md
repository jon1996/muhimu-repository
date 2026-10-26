# BETA-LOCAL-CLOSEOUT-01 — Clôture validation bêta locale

**Date :** 2026-10-15  
**Autorisation :** GO écrit utilisateur (bêta locale uniquement)  
**Références :** `BETA_FINAL_READINESS_REPORT.md`, `SEC_SESSION01_BETA_DEPLOY_REPORT.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | Runner read-only **OK** sur bêta live ; données et ACC-03 **stables** ; réconciliation montants **documentée**. **Tests navigateur SessionGuard non exécutés** (checklist §5). **Testeurs externes : NO-GO** — pas d’infra distante sans GO séparé. |

---

## 1. Précontrôles

| Contrôle | Résultat |
|----------|----------|
| Cible **`muhimu-beta`** locale | **OK** — seul `muhimu-beta-backend-1` recréé |
| Sauvegardes / rollback | **OK** — `backups/postgres/muhimu_beta_sec_session01_pre.dump` (~369 KB), `muhimu_beta_uat02_pre.dump` ; rollback : `pg_restore` sur volume `postgres_beta_data` (procédure `BETA_DEPLOYMENT_PLAN.md` §10) |
| Écart dépôt ↔ image déployée (avant closeout) | **`runner_rls.py` absent** dans conteneur ; `uat_probe.py` ancienne version → **écart confirmé**, justifie rebuild |
| Correctif sans changement RLS / rôles PG | **OK** — utilise uniquement `tenant_context()` (GUC `app.current_user_id` / `app.current_organization_id`) ; **aucune** migration policy |
| Périmètre tenant runner | **OK** — `ORG_SLUG` et `RUNNER_OWNER_EMAIL` **constants** (`beta-test-01`, owner test) ; pas de paramètre org arbitraire |

**Arrêt si modification non prévue :** N/A.

---

## 2. Rebuild ciblé déployé

| Élément | Action |
|---------|--------|
| Image | **`muhimu-beta-api`** rebuild (2 passes : `runner_rls` + fix `uat_probe`) |
| Service | **`backend`** `--no-deps --force-recreate` |
| Non touché | `platform`, `frontend`, `console`, `proxy`, `db`, `redis`, **DEV**, **Frappe** |
| Migrate / bootstrap / scénarios mutants | **Aucun** |

**Fichiers dépôt concernés :**

- `apps/identity/beta_test01/runner_rls.py` (nouveau)
- `apps/identity/beta_test01/scenarios.py` (délégation ORM)
- `apps/identity/beta_test01/uat_probe.py` (contexte RLS + `select_related`)

---

## 3. Validation runner — `run_beta_uat01_probes --confirm-target`

**Exécution :** 2026-10-15, conteneur `muhimu-beta-backend-1`, **exit 0**.

| Contrôle | Résultat |
|----------|----------|
| Résolution `beta-test-01` sous `muhimu_app` | **OK** — org `cabinet`, demo |
| Contournement RLS | **Non** — contexte tenant owner test uniquement |
| Isolation cabinet | **OK** — owner 200/200 ; isol main **400** / isol **200** ; viewer main **200** / isol **400** |
| Matrice `user_can_access_company` | Cohérente avec API |
| BETA-SCOPE | `restrict_mode=true`, features **false** |
| Consolidation | **403** |
| PDF disclaimer | **200**, `DOCUMENT DE TEST` présent |
| ACC-03 (SQL) | **4/4** triggers actifs |

**Non exécuté :** `run_beta_test01_scenarios` (18 scénarios **écrivants**).

---

## 4. Réconciliation des montants — SARL Fleuve Congo (posted)

### Sources des chiffres historiques

| Rapport | Montant cité | Méthode / périmètre |
|---------|--------------|---------------------|
| **BETA-UAT-01** (2026-10-14) | **3 250 000** XAF (D = C) | Contrôle intégrité **lecture seule** : Σ **débit = Σ crédit** sur **lignes** d’écritures **posted** — **à l’époque** ~**5** écritures (clôture 2025 + vente demo, sans reruns massifs) |
| **BETA-UAT-02** (2026-10-14) | **3 300 000** XAF | Même agrégat SQL post **ré-exécution partielle** scénarios (+ écritures test **50 000** répétées) |
| **SEC-SESSION-01 / FINAL-READINESS** (2026-10-15) | **123 000 000** XAF | Σ débit/crédit **toutes lignes posted** — **13** écritures, incluant **`achat ordinateur`** |

### Nature de l’agrégat

- Les trois valeurs sont la **somme des montants de lignes** (`ledger_entryline.debit` / `.credit`) pour `status=posted`, **pas** un solde de balance ni un total « par écriture » unique.
- Pour toute écriture équilibrée, Σ débit lignes = Σ crédit lignes = « volume » comptable de l’écriture.

### État actuel (SQL owner, 2026-10-15)

| Agrégat | Valeur |
|---------|--------|
| Σ lignes posted (toutes) | **123 000 000** / **123 000 000** XAF |
| Σ hors écriture `achat ordinateur` | **3 400 000** XAF |
| Écriture exceptionnelle | **`achat ordinateur`** (2026-10-15) — **119 600 000** XAF (2 lignes) |

**Composition ~3,4 M (hors achat) :** vente demo 1 M, clôture 2025 1 M + 800 k, affectation 200 k, **8×** tests « Test équilibrée BT01 » à 50 k (400 k) = **3,4 M**.

**Conclusion :** pas d’incohérence comptable (D = C partout) ; l’écart **3,25 M → 123 M** s’explique par **nouvelles écritures posted** (reruns scénarios + **saisie manuelle** 119,6 M), pas par un changement de définition d’agrégat.

**Aucune donnée modifiée** dans ce closeout.

---

## 5. SessionGuard navigateur — checklist (non exécutée par l’agent)

Les scénarios ci-dessous **ne sont pas déclarés validés** ; ils sont **à exécuter manuellement** sur `https://erp.beta.localhost:18443`.

| ID | Scénario | Procédure | Statut |
|----|----------|-----------|--------|
| SG-1 | Idle 30 min | Rester inactif > 30 min (ou simuler via attente réelle) ; toute action API → déconnexion | **À faire** |
| SG-2 | Redirect login | Après expiration, vérifier URL `/login?message=…` et texte FR | **À faire** |
| SG-3 | URL métier post-expiration | Ouvrir `/app/beta-test-01/journal` après expiration → redirect login | **À faire** |
| SG-4 | Multi-onglets | Deux onglets ; expiration dans l’un → l’autre refuse les appels authentifiés | **À faire** |
| SG-5 | Avertissement ~5 min | Bandeau « Session bientôt expirée » avant idle (activité réelle) | **À faire** |
| SG-6 | Saisie non enregistrée | Formulaire modifié + expiration → modale « Modifications non enregistrées » (si écran câblé `setHasUnsavedWork`) | **À faire** |

Référence complémentaire : `docs/beta-testers/UAT_NAVIGATEUR_CHECKLIST.md`.

---

## 6. Risques résiduels

| ID | Risque |
|----|--------|
| R1 | Checklist SessionGuard non clôturée |
| R2 | Montant demo Fleuve **123 M** peut perturber démos balance (donnée réelle en base) |
| R3 | Runner mutants (`scenarios.py`) corrigé en code mais **non rejoué** sur bêta |

---

## Restrictions respectées

Pas de déploiement distant, testeurs, migration, changement RLS, écritures, scénarios mutants, prune, DEV/Frappe modifiés.

---

**BETA-LOCAL-CLOSEOUT-01 : CONDITIONAL GO.**  
**Infra distante / testeurs : STOP — en attente de votre autorisation écrite.**
