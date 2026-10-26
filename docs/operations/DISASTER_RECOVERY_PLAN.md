# Plan de reprise d’activité — MUHIMU Accounting (OPS-01)

**Statut :** lab local validé (drill restore 2026-10-12)  
**Périmètre :** perte ou corruption PostgreSQL / médias — pas encore un engagement SLA production

---

## 1. Objectifs (propositions — non garantis)

| Indicateur | Proposition bêta privée | Commentaire |
|---|---|---|
| **RPO** | ≤ 24 h | Une sauvegarde logique quotidienne minimum |
| **RTO** | ≤ 4 h | Restore + validations + bascule proxy (à confirmer en staging distant) |

Les valeurs ci-dessus sont des **cibles de conception**. Elles ne deviennent contractuelles qu’après drills réguliers sur l’environnement distant.

Mesures lab (instance locale) :

| Opération | Durée réelle |
|---|---|
| Backup PG DEV | ~6 s |
| Backup médias | ~3 s |
| Restore isolé + validations | ~17 s |

---

## 2. Scénarios

| Scénario | Détection | Réponse |
|---|---|---|
| Corruption logique DB | Erreurs app / contrôles comptables | Restore sur instance parallèle → bascule |
| Perte volume Docker hôte | Volume absent / PG refuse de démarrer | Restore depuis `backups/` hors VHDX |
| Erreur humaine DROP | Audit / alerte | Restore point-in-time si WAL (futur) ou dernier dump |
| Incident ransomware hôte | Indispo | Restaurer depuis copie **offsite** chiffrée (3-2-1) |

---

## 3. Responsabilités

| Rôle | Responsabilité |
|---|---|
| Opérateur technique | Exécuter backup/restore selon runbooks |
| Responsable produit | Décider bascule / communication clients |
| Sécurité | Gardien des secrets de déchiffrement / mots de passe rôles |

---

## 4. Gestion des secrets

- Mots de passe PG / `DJANGO_SECRET_KEY` : coffre (pas dans les dumps)  
- `BACKUP_ENCRYPTION_PASS` : coffre séparé du stockage des `.enc`  
- Rôles restaurés : reposer les passwords via env (`OPS_RESTORE_*` / `.env` cible)  
- Jamais de secret dans `docs/` ni logs d’audit texte

---

## 5. Dépendances au redémarrage

1. PostgreSQL 16 + rôles `muhimu`, `muhimu_app`, `muhimu_platform`  
2. Extension `plpgsql`  
3. Fonctions SECURITY DEFINER (`app_user_can_access_*`, `app_bypass_rls` → toujours false)  
4. Politiques RLS (FORCE)  
5. Redis (sessions rate-limit SEC-P0-01 — fail-closed si absent)  
6. Médias  
7. Images / compose application  

---

## 6. Stratégie 3-2-1 (cible distante)

1. **3 copies** : primaire + backup quotidien local + copie offsite  
2. **2 supports** : filesystem hôte + object storage  
3. **1 hors site** : compte / région distincte  

Automatisation cron / CI : hors scope lab ; à planifier avec OPS follow-up.

---

## 7. Exercices

- Drill restore **mensuel** minimum avant ouverture large  
- Conserver le rapport + `restore_validate_*.out`  
- Ne supprimer les volumes de drill qu’après autorisation

---

## 8. Liens

- [BACKUP_RUNBOOK.md](BACKUP_RUNBOOK.md)  
- [RESTORE_RUNBOOK.md](RESTORE_RUNBOOK.md)  
- [OPS01_BACKUP_RESTORE_REPORT.md](../audit/OPS01_BACKUP_RESTORE_REPORT.md)
