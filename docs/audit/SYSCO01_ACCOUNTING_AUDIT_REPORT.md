# SYSCO-01 — Rapport d’audit fonctionnel comptable (lecture seule)

**Date :** 2026-10-12  
**Nature :** audit **read-only** — aucun correctif métier, aucune modification de données  
**Avertissement :** ce document **n’est pas** une certification SYSCOHADA / AUDCIF / PCGO.

**Sources internes utilisées :** `docs/ledger.md`, `docs/audit/SYSCOHADA_COMPLIANCE_MATRIX.md`, code `apps/ledger/**`, tests ledger, backlog P0/SYSCO-01.  
**Source normative citée dans le dépôt :** Acte uniforme AUDCIF + Système comptable OHADA (PCGO) — document de travail référencé par `docs/ledger.md` (1204 pages). Aucune règle OHADA inventée hors de ces références.

---

## 1. Verdict

| Question | Réponse |
|---|---|
| Moteur de tenue (partie double, journaux, GL, balance, snapshots) | **Opérationnel** (preuves techniques) |
| Liasse SN / SMT (bilan, CR, TFT, notes) | **Implémentée partiellement** — **non attestée** |
| Validation expert-comptable écrite | **Absente** |
| Bêta comptable avec **données fictives** | **CONDITIONAL GO** |
| Communication « conforme / certifié SYSCOHADA » | **NO-GO** |

### Verdict global SYSCO-01 (phase audit) : **CONDITIONAL GO**

Autorisable pour une **bêta privée à données fictives**, sous réserves explicites (§7), **après** lecture du pack EC et sans claim de conformité.

---

## 2. Présentation du logiciel (périmètre audit)

MUHIMU Accounting est un SaaS multi-tenant (Django Ninja + Next.js) orienté comptabilité des **entreprises commerciales / artisanales / de services** des États membres OHADA (liste `tenancy/ohada.py` : 17 pays, devises XOF/XAF/KMF/CDF/GNF).

Hors périmètre v1 documenté : banques, microfinance, assurances, NPO, etc. (AUDCIF art. 5 al. 4 — `docs/ledger.md`).

---

## 3. Inventaire des fonctionnalités (réellement dans le code)

Légende : **C** = complète (cœur + tests) · **P** = partielle · **A** = absente · **NV** = non vérifiée / validation métier requise

| Domaine | État | Preuve principale | Tests |
|---|---|---|---|
| Plan comptable général OHADA (PCGO 1–8) | **C** (catalogue) | `pcgo.py` (~1396 comptes), `setup.sync_official_accounts` | engines / demo |
| Classe 9 / CAGE | **P** | `cage.py`, `commitments.py` | `test_cage`, `test_class9`, `test_commitments` |
| Journaux OD/AC/VT/BQ/CA (+ AN) | **C** | `DEFAULT_JOURNALS`, `Journal` | books / demo |
| Saisie brouillon | **C** | `create_draft` / `update_draft` | engines |
| Validation / comptabilisation | **C** (app) | `post_entry`, `assert_double_entry` | nombreux |
| Grand livre | **C** | `general_ledger`, PDF | `test_pdf_books` |
| Balance générale | **C** | `trial_balance`, snapshots | opening, books, ACC-01 |
| Balance auxiliaire | **P** | lettrage / open items | `test_lettering` |
| États SN (bilan, CR/SIG, TFT) | **P** / **NV** | `sn_map.py`, `statements.py` | `test_sn_map` |
| Notes annexes | **P** | `notes_sn`, `notes_balance` | plusieurs |
| SMT | **P** / **NV** | `smt_map.py` | `test_smt` |
| Exercices / périodes | **C** | `Exercise`, `AccountingPeriod` | engines |
| Ouverture / AN | **C** | `opening.py` | `test_opening` |
| Clôture annuelle + affectation | **P** | `closing.py` | helpers `test_closing` — **pas d’E2E close** |
| Réouverture exercice | **A** | — | — |
| Immobilisations / amort. linéaire | **P** | `assets.py`, `amortization.py` | `test_amortization` |
| Devises / écarts de change | **C** (moteur) | `fx.py` | `test_fx` |
| TVA / déclarations nationales | **A** (hors périmètre) | identité fiscale seulement | — |
| Exports / livres PDF | **C** | `pdf_books.py`, `pdf_statements.py` | PDF tests |
| Piste d’audit applicative | **P** | `apps.audit` + sceau période | partiel |
| Multi-sociétés + RLS | **C** (tech) | tenancy + migrations RLS | SAAS-03 |
| Stocks / inventaire | **P** | `stocks.py` | `test_stocks` |
| Trésorerie opérationnelle (caisse, banque, OFX) | **P** | `cash.py`, `bank_rec.py`, `ofx.py` | tests dédiés |
| Consolidation / combinaison | **P** | `consolidation.py` | `test_consolidation` |

---

## 4. Synthèse des écarts majeurs

| ID | Gravité | Écart |
|---|---|---|
| SYSCO-01 | **P0 métier** | Mapping liasse SN/SMT **non validé** par EC |
| CLOSE-01 | **P1** | Pas de test E2E `close_exercise` + affectation complète |
| REOPEN-01 | **P1** | Réouverture d’exercice absente |
| ACC-02 | **P1** | Immutabilité contournable via `.update()` ORM |
| ACC-03 | **P1** | Pas de CHECK SQL d’équilibre |
| TAX-01 | **P2** (hors scope) | Pas de moteur TVA national |
| NOTES-01 | **P1** | Exhaustivité notes annexes partielle |
| SMT-01 | **P1** | Seuils / classification trésorerie à faire confirmer |

Détail priorisé : voir § risques dans ce rapport et la matrice `SYSCO01_REQUIREMENTS_MATRIX.md`.

---

## 5. Couverture des tests comptables

- Suite globale produit : **265** tests (session OPS-01).  
- Modules ledger : ~25 fichiers `test_*.py` (SN, SMT, opening, closing helpers, FX, amortissement, PDF, stocks, etc.).  
- Preuves fortes : partie double applicative, snapshots (ACC-01), ouverture AN, FX, mapping unitaire SN.  
- Preuves faibles / absentes : clôture E2E, réouverture, TVA, attestation EC, exhaustivité notes.

---

## 6. Contrôles d’intégrité (état technique)

| Contrôle | Implémentation | Limite |
|---|---|---|
| Équilibre D/C | `assert_double_entry` à la validation | Pas de contrainte SQL |
| Écritures déséquilibrées | Refus HTTP 400 | Contournement DB hors API |
| Soldes / snapshots | `BalanceSnapshot` + verrou | Pas de job de réconciliation continue |
| Balance vs grand-livre | Mêmes sources de mouvements | À valider EC sur jeux fictifs |
| Périodes clôturées | Report art. 22-4 vers période ouverte | Peu de tests dédiés |
| Exercice CLOSED | `post_entry` refuse | Status `CLOSING` peu utilisé |
| Traçabilité | AuditLog + contrepassation | Pas de diff ligne à ligne |
| Immutabilité postée | `save()` bloqué | `.update()` / SQL brut |
| RAN / ouverture | `opening.py` | — |
| Isolation sociétés | RLS + middleware | Validé SAAS-03 |
| Arrondis devises | `money.quantize_amount` | — |

---

## 7. Réserves pour une bêta fictive (CONDITIONAL GO)

1. Afficher clairement : **données fictives / non attestation SYSCOHADA**.  
2. Ne pas communiquer « conforme SYSCOHADA ».  
3. Limiter les pilotes à des jeux contrôlés (XOF commerce, CDF services recommandés).  
4. Exiger revue EC des liasses générées avant élargissement.  
5. Ne pas s’appuyer sur le logiciel pour des déclarations fiscales TVA nationales.  
6. Traiter immédiatement tout écart P0/P1 signalé par l’EC (correctifs **sur autorisation**).

---

## 8. Livrables associés

| Fichier | Contenu |
|---|---|
| `SYSCO01_REQUIREMENTS_MATRIX.md` | Matrice exigences / couverture |
| `SYSCO01_TEST_SCENARIOS.md` | 18 scénarios chiffrés (attendu indépendant) |
| `SYSCO01_FINANCIAL_STATEMENTS_REVIEW.md` | Revue états SN/SMT |
| `SYSCO01_EXPERT_VALIDATION_PACK.md` | Dossier EC + grille de signature |

---

## 9. Risques et priorités (correctifs proposés — non implémentés)

### P0 — Intégrité financière / conformité majeure

| ID | Risque | Correctif proposé (non fait) |
|---|---|---|
| SYSCO-01 | Liasse SN/SMT affichée sans attestation EC → risque d’erreur de presentation financière | Revue EC + ajustement `sn_map` / `smt_map` uniquement après autorisation ; retirer claims « conforme » des PDF |

### P1 — Écart significatif

| ID | Risque | Correctif proposé (non fait) |
|---|---|---|
| CLOSE-01 | Clôture / affectation peu prouvée | Tests E2E `close_exercise` + jeux scénarios 15–16 |
| REOPEN-01 | Impossible de réouvrir un exercice | Spécifier flux de réouverture contrôlé (droit + piste d’audit) |
| ACC-02 | Contournement immutabilité via ORM `.update()` | Intercepter `QuerySet.update` / couche service unique |
| ACC-03 | Pas de CHECK SQL D=C | Contrainte DB ou trigger d’équilibre (après analyse perf) |
| NOTES-01 | Notes annexes incomplètes | Compléter notes minimales retenues par EC |
| SMT-01 | Seuils SMT / devise ambiguës | Clarifier F CFA vs multi-devise ; tests seuils |

### P2 — Amélioration fonctionnelle

| ID | Risque | Correctif proposé (non fait) |
|---|---|---|
| TAX-01 | Pas de TVA déclarative nationale | Module fiscal pays (hors SYSCOHADA strict) ou exclusion produit claire |
| A04 / stocks | Inventaire annuel partiel | Campagnes inventaire + transcription livre |
| A18 | Clôture IT trimestrielle manuelle | Job / rappel périodique |
| PDF-CLAIM | Libellés de conformité dans notes/PDF | Neutraliser le wording jusqu’au PV |

### P3 — Ergonomie / documentation

| ID | Risque | Correctif proposé (non fait) |
|---|---|---|
| DOC-01 | Matrice historique vs SYSCO-01 | Maintenir une seule source d’exigences |
| UX-01 | Guidage clôture / AN | Assistants UI + checklists EC |

---

## 10. Prochaine étape (sans correctif)

Transmettre le pack EC ; collecter PV / réserves ; **puis** autoriser les correctifs de mapping listés. **Aucun correctif ne démarre sans autorisation explicite.**
