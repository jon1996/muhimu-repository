# Bilan d’exécution des tests

**Date :** 2026-10-10  
**Environnement :** conteneur Docker `muhimuerp-backend-1`  
**Commande :** `docker compose exec -T backend python manage.py test apps --verbosity=2`  
**Base de données :** PostgreSQL Docker `test_muhimu` (créée puis détruite par Django)  
**Base métier `muhimu` :** non utilisée pour les assertions ; intacte après destruction de `test_muhimu`  
**Log brut :** `_test_run_raw.log`

---

## Résultat global

| Métrique | Valeur |
|---|---|
| Tests découverts | **195** |
| Réussis | **195** |
| Échoués | **0** |
| Erreurs | **0** |
| Ignorés (skipped) | **0** |
| Durée | **197,358 s** |
| Verdict Django | **OK** |

---

## Tentative locale (venv Windows) — non conclusive

| Élément | Détail |
|---|---|
| Commande | `manage.py test apps` via `.venv` |
| Résultat | **Échec avant exécution des cas** |
| Cause | `ModuleNotFoundError: No module named 'reportlab'` |
| Effet collatéral | Django a créé puis détruit `test_muhimu` pendant le check URL |
| Action | Relance dans Docker (dépendances `requirements.txt` présentes) |

**Note :** le venv local n’était pas aligné sur `requirements.txt`. Ce n’est **pas** un échec de test métier.

---

## Couverture par domaine (tests existants verts)

| Domaine | Fichiers de test | Statut run |
|---|---|---|
| Bootstrap comptes | `identity/tests/test_bootstrap_accounts.py` | OK |
| CAGE / classe 9 reflet | `test_cage.py` | OK |
| Consolidation | `test_consolidation.py` | OK |
| Seed démo | `test_demo.py` | OK |
| Échéances / immuabilité partielle | `test_due_on.py` | OK |
| Devises / FX | `test_fx.py` | OK |
| À-nouveaux | `test_opening.py` | OK |
| Auxiliaires tiers | `test_party_aux.py` | OK |
| Livres PDF | `test_pdf_books.py` | OK |
| États PDF / format montants | `test_pdf_statements.py` | OK |
| Amortissements | `test_amortization.py` | OK |
| Banque / OFX | `test_bank_rec.py`, `test_ofx.py` | OK |
| Caisse | `test_cash.py` | OK |
| Clôture helpers | `test_closing.py` | OK |
| Engagements | `test_commitments.py` | OK |
| Escompte | `test_escompte.py` | OK |
| ESG / note 35 | `test_esg.py` | OK |
| Lettrage / notes 7–17 | `test_lettering.py` | OK |
| Notes balance | `test_notes_balance.py` | OK |
| Mapping SN / TFT / CR | `test_sn_map.py` | OK |
| SMT | `test_smt.py` | OK |
| Stocks | `test_stocks.py` | OK |
| Class9 isolation écriture | `test_class9.py` | OK |
| Liasse / OHADA / identity | `tenancy/tests/*` | OK |
| Demo grants / mail | `platform/tests/*` | OK |

---

## Fonctionnalités **non couvertes** ou insuffisamment couvertes

Ces absences restent vraies **malgré** 195 tests verts :

| Zone | Manque |
|---|---|
| Concurrence posting / snapshots | Aucun test multi-thread / multi-process |
| Isolation RLS inter-organisations | Aucun test « org A vs org B » |
| Isolation société cabinet (`CompanyAccess`) | Pas de suite négative dédiée |
| CHECK SQL équilibre | Non applicable (contrainte absente) |
| Clôture annuelle E2E (`close_exercise` + affectation) | Seulement helpers (`restore_pnl`, réserve) |
| Import CSV plan comptable E2E API | Parse/unit indirect seulement |
| Import bulk écritures | Feature absente |
| Rate-limit / auth brute-force | Non testé |
| Réconciliation snapshot ↔ lignes | Absente |
| Performance 1k/10k/100k | Non exécutée |
| UX / frontend | Pas de tests e2e navigateur dans ce run |
| Backup/restore | Hors suite unitaire |

---

## Interprétation

1. **Les tests existants passent** dans l’environnement Docker isolé — bonne hygiène de revue.
2. **Vert ≠ prêt bêta :** les P0 portent surtout sur des **trous de couverture** et des risques d’exploitation, pas sur des échecs actuels.
3. Toute correction P0 doit **ajouter** les tests listés dans `P0_REMEDIATION_PLAN.md` et conserver ce bilan à 195+ OK.
