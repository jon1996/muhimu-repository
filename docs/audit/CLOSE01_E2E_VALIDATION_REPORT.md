# CLOSE-01 — Validation E2E de la clôture comptable

**Date :** 2026-10-13  
**Nature :** tests + correctifs techniques documentés · **pas** de changement de règles SYSCOHADA  
**Données DEV/bêta :** non modifiées (exécution sur `test_muhimu` uniquement)  
**Réouverture :** politique **R0 + R2** (aucun REOPEN self-service)

**Verdict :** **GO**

---

## 1. Cartographie du processus

```text
OPEN
  │  preview_close (blockers : CLOSED, brouillons, dernière période ≠ OPEN)
  ▼
close_exercise  ──► OD source=result_close (6/7/8 → 131|139) si mouvements PNL
  │                 status=CLOSED · net_result / revenue
  │                 ensure_company_ledger(N+1)
  │                 select_for_update(exercise)  [CLOSE-01]
  ▼
CLOSED
  │  allocate_result (AGO) → écritures sur N+1 (111/118/121/465 ou 129)
  │  post_opening(N+1) → journal AN (BS + 13 ; pas de 6/7/8)
  ▼
N+1 OPEN (corrections éventuelles R2 sur N+1 uniquement)
```

| Élément | Implémentation |
|---|---|
| Statuts exercice | `OPEN` · `CLOSING` (enum inutilisé) · `CLOSED` |
| Statuts période | `OPEN` · `VALIDATED` · `IT_CLOSED` (non chaînés par close) |
| Prévisualisation | `preview_close` |
| Arrêté | classes **6/7/8** → **131** (bénéfice) / **139** (perte) |
| Affectation | `allocate_result` après CLOSED |
| À-nouveaux | `post_opening` (exercice N+1 ouvert) |
| Irréversible | status CLOSED ; POSTED immuables (ACC-02/03) ; pas de reopen |
| Autorisation API | `require_writer` (OWNER/ADMIN/ACCOUNTANT) |
| Isolation | exercice filtré par `company` |

### Transitions / opérations irréversibles

1. `CLOSE` : pose `CLOSED` + OD d’arrêté (idempotency `close:{id}:{net}`).  
2. `ALLOCATE` : une seule fois (`allocation_entry_id`).  
3. Toute mutation substance des écritures POSTED : refus ORM + SQL.  
4. `post_entry` / `post_opening` sur exercice CLOSED : refus.

---

## 2. Correctifs techniques (portée documentée)

| ID | Changement | Justification | Règle comptable ? |
|---|---|---|---|
| CLOSE-01-T1 | `trial_balance_ytd` + usage dans `preview_close` / `close_exercise` | `trial_balance(décembre)` ignorait les mouvements des mois antérieurs (snapshots absents) → résultat de clôture faux si écritures en janvier | **Non** — lecture du cumul annuel pour l’arrêté existant |
| CLOSE-01-T2 | `select_for_update` sur l’exercice dans `close_exercise` | Deux clôtures concurrentes pouvaient passer le précontrôle | **Non** — verrou technique |

Fichiers : `services/balance.py`, `services/closing.py`.

---

## 3. Scénarios E2E et résultats

Fichier : `apps/ledger/tests/test_close_e2e.py` (**19** tests).

Jeux fictifs XOF (attendus indépendants) :

| Scénario | Attendu indépendant | Résultat |
|---|---|---|
| 01 Clôture équilibrée / bénéfice | XI = 2 100 000 − 1 800 000 − 200 000 = **100 000** ; OD D=C ; 6/7 soldés ; 131 = 100 000 C | OK |
| 02 Bénéfice = cr_amounts YTD | XI = 100 000 | OK |
| 03 Perte | XI = **−300 000** ; 139 débiteur | OK |
| 04 Sans opérations PNL | XI = 0 ; pas d’OD `result_close` ; CLOSED | OK |
| 05 Brouillons ouverts | refus 409 | OK |
| 06 Seconde clôture | refus 409 ; 1 seule OD | OK |
| 07 Post après CLOSED | refus | OK |
| 08 Affectation bénéfice | légale 10 000 + RAN 90 000 = 100 000 ; sur N+1 | OK |
| 09 AN N+1 | 521/101/131 ; pas de 6/7 ; puis allocate | OK |
| 10 Isolation 2 sociétés | A clôturée ≠ B | OK |
| 11 Rollback transactionnel | pas de CLOSE partiel | OK |
| 12 Concurrence 4 threads | **1** succès ; 1 OD | OK |
| 13 Immutabilité ACC-02/03 | update ORM + SQL refusés sur OD clôture | OK |
| 14 Reverse ≠ réouverture | N reste CLOSED ; origine intacte | OK |
| 15 Pas de REOPEN | `reopen_exercise` absent ; AN sur CLOSED refusé | OK |
| 16 Affectation perte → 129 | OK | OK |
| 17 Snapshots ACC-01 | mov période = SUM lignes | OK |
| 18 API viewer 403 ; cross-company | autre société reste OPEN | OK |
| 19 YTD vs décembre | décembre vide ≠ YTD 100 000 | OK |

---

## 4. Intégration ACC-02 / ACC-03

| Contrôle | Statut |
|---|---|
| Écritures POSTED immuables après clôture | OK |
| Triggers SQL n’empêchent pas close/allocate/AN légitimes | OK |
| OD clôture équilibrée (D=C) | OK |
| Contrepassation ne réouvre pas N | OK |
| Rollback atomic | OK |
| Triggers non désactivés | OK |

---

## 5. Sécurité et concurrence

| Test | Résultat |
|---|---|
| 4 clôtures simultanées | 1 OK + refus ; pas de doublon OD |
| Viewer → POST `/ledger/exercise/close` | **403** |
| Clôture société active ≠ autre société | Autre reste OPEN |
| Modification après CLOSED | Refus post + immutabilité |

**Aucune anomalie bloquante** de concurrence ou d’autorisation détectée après T2.

---

## 6. Réouverture (R0 + R2)

- Aucun mécanisme `reopen_exercise` ajouté.  
- Corrections éventuelles : écritures sur **N+1** uniquement.  
- Modification rétroactive des POSTED : interdite.

---

## 7. Non-régression

| Suite | Résultat |
|---|---|
| CLOSE-01 E2E | **19 OK** |
| ACC-01 / ACC-02 / ACC-03 / due_on / SAAS-03 | Inclus |
| `manage.py test apps` (+ CLOSE-01) | **328 OK** (~447 s) |

Environnement : PostgreSQL via conteneur backend DEV · base temporaire `test_muhimu` · **0** écriture sur `muhimu` DEV métier (toujours 10 POSTED historiques).

---

## 8. Fichiers modifiés / ajoutés

| Fichier | Action |
|---|---|
| `backend/apps/ledger/services/balance.py` | `trial_balance_ytd` |
| `backend/apps/ledger/services/closing.py` | YTD + `select_for_update` |
| `backend/apps/ledger/tests/test_close_e2e.py` | **Nouveau** — 19 scénarios |
| `docs/audit/CLOSE01_E2E_VALIDATION_REPORT.md` | Ce rapport |

---

## 9. Risques résiduels

| Risque | Niveau | Note |
|---|---|---|
| `ExerciseStatus.CLOSING` non utilisé | P3 | Fenêtre intermédiaire absente |
| IT-close périodes non chaîné à la clôture annuelle | P2 | Manuel via `it_close_period` |
| `trial_balance` mensuel inchangé (hors clôture) | Info | Seule la clôture utilise YTD |
| Mapping SN / réserve légale 10 %–20 % | VAL_METIER | Toujours EC (SYSCO-01) |
| AN manuel (pas d’auto depuis balance clôture) | P2 | UX / assistant futur |

---

## 10. Questions expert-comptable

1. L’arrêté doit-il exiger la clôture IT de toutes les périodes 1–11 avant l’OD de décembre ?  
2. Enchaînement prescrit : AN puis affectation, ou affectation puis AN ?  
3. La suggestion de réserve légale 10 % / plafond 20 % du capital est-elle acceptable pour la bêta PME ?  
4. Un exercice sans mouvement PNL doit-il produire une OD nulle ou seulement le statut CLOSED (comportement actuel) ?

---

## 11. Verdict

**GO** — le cycle clôture → affectation → à-nouveaux N+1 est démontré E2E sans incohérence comptable sur jeux fictifs, avec ACC-02/03 actifs et isolation multi-sociétés.

- PDF-CLAIM : non démarré  
- Mapping SYSCOHADA : non modifié  
- Bêta / données historiques DEV : non touchées
