# Plan de déploiement — Bêta MUHIMU distante

**Référence :** BETA-REMOTE-ARCH-01  
**Statut :** **planification** — **aucune commande exécutée** sans GO implémentation  
**Date :** 2026-10-15

---

## 0. Prérequis (décisions produit)

- [ ] GO écrit **implémentation infra** (distinct du présent GO architecture)
- [ ] Choix option A ou B (`BETA_REMOTE_COST_ESTIMATE.md`)
- [ ] FQDN validés (D1)
- [ ] Modèle accès testeurs VPN vs HTTPS (D2)
- [ ] Budget approuvé

---

## Phase 1 — Fondations (sans trafic testeurs)

| Étape | Action | Vérification |
|-------|--------|--------------|
| 1.1 | Provisionner VPS / compte cloud **dédié** | Facture / ID projet isolé |
| 1.2 | Durcir OS (updates, utilisateur deploy, fail2ban optionnel) | SSH clé |
| 1.3 | Installer Docker Engine + Compose v2 | `docker version` |
| 1.4 | Configurer pare-feu (443, VPN, deny reste) | Scan externe nmap |
| 1.5 | Déployer VPN admin (WireGuard/Tailscale) | Ping admin via tunnel |
| 1.6 | **Ne pas** ouvrir DNS public tant que TLS pas prêt (ou DNS-01) | — |

**Rollback phase 1 :** destroy VPS (aucune donnée métier).

---

## Phase 2 — Secrets et configuration

| Étape | Action | Interdit |
|-------|--------|----------|
| 2.1 | Créer `.env.beta.remote` **nouveau** (secrets aléatoires) | Copier `.env.beta` local |
| 2.2 | `DJANGO_ALLOWED_HOSTS`, `FRONTEND_ORIGINS`, URLs publiques = FQDN remote | localhost beta |
| 2.3 | Mots de passe PG **distincts** (owner, app, platform) | Réutiliser muhimu_beta |
| 2.4 | Stocker backup chiffré des secrets (coffre ops) | Git |

---

## Phase 3 — Images et compose

| Étape | Action |
|-------|--------|
| 3.1 | Build ou pull images taguées `beta-remote-<sha>` depuis CI |
| 3.2 | Copier `docker-compose.beta.yml` → `docker-compose.beta.remote.yml` (overlay : ports 443 public, volumes nommés **remote**, pas de loopback forcé) |
| 3.3 | Configurer proxy TLS (Let’s Encrypt) — **après** GO certificats |
| 3.4 | `docker compose -f docker-compose.beta.remote.yml --env-file .env.beta.remote up -d` **sans** `--build` non traçé |

**Service `migrate` :** one-shot ; **pas** de `bootstrap_demo`.

---

## Phase 4 — Base de données et jeu demo **propre**

| Étape | Action |
|-------|--------|
| 4.1 | Migrations via `migrate` (même pipeline que local) |
| 4.2 | Provision **nouveau** jeu : org `beta-remote-demo-01` (commande dédiée à créer — **ne pas** `pg_restore` depuis `muhimu_beta`) |
| 4.3 | Comptes testeurs `@beta-remote.muhimu.tech` (fictifs) ; MDP via canal sécurisé |
| 4.4 | Contenu cible : 2 sociétés cabinet, exercices 2025 clôturé / 2026 ouvert, posted **≤ 5 M XAF** total par société (pas de saisie 119 M) |

### Contenu demo recommandé

| Domaine | Contenu |
|---------|---------|
| Organisations | 1 cabinet fictif « Beta Remote Demo » |
| Sociétés | 2 PME Congo XAF (noms **≠** Fleuve/Niari si souhaité branding) |
| PCGO | Plan SYSCOHADA généré (`ensure_company_ledger`) |
| Exercices | 2025 closed + 2026 open |
| Écritures | Vente demo, clôture, affectation, 2–3 écritures équilibrées **contrôlées** |
| Erreurs pédagogiques | 1 brouillon déséquilibré (non posted), 1 tierce partie inactive |
| Rapports | Balance, GL, PDF avec disclaimer |
| **Exclus** | Données réelles, NIF/RCCM réels, copy credentials local |

---

## Phase 5 — Validation technique (bloquante testeurs)

| # | Critère | Référence |
|---|---------|-----------|
| 5.1 | MFA admin hébergeur + staff console | Checklist G3–G4 |
| 5.2 | HTTPS valide ( navigateur vert ) | H1 |
| 5.3 | `run_beta_uat01_probes --confirm-target` (adapté remote DB) | Closeout local |
| 5.4 | ACC-03 × 4 | SQL |
| 5.5 | BETA-SCOPE + consolidation 403 | API |
| 5.6 | SessionGuard SG-1–SG-6 | Manuel |
| 5.7 | Backup + **restore drill** sur clone | O2 |
| 5.8 | Scan ports externe (443 seul) | N3 |
| 5.9 | Documentation testeurs à jour (URLs remote) | `docs/beta-testers/*` |

**Interdit avant GO testeurs :** invitation email, comptes prod, scénarios mutants massifs.

---

## Phase 6 — Ouverture testeurs (sur GO **séparé**)

1. Distribution credentials (1 canal chiffré).  
2. Créneau support ops.  
3. Monitoring renforcé 72 h.  
4. Collecte anomalies (`GRILLE_ANOMALIES.md`).

---

## Phase 7 — Mises à jour continues

| Type | Procédure |
|------|-----------|
| Correctif sécurité | Snapshot DB → rebuild API → probes → 24 h watch |
| Feature | Même que bêta locale closeout (backend ciblé possible) |
| Rollback | Restore dump + image pin N-1 |

---

## Interdictions (rappel mandat ARCH-01)

Pas de déploiement, DNS, certificat, achat, testeurs, modification RLS, copy DB locale, prune volumes.

---

## Références

- Local : `docs/audit/BETA_DEPLOYMENT_PLAN.md`, `BETA_LOCAL_CLOSEOUT_REPORT.md`
- Architecture : `docs/architecture/BETA_REMOTE_ARCHITECTURE.md`
- Sécurité : `docs/audit/BETA_REMOTE_SECURITY_CHECKLIST.md`
