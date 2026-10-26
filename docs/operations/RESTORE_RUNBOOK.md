# Runbook — Restauration MUHIMU Accounting (OPS-01)

**Règle d’or :** ne jamais restaurer sur les volumes `muhimuerp_postgres_data` ou `muhimu-beta_postgres_beta_data` sans décision de crise documentée.

Le drill standard utilise un projet **isolé** : `muhimu-ops-restore` + volume `muhimu_ops_restore_pgdata`.

---

## 1. Prérequis

| Élément | Valeur |
|---|---|
| Dump | `backups/postgres/muhimu_<env>_<ts>.dump` (+ `.sha256`) |
| Rôles | `…_roles.sql` (sans passwords) |
| Compose | `docker-compose.ops-restore.yml` |
| Secrets restore | `OPS_RESTORE_APP_PASSWORD`, `OPS_RESTORE_PLATFORM_PASSWORD` (env) |
| Port hôte | `5439` (défaut) — distinct de DEV `5433` |

---

## 2. Drill de restauration (lab)

```bash
export OPS_RESTORE_APP_PASSWORD='…'
export OPS_RESTORE_PLATFORM_PASSWORD='…'
export OPS_RESTORE_PG_PASSWORD='…'   # ignoré si volume déjà initialisé
export DUMP=backups/postgres/muhimu_dev_YYYYMMDD_HHMMSS.dump
export ROLES=${DUMP%.dump}_roles.sql
sh scripts/ops/restore_drill.sh
```

Sous Windows PowerShell : `scripts/ops/_launch_restore.ps1` (génère des mots de passe temporaires).

### Étapes automatisées

1. Vérification checksum SHA-256  
2. Démarrage cluster Postgres 16 isolé  
3. `DROP/CREATE DATABASE muhimu_restore` (volume temp **conservé**)  
4. Création rôles `muhimu_app` / `muhimu_platform`  
5. Pose des mots de passe depuis l’environnement  
6. `pg_restore --no-owner`  
7. Grants schéma  
8. Validations SQL (`scripts/ops/validate_restored.sql`)

Durée mesurée (lab 2026-10-12) : **~17 s**.

---

## 3. Vérifications post-restauration

| Contrôle | Attendu |
|---|---|
| Tables public | ≥ 30 (typ. 42) |
| RLS FORCE | 32 |
| Politiques | 32 |
| Compteurs | = `meta.json` du dump |
| Σ débit / Σ crédit | égaux, imbalance 0 |
| Écritures déséquilibrées | 0 |
| Lignes orphelines | 0 |
| `muhimu_app` BYPASSRLS | false |
| `muhimu_platform` BYPASSRLS | true |
| `SET ROLE muhimu_platform` depuis app | refusé |
| `app_bypass_rls()` après forge GUC | false |

---

## 4. Ordre de restauration des composants (cible distante)

1. Secrets / `.env` (coffre) — **hors dump**  
2. Cluster PostgreSQL vierge + rôles  
3. `pg_restore` base applicative  
4. Médias (`tar xz` vers `MEDIA_ROOT`)  
5. Redis (cache volatile — pas de restore métier requis)  
6. Backend / platform (Gunicorn)  
7. Frontend / console  
8. Proxy TLS  
9. Smoke : `/api/health`, login, balance société démo

---

## 5. Retour arrière

| Situation | Action |
|---|---|
| Drill lab échoué | Conserver le volume temp ; corriger ; rejouer `restore_drill.sh` (recrée la DB) |
| Prod (futur) | Ne basculer le DNS / proxy qu’après validations ; conserver l’ancien volume jusqu’à GO |
| Fausse bascule | Repointer le proxy vers l’ancien stack ; **ne pas** `docker volume rm` |

---

## 6. Suppression des ressources temporaires

**Interdit sans autorisation explicite.**

Ressources du drill :

- Projet Compose : `muhimu-ops-restore`  
- Volume : `muhimu_ops_restore_pgdata`  
- Réseau : `muhimu_ops_restore_net`  
- Port hôte : `5439`

Arrêt sans destruction :

```bash
docker compose -p muhimu-ops-restore -f docker-compose.ops-restore.yml down
# SANS -v
```
