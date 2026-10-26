# BETA_READINESS_REPORT — Décision formelle bêta privée (BETA-READINESS-01)

**Date :** 2026-10-13  
**Mode :** audit **lecture seule** (aucune migration, note, déploiement, RLS, volume)  
**Références :** ACC-01/02/03, CLOSE-01, PDF-CLAIM, SAAS-03, SEC-P0-01, OPS-01, SYSCO-01, suite **333 tests OK** (DEV)

---

## Verdict synthétique

| Scénario | Verdict |
|----------|---------|
| **Instance bêta actuelle, sans déploiement** | **NO-GO** |
| **Bêta privée locale / réseau contrôlé, après plan de déploiement autorisé** | **CONDITIONAL GO** |
| **Bêta accessible sur Internet (testeurs distants)** | **NO-GO** (critères §4 non remplis) |
| **Production / dépôt réglementaire** | **NO-GO** (SYSCO-01 + EC) |

---

## 1. Anomalies bloquantes

| ID | Anomalie | Preuve (audit) | Levier |
|----|----------|----------------|--------|
| B1 | **Code bêta obsolète** vs dépôt DEV (PDF-CLAIM, bandeau UI) | `pdf_disclaimers.py` **absent** dans `muhimu-beta-backend-1` ; bandeau **absent** frontend bêta ; DEV monté en volume | Rebuild + deploy (`BETA_DEPLOYMENT_PLAN.md`) |
| B2 | **Migration 0033 (ACC-03) non appliquée** en bêta | DEV : 33 migrations ledger ; bêta : **32** ; **0 trigger** ACC-03 en bêta vs **4** en DEV | Migrate 0033 sur bêta |
| B3 | **MFA administrateurs non implémenté** | `SEC_P0_01_AUTH_SECURITY_REPORT.md` — proposition seule | Bloquant **Internet** ; P1 avant scale |
| B4 | **Validation expert-comptable mapping liasse** | SYSCO-01 CONDITIONAL GO | Bloquant communication « conforme » ; états OK **avec disclaimers** seulement |
| B5 | **Écart immutabilité SQL** bêta | Bypass SQL possible sans 0033 | Aligner bêta sur DEV |

---

## 2. Anomalies non bloquantes (bêta privée fictive)

| ID | Anomalie | Mitigation |
|----|----------|------------|
| N1 | 0 notes 2 legacy en base | Surveillance + options A/B/C (`LEGACY_NOTES_REVIEW.md`) |
| N2 | Consolidation / CAGE / ESG exposés API+UI | Restreindre périmètre (`BETA_FEATURE_SCOPE.md`) |
| N3 | Viewer peut exporter PDF | Acceptable pilote restreint ; durcir si rôle viewer élargi |
| N4 | Bêta DB vide (0 exercices) | Jeux fictifs à charger / onboarding testeurs |
| N5 | Checklist `BETA_LAUNCH_CHECKLIST.md` partiellement datée (195 tests) | Mettre à jour références 333 tests |
| N6 | SMTP console en bêta | OK lab ; requis pour invitations Internet |
| N7 | Pas de réouverture exercice | **Voulu** (R0+R2) — documenter support |

---

## 3. Fonctionnalités à exclure (1ʳᵉ bêta)

Voir détail `BETA_FEATURE_SCOPE.md` :

- Consolidation / combiné (UI + API)
- Classe 9 / CAGE avancé
- RSE / ESG
- Escompte (optionnel)
- Toute affirmation marketing certification SYSCOHADA

---

## 4. Écarts DEV / bêta (instantané 2026-10-13)

| Dimension | DEV (`muhimuerp`) | Bêta (`muhimu-beta`) |
|-----------|-------------------|----------------------|
| Code backend | Volume live + derniers correctifs | Image production **2026-10-10**, sans PDF-CLAIM |
| Code frontend | Volume live + bandeau beta | Image sans bandeau |
| Django DEBUG | `.env` dev (typ. debug local) | `DJANGO_DEBUG=0` |
| Bootstrap démo | `BOOTSTRAP_LOCAL_ACCOUNTS=1` | `0` ✅ |
| Serveur app | runserver | Gunicorn ✅ |
| Postgres port hôte | 5433 exposé | Non publié ✅ |
| Redis | 6379 exposé | Réseau interne, `--appendonly no` |
| Migrations ledger | **0033** | **0032** |
| Triggers ACC-03 | 4 | **0** |
| RLS activée | Oui (tables échantillon) | Oui (tables échantillon) |
| Rôles PG | muhimu / muhimu_app / muhimu_platform | Idem |
| Exercices en base | 5 | 0 |
| Notes annexes persistées | 0 | 0 |
| Proxy HTTPS | Non (ports 3001/8001) | nginx 18080/18443 ✅ |
| Rate-limit auth | Configurable | `.env.beta.example` SEC-P0-01 ✅ |

**À déployer en bêta pour parité fonctionnelle :** commit courant (PDF-CLAIM, CLOSE-01, ACC-02 app, ACC-03/0033), rebuild images, migrate 0033, fumée PDF + clôture.

---

## 5. Phase 1 — Notes 2 (résumé)

→ **`LEGACY_NOTES_REVIEW.md`**

- **0** enregistrement problématique persisté (DEV et bêta).
- Risque principal : **déploiement** du nouveau défaut + bandeau PDF sur bêta (B1).
- Traitements A/B/C documentés ; **aucune modification** effectuée.

---

## 6. Phase 2 — Fonctionnalités (résumé)

→ **`BETA_FEATURE_SCOPE.md`**

- Cœur comptable **testé** (écritures, balance, clôture E2E, immobilisations, trésorerie, états).
- **API non filtrée** pour modules expérimentaux — recommandation feature flags + 403.
- Pas de module fiscal national ; pas de réouverture self-service.

---

## 7. Phase 3 — Écarts (résumé)

→ Section 4 ci-dessus + **`BETA_DEPLOYMENT_PLAN.md`**

- Ne **pas** appliquer migrate sans backup.
- Ne **pas** modifier volumes/prune (contrainte utilisateur respectée).

---

## 8. Checklist GO / NO-GO

Légende : **O** obligatoire · **R** recommandé · **I** obligatoire si **Internet**

| # | Critère | Local privé | Internet | État |
|---|---------|-------------|----------|------|
| 1 | Intégrité comptable (ACC-01/02/03) | O | O | ✅ DEV / ❌ bêta (B2,B5) |
| 2 | Isolation multi-tenant SAAS-03 | O | O | ✅ tests 333 ; RLS bêta OK |
| 3 | Authentification SEC-P0-01 | O | O | ✅ rate-limit config bêta |
| 4 | MFA admin | R | **I** | ❌ non implémenté |
| 5 | Backup / restore OPS-01 | O | O | ✅ procédure lab ; drill à reproduire sur bêta |
| 6 | Données fictives uniquement | O | O | ⚠️ charte + process à formaliser |
| 7 | Mentions non-certification PDF-CLAIM | O | O | ✅ DEV code / ❌ bêta déployé (B1) |
| 8 | Périmètre fonctionnel défini | O | O | 📄 BETA_FEATURE_SCOPE |
| 9 | Tests E2E clôture CLOSE-01 | O | O | ✅ 19 tests |
| 10 | Journalisation / supervision | R | **I** | ⚠️ basique (LOG_LEVEL) |
| 11 | Remontée anomalies | R | O | 📋 à activer (canal + template) |
| 12 | Retour arrière | O | O | 📄 plan rollback |
| 13 | Conditions accès testeurs | O | O | ⚠️ invitations / liste nominative |
| 14 | Validation EC mapping | R | R | ❌ en attente |

---

## 9. Plan de mise à jour bêta (non exécuté)

→ **`BETA_DEPLOYMENT_PLAN.md`** (backup → migrate 0033 → rebuild → triggers → RLS → fumée → PDF → clôture → rollback)

---

## 10. Actions nécessitant autorisation

| Action | Owner |
|--------|-------|
| Rebuild + redeploy stack bêta | Ops / produit |
| Application migration 0033 sur `muhimu_beta` | Ops (post-backup) |
| Feature flags périmètre bêta | Dev |
| MFA staff / console | Dev (SEC-01) |
| Migration notes legacy (option C) | Produit + ops (si scan > 0) |
| Ouverture Internet / DNS public | Produit + sécurité |
| Validation EC jeux fictifs | Expert-comptable externe |

---

## 11. Décision proposée

1. **Valider le CONDITIONAL GO** pour une **bêta privée** sous conditions : exécution du **plan de déploiement** (parité DEV), charte données fictives, périmètre fonctionnel restreint, PDF-CLAIM actif.
2. **Maintenir NO-GO** sur l’**état actuel** de l’instance bêta sans rebuild/migrate.
3. **Reporter NO-GO Internet** jusqu’à MFA admin, SMTP, monitoring, checklist §4 complète.

---

## 12. Livrables BETA-READINESS-01

| Document | Contenu |
|----------|---------|
| `BETA_READINESS_REPORT.md` | Ce rapport |
| `BETA_FEATURE_SCOPE.md` | Périmètre + API |
| `BETA_DEPLOYMENT_PLAN.md` | Plan ops non exécuté |
| `LEGACY_NOTES_REVIEW.md` | Notes 2 historiques |

**Aucune modification système effectuée.** En attente d’instructions.
