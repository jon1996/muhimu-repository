# ACC-03 — Rapport de promotion contrôlée vers DEV

**Date :** 2026-10-13  
**Cible :** DEV uniquement — projet Compose `muhimuerp`, base `muhimu`, conteneur `muhimuerp-db-1`  
**Bêta :** **hors périmètre** — non migrée  
**Verdict :** **GO** — migration `ledger.0033_acc03_sql_integrity` **appliquée sur DEV**

---

## 1. Inspection (étape 1)

| Contrôle | Résultat |
|---|---|
| SQL destructif non prévu (DROP DATA / TRUNCATE) | **Absent** — DDL triggers/functions uniquement |
| Modification RLS / POLICY | **Absente** |
| Contournement GUC | **Absent** |
| Propriétaires fonctions (labo) | `muhimu` (superuser migrate) |
| Triggers UPDATE/DELETE/INSERT | Conformes (immutabilité + équilibre) |
| Cascade brouillon | Conservée (DELETE draft autorisé) |
| Annotations whitelist | `due_on`, `lettering`, `bank_pointage`, `third_party_id` |
| ACC-02 / `post_entry` / `reverse_entry` | Compatibles (pas de mutation rétroactive) |

Fichier : `backend/apps/ledger/migrations/0033_acc03_sql_integrity.py`

---

## 2. Sauvegarde DEV (étape 2)

| Élément | Valeur |
|---|---|
| Dump | `backups/postgres/muhimu_dev_20261013_014859.dump` |
| Format | custom (`pg_dump -Fc --no-owner`) |
| Taille | 537 386 octets |
| SHA-256 | `fd942eea76bf2e703906d5a91715e7b59f143fa385b99ed0ce2c9f08e13aca0e` |
| TOC `pg_restore -l` | **553** lignes |
| Rôles (sans mots de passe) | `muhimu_dev_20261013_014859_roles.sql` |
| Meta | `muhimu_dev_20261013_014859.meta.json` |
| Checksums | `muhimu_dev_20261013_014859.sha256` |

**Sauvegardes OPS-01 conservées** (non remplacées) :

- `muhimu_dev_20261010_025933.dump`
- `muhimu_dev_20261010_044901.dump` (+ `.enc`, meta, sha256, roles)

---

## 3. Précontrôles comptables DEV (étape 3 — lecture seule)

| Indicateur | Valeur | Statut |
|---|---|---|
| Écritures POSTED | 10 | OK |
| Brouillons | 0 | OK |
| Lignes | 22 | OK |
| POSTED déséquilibrées | **0** | OK |
| POSTED sans lignes | **0** | OK |
| Lignes orphelines | **0** | OK |
| Lignes débit+crédit | **0** | OK |
| Lignes montant nul | **0** | OK |
| Incohérences company/org | **0** | OK |
| Compte ≠ société ligne | **0** | OK |
| Doublons (journal, exercice, number) | **0** | OK |
| Σ débit / Σ crédit | 1 037 200 / 1 037 200 | OK |
| Policies RLS entry/line | 2 présentes | OK |
| Triggers ACC-03 avant migrate | 0 | Attendu |

**Aucune anomalie** → poursuite autorisée.

---

## 4. Répétition sur copie isolée (étape 4)

Environnement : `docker-compose.acc03-dev-promote.yml`  
Projet : `muhimu-acc03-promote` · port **5441** · volume `muhimu_acc03_promote_pgdata` (conservé, `down` sans `-v`)  
≠ OPS-01, ≠ ACC-03 lab précédent, ≠ DEV/bêta.

| Étape | Résultat |
|---|---|
| Restore dump DEV | OK (10 écritures, 22 lignes, Σ 1 037 200) |
| Empreinte avant migrate | entries `dd16d781…` · lines `0682ef08…` |
| `migrate ledger 0033` | **OK** |
| Empreinte après migrate | **Identique** |
| 4 triggers présents | OK |
| RLS entry/line | 2 policies inchangées |
| Rollback `migrate ledger 0032` | OK (0 trigger) · empreintes **identiques** |
| Re-apply 0033 | OK (4 triggers) |
| Tests ACC-03/02/01 | **54 OK** |
| Suite `apps` | **309 OK** |

---

## 5. Décision avant migration DEV (étape 5)

| Contrôle | Résultat |
|---|---|
| Identité base | `current_database() = muhimu` · projet `muhimuerp` |
| ≠ bêta | Confirmé (périmètre DEV uniquement) |
| Précontrôles | Tous verts |
| Répétition | GO |
| Connexions actives | 1 backend sur `muhimu` (nominal) |
| Bootstrap démo | **Non lancé** |

**Décision :** exécuter `migrate ledger 0033_acc03_sql_integrity` sur DEV.

---

## 6. Migration DEV appliquée (étape 5–6)

```text
docker compose -p muhimuerp exec -T backend \
  python manage.py migrate ledger 0033_acc03_sql_integrity --noinput
→ Applying ledger.0033_acc03_sql_integrity... OK
→ applied 2026-10-13 00:34:28.500735+00
```

### Post-vérifications DEV

| Contrôle | Résultat |
|---|---|
| Migration 0033 enregistrée | Oui |
| 4 triggers `trg_ledger_*` | Actifs |
| RLS entry/line | Intactes |
| `muhimu_app` | NOSUPERUSER, **NOBYPASSRLS** |
| Empreintes entries/lines | **Inchangées** (`dd16d781…` / `0682ef08…`) |
| Σ D/C | 1 037 200 / 1 037 200 |
| POSTED déséquilibrées | 0 |
| API health | `{"status": "ok"}` · backend healthy |
| Tests applicatifs post-migrate (test DB) | ACC-03/02/due_on **50 OK** |

Lettrage / pointage / échéances / contrepassation couverts par la suite ACC-03/02 (données de test, pas de mutation des historiques DEV).

---

## 7. État des environnements

| Environnement | ACC-03 0033 | Notes |
|---|---|---|
| **DEV** (`muhimu` / muhimuerp) | **Appliquée** | Données historiques inchangées |
| **Bêta** | **Non migrée** | Hors périmètre |
| Lab promote | Volume conservé | Stack arrêtée (`down` sans `-v`) |
| Lab ACC-03 initial | Volume `muhimu_acc03_pgdata` | Inchangé |

---

## 8. Anomalies

Aucune. Aucune correction de données effectuée.

---

## 9. Rollback DEV (si besoin)

```bash
docker compose -p muhimuerp exec -T backend \
  python manage.py migrate ledger 0032_a1_prime_rls_company --noinput
```

Sauvegarde de secours : `backups/postgres/muhimu_dev_20261013_014859.dump`  
SHA-256 : `fd942eea76bf2e703906d5a91715e7b59f143fa385b99ed0ce2c9f08e13aca0e`

---

## 10. Verdict final

**GO — ACC-03 promu sur DEV avec succès.**

- CLOSE-01 / PDF-CLAIM : non démarrés  
- Bêta : non touchée  
- Prochaine étape éventuelle : promotion bêta **uniquement sur autorisation séparée**
