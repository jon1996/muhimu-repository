# Backlog d’issues — audit pré-bêta

Format : ID · Gravité · Composant · Description · Fichier · Effort · Tests de validation

---

## P0 — Bloquant avant bêta

### ACC-01 — Course critique sur BalanceSnapshot
- **Statut :** **CORRIGÉ** (2026-10-10) — voir `ACC01_FIX_REPORT.md`  
- **Gravité :** CRITICAL  
- **Composant :** ledger / balance  
- **Fichier :** `backend/apps/ledger/services/balance.py` (`apply_posted_lines`)  
- **Cause :** read-modify-write sans verrou  
- **Impact :** soldes / balance / états faux sous validations simultanées  
- **Effort :** M (0,5–1 j)  
- **Validation :** 4 tests `TransactionTestCase` multi-connexions + suite 199 OK  

### SAAS-03 — Isolation multi-tenant
- **Statut :** **V1/V2/V4 CORRIGÉS** · **V3 design en attente** — `SAAS03_FIX_REPORT.md`  
- **Gravité :** HIGH (V3 résiduel)  
- **Résultat tests (2026-10-10) :** 233 découverts · 232 OK · 1 skipped (V3)  
- **Restant :** valider puis implémenter V3 A1 (`SAAS03_V3_RLS_DESIGN.md`)  

### OPS-01 — Pas de backup/restore prouvé
- **Gravité :** CRITICAL  
- **Composant :** exploitation  
- **Preuve :** aucune doc/runbook dans le dépôt  
- **Impact :** perte de données pilotes  
- **Effort :** M (1 j + drill)  
- **Validation :** restore sur instance vierge + smoke tests  

### ARCH-01 — Runtime Docker non production
- **Gravité :** HIGH  
- **Composant :** docker-compose  
- **Fichier :** `docker-compose.yml` (migrate + bootstrap_demo + runserver)  
- **Impact :** instabilité, comptes locaux, pas prêt externes  
- **Effort :** M  
- **Validation :** compose/prod profile gunicorn, bootstrap off  

### SEC-P0-01 — Pas de rate-limit auth
- **Gravité :** HIGH  
- **Composant :** identity  
- **Fichier :** `apps/identity/api.py`  
- **Impact :** brute-force comptes pilotes  
- **Effort :** S–M  
- **Validation :** 5ᵉ échec → 429 / lockout temporaire  

### SYSCO-01 — Validation expert-comptable liasse
- **Gravité :** HIGH (métier)  
- **Composant :** sn_map / statements  
- **Fichiers :** `services/sn_map.py`, `statements.py`  
- **Impact :** états contestés par les pilotes EC  
- **Effort :** externe + éventuels correctifs  
- **Validation :** PV signé + jeux fictifs verts  

---

## P1 — Avant commercialisation

| ID | Gravité | Description | Fichiers |
|---|---|---|---|
| ACC-02 | HIGH | Immuabilité contournable via `.update()` | `lettering.py`, `bank_rec.py`, modèles |
| ACC-03 | HIGH | Pas de CHECK SQL équilibre pièce | migrations Entry/EntryLine |
| ACC-04 | MEDIUM | Idempotency sans compare payload | `posting.py` |
| ACC-05 | MEDIUM | Pas de réconciliation snapshots | nouveau job |
| ARCH-02 | HIGH | Celery non branché | docs + infra |
| ARCH-03 | MEDIUM | api.py monolithique | `ledger/api.py` |
| IO-01 | HIGH | Pas d’export portabilité sortie client | API manquante |
| IO-02 | MEDIUM | Pas d’import bulk écritures | API manquante |
| SEC-01 | HIGH | Pas de MFA | identity |
| SEC-03 | MEDIUM | Headers HSTS | settings |
| UX-01 | HIGH | Pas d’assistant démarrage | frontend |
| DOC-01 | HIGH | Pas de guide utilisateur / CGU | docs produit |
| CLOSE-01 | MEDIUM | Clôture annuelle peu testée E2E | `closing.py` |
| REOPEN-01 | MEDIUM | Réouverture exercice absente | — |

---

## P2 — Améliorations futures

| ID | Description |
|---|---|
| TAX-01 | Moteur TVA / fiscalité nationale |
| CCA-01 | Automatisation CCA/PCA |
| BILL-01 | Facturation liée au ledger |
| SUB-01 | Abonnements / metering |
| PERF-01 | Bench 10k–100k + index |
| RLS-CO | RLS aussi au niveau `company_id` (option) |
| ANALYTICS | Budgets / analytique avancée |

---

## Suivi

Mettre à jour ce fichier à chaque correction P0 avec : date, PR, résultat tests, validateur.
