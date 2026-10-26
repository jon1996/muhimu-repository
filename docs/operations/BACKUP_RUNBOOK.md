# Runbook — Sauvegarde MUHIMU Accounting (OPS-01)

**Périmètre :** PostgreSQL 16 + médias Django  
**Environnements :** `dev` (`muhimuerp`) et `beta` (`muhimu-beta`) — **séparés**  
**Secrets :** jamais en arguments de ligne de commande ni dans Git

---

## 1. Prérequis

- Docker Desktop opérationnel
- Stack cible UP (`db` + `backend` pour les médias)
- Git Bash ou shell POSIX
- Espace disque : viser ≥ 3× la taille du volume PG sur **D:** (`backups/`)
- Option chiffrement : OpenSSL + variable `BACKUP_ENCRYPTION_PASS` (hors fichier versionné)

---

## 2. Contenu d’une sauvegarde

| Artefact | Description |
|---|---|
| `muhimu_<env>_<ts>.dump` | `pg_dump -Fc` (schéma, données, ACL, politiques RLS, fonctions) |
| `muhimu_<env>_<ts>_roles.sql` | DDL rôles `muhimu_app` / `muhimu_platform` **sans mots de passe** |
| `muhimu_<env>_<ts>.sha256` | Contrôle d’intégrité |
| `muhimu_<env>_<ts>.meta.json` | Compteurs + durée + checksums (pas de secrets) |
| `muhimu_<env>_media_<ts>.tar.gz` | Archive `/app/media` |
| `*.dump.enc` (optionnel) | AES-256-CBC PBKDF2 si `BACKUP_ENCRYPT=1` |

Les mots de passe PostgreSQL **ne sont jamais** inclus dans les archives.

---

## 3. Procédure — DEV

```bash
cd "/d/muhimu/muhimu ERP"   # ou chemin du dépôt
export ENV=dev
export BACKUP_ENCRYPT=0     # 1 + BACKUP_ENCRYPTION_PASS pour chiffrer
export BACKUP_RETAIN=7
sh scripts/ops/backup_all.sh
```

Vérifier :

1. Exit code 0  
2. Fichiers créés sous `backups/postgres/` et `backups/media/`  
3. `sha256` cohérent  
4. `meta.json` → `counts.debit == counts.credit`  
5. Log : `backups/logs/backup_dev_*.log`

Durée mesurée (lab 2026-10-10) : **~6 s** dump PG + **~3 s** médias.

---

## 4. Procédure — Bêta

```bash
export ENV=beta
# Charger .env.beta dans le shell UNIQUEMENT si nécessaire pour compose ;
# préférer : docker compose --env-file .env.beta (déjà géré par le script).
sh scripts/ops/backup_all.sh
```

Ne pas confondre avec DEV : bases `muhimu` ≠ `muhimu_beta`, volumes distincts.

---

## 5. Chiffrement

```bash
export BACKUP_ENCRYPT=1
export BACKUP_ENCRYPTION_PASS='…'   # généré hors bande, coffre secrets
export BACKUP_REMOVE_PLAINTEXT=1    # supprime le .dump en clair après .enc
sh scripts/ops/backup_postgres.sh
```

Algorithme : `openssl enc -aes-256-cbc -pbkdf2 -iter 200000`.

---

## 6. Rétention

- Défaut : **7** jeux (`BACKUP_RETAIN`) les plus récents par env  
- Stratégie cible distante **3-2-1** :
  1. 3 copies (prod + offsite + cold)  
  2. 2 supports (disque + objet cloud)  
  3. 1 copie hors site / hors compte cloud principal  

---

## 7. Journalisation / alertes

- Logs : `backups/logs/`  
- En cas d’échec : exit ≠ 0 + message `ERROR:`  
- Alerte ops (à brancher OPS follow-up) : surveiller exit code CI / cron + présence du `.meta.json` du jour

---

## 8. Interdits

- Ne pas versionner `backups/` (déjà dans `.gitignore`)  
- Ne pas coller de mots de passe dans les scripts  
- Ne pas considérer le volume Docker seul comme sauvegarde  
- Ne pas écraser la sauvegarde de référence sans copie
