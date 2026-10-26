# OPS-01 — Sauvegarde, restauration et plan de reprise

**Date :** 2026-10-12 (drill) / préparation 2026-10-10  
**Périmètre :** lab local — **aucun déploiement distant**  
**Prérequis :** ACC-01, SAAS-03, ARCH-01, SEC-P0-01 ; suite **265** tests

---

## 1. Verdict

| Domaine | Verdict |
|---|---|
| Audit sources DEV / bêta | **GO** |
| Scripts backup (PG + médias + checksum + rétention) | **GO** |
| Chiffrement optionnel AES-256 | **GO** (démo `.dump.enc`) |
| Drill restore isolé | **GO** (~17 s) |
| Intégrité comptable restaurée | **GO** (match `meta.json`) |
| Sécurité RLS / rôles sur base restaurée | **GO** |
| Non-régression 265 + OPS guards + SEC spot | **GO** |
| Automatisation 3-2-1 distante / cron | **Non fait** (documenté) |

### Verdict global OPS-01 : **GO** (lab local)

Production distante : **NO-GO** jusqu’à drills hébergés + rétention offsite.

---

## 2. Phase 1 — Audit

### Bases

| Env | Projet | DB | Volume | Port hôte |
|---|---|---|---|---|
| DEV | `muhimuerp` | `muhimu` | `muhimuerp_postgres_data` | 5433 |
| Bêta | `muhimu-beta` | `muhimu_beta` | `muhimu-beta_postgres_beta_data` | non publié |
| Drill | `muhimu-ops-restore` | `muhimu_restore` | `muhimu_ops_restore_pgdata` | 5439 |

### PostgreSQL (DEV, lecture seule)

| Élément | Valeur |
|---|---|
| Version | 16.15 |
| Extension | `plpgsql` |
| Tables public | 42 |
| RLS FORCE | 32 |
| Politiques | 32 |
| SECURITY DEFINER | `app_user_can_access_company`, `app_user_can_access_consolidation_group`, `app_user_is_org_admin` (+ `app_bypass_rls` → toujours false) |
| `muhimu_app` | NOSUPERUSER, **NOBYPASSRLS** |
| `muhimu_platform` | NOSUPERUSER, **BYPASSRLS** |

### Médias

| Env | Chemin conteneur | Taille approx. |
|---|---|---|
| DEV | `/app/media` (bind) | ~200 Ko |
| Bêta | volume `beta_media` | ~212 Ko |

### Sauvegarde préexistante (non modifiée)

`backups/postgres/muhimu_dev_20261010_025933.dump` (537 386 o, TOC 553) — **conservée**.

### Risques identifiés (avant OPS-01)

- Volume Docker ≠ backup  
- Pas de drill restore prouvé  
- Pas de chiffrement / rétention formalisée  
- Redis volatile (OK) ; rate-limit SEC dépend de Redis disponible

---

## 3. Architecture de sauvegarde

```
ENV=dev|beta
  → pg_dump -Fc  (+ roles.sql sans passwords)
  → tar médias
  → sha256 + meta.json (compteurs comptables)
  → optionnel: openssl AES-256-CBC (.enc)
  → rétention N=7
```

Scripts :

| Script | Rôle |
|---|---|
| `scripts/ops/backup_postgres.sh` | Dump + rôles + meta |
| `scripts/ops/backup_media.sh` | Archive médias |
| `scripts/ops/backup_all.sh` | Orchestration |
| `scripts/ops/restore_drill.sh` | Restore isolé |
| `scripts/ops/validate_restored.sql` | Contrôles SQL |
| `scripts/ops/test_ops_guards.sh` | Garde-fous (8) |
| `docker-compose.ops-restore.yml` | Cluster temp |

---

## 4. Résultats backup (DEV 2026-10-10)

| Mesure | Valeur |
|---|---|
| Fichier | `muhimu_dev_20261010_044901.dump` |
| Taille | 537 386 o |
| SHA-256 | `a3a9918612883c10ea323d2c8df78911af0faa8cf81e467cf1300c2450da0e8d` |
| Durée PG | **6 s** |
| Médias | `muhimu_dev_media_20261010_044910.tar.gz` (166 988 o, **3 s**) |
| Chiffrement démo | `…dump.enc` (537 408 o) — passphrase **non stockée** |

### Compteurs source (`meta.json`)

| orgs | companies | journals | entries | lines | snapshots | users | débit | crédit |
|---|---|---|---|---|---|---|---|---|
| 4 | 5 | 35 | 10 | 22 | 16 | 3 | 1 037 200 | 1 037 200 |

---

## 5. Résultats restore drill (2026-10-12)

| Mesure | Valeur |
|---|---|
| Cible | `muhimu_restore` sur volume **temp** uniquement |
| Durée | **17 s** |
| Tables | 42 |
| Compteurs | **identiques** au `meta.json` |
| Imbalance débit/crédit | **0** |
| Écritures déséquilibrées | **0** |
| Lignes orphelines | **0** |
| SET ROLE platform depuis app | **refusé** |
| `app_bypass_rls` après forge GUC | **false** |

DEV après drill : orgs=4, entries=10, débit=crédit=1 037 200 — **inchangé**.

---

## 6. Tests

| Suite | Résultat |
|---|---|
| `test_ops_guards.sh` | 8/8 OK |
| Django complète | **265 OK** (~471 s) |
| SEC-P0-01 spot (throttle redis, max_email=5) | OK |
| DEV `/api/health` + bêta HTTPS health | 200 |

---

## 7. RPO / RTO proposés

| | Proposition bêta | Mesure lab |
|---|---|---|
| RPO | ≤ 24 h | Backup manuel prouvé |
| RTO | ≤ 4 h | Restore lab 17 s (hors bascule DNS) |

Non contractuel avant drills distants.

---

## 8. Risques résiduels

1. Pas de copie offsite / 3-2-1 automatisé  
2. Pas de PITR (WAL) — restore = dernier dump  
3. Mots de passe rôles à reposer manuellement depuis coffre  
4. Volume drill encore présent (attente autorisation suppression)  
5. Stack DEV redémarrée avec override runserver-only (compose principal migrate+bootstrap toujours présent)

---

## 9. Ressources temporaires — état après clôture (2026-10-12)

Arrêt contrôlé autorisé : `docker compose -p muhimu-ops-restore -f docker-compose.ops-restore.yml down` (**sans** `-v`).

| Ressource | Identifiant | État final |
|---|---|---|
| Projet Compose | `muhimu-ops-restore` | **arrêté** (plus de conteneurs) |
| Conteneur | `muhimu-ops-restore-db-1` | **supprimé** (conteneur uniquement) |
| Réseau | `muhimu_ops_restore_net` | **supprimé** |
| Port hôte | `5439` | **libéré** |
| Volume | `muhimu_ops_restore_pgdata` | **conservé** (données drill intactes) |

Vérifications post-arrêt :
- Volume `muhimu_ops_restore_pgdata` toujours listé ; non monté par DEV/bêta.  
- Volumes `muhimuerp_postgres_data` et `muhimu-beta_postgres_beta_data` intacts.  
- DEV + bêta healthy ; `/api/health` 200.  
- Sauvegardes / `.enc` / `.sha256` / `.meta.json` / logs / médias : **présents**.  

**Suppression du volume** `muhimu_ops_restore_pgdata` : **non effectuée** — nécessite une autorisation ultérieure.

---

## 10. Livrables

- `docs/audit/OPS01_BACKUP_RESTORE_REPORT.md` (ce fichier)  
- `docs/operations/BACKUP_RUNBOOK.md`  
- `docs/operations/RESTORE_RUNBOOK.md`  
- `docs/operations/DISASTER_RECOVERY_PLAN.md`

---

## 11. Suite

- Attente instructions pour **suppression** (ou conservation) des ressources temp  
- OPS follow-up : cron backup, offsite, alerte échec  
- Aucun démarrage d’autres modules ERP
