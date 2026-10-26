# SYSCO-01 — Matrice des exigences (référentiel ↔ code ↔ tests)

**Statuts :**  
`CONF_TECH` = conforme selon tests techniques · `ECART` = écart détecté · `VAL_METIER` = validation EC requise · `NON_IMPL` = non implémenté · `NON_VERIF` = non vérifiable ici · `HORS` = hors périmètre v1

**Sources normatives internes :** `docs/ledger.md` (AUDCIF art. cités + PCGO Titre VII) ; seuils SMT art. 11–13.  
Aucune règle inventée hors de ces références.

---

## A. Organisation comptable (AUDCIF art. 14–24)

| ID | Exigence | Source | Implémentation | Tests | Statut |
|---|---|---|---|---|---|
| A01 | Enregistrement sans retard | art. 15 | API synchrone `posting` | engines | CONF_TECH |
| A02 | Date de valeur / pièce | art. 16 | `accounting_date`, `value_date` | opening, fx | CONF_TECH |
| A03 | Récap ≤ 1 mois | art. 16 | périodes mensuelles | partiel | VAL_METIER |
| A04 | Inventaire physique annuel | art. 16 | `InventoryCampaign` partiel | `test_stocks` | ECART / P |
| A05 | Partie double | art. 17-2 | `assert_double_entry` | multi | ECART (pas CHECK SQL) |
| A06 | Pièce justificative 10 ans | art. 17-3, 24 | `SourceDocument` + hash | — | VAL_METIER (rétention ops) |
| A07 | Chronologie figée | art. 17-4 | séquences journal | books | CONF_TECH |
| A08 | Origine / imputation / contenu | art. 17-5 | Entry + lines + source | — | CONF_TECH |
| A09 | Plan PCGO normalisé | art. 17-7, 18 | `pcgo.py` | setup | VAL_METIER (exhaustivité édition) |
| A10 | Livre-journal | art. 19 | PDF / API | `test_pdf_books` | CONF_TECH |
| A11 | Grand-livre | art. 19 | API + PDF | idem | CONF_TECH |
| A12 | Balance générale | art. 19 | trial_balance + snapshots | opening, ACC-01 | CONF_TECH |
| A13 | Livre d’inventaire (transcription) | art. 19 | bundle PDF statements/books | partiel | VAL_METIER |
| A14 | Auxiliaires + centralisation | art. 19 | journaux + lettrage | lettering | VAL_METIER |
| A15 | Correction par négatif (ex. courant) | art. 20 | `reverse_entry` | indirect | CONF_TECH / VAL_METIER |
| A16 | Erreur exercice antérieur → RAN + notes | art. 20 | ouverture / notes partielles | opening | ECART (process notes) |
| A17 | Irréversibilité après validation | art. 22 | save bloqué ; `.update()` contourne | due_on | ECART |
| A18 | Clôture IT trimestrielle | art. 22 | `it_close_period` ; pas de job Celery | — | ECART |
| A19 | Date dans période close → 1er jour ouvert | art. 22-4 | `resolve_period` | — | VAL_METIER |
| A20 | Chemin de révision | art. 22 | AuditLog | partiel | VAL_METIER |
| A21 | Arrêté ≤ 4 mois | art. 23 | non contrôlé logiciel | — | NON_VERIF |

---

## B. Plan de comptes (PCGO Titre VII)

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| B01 | Classes 1–8 | `pcgo.py` | engines | CONF_TECH / VAL_METIER édition |
| B02 | Classe 9 facultative | cage / commitments | test_cage, class9 | VAL_METIER |
| B03 | Hiérarchie / imputabilité | `taxonomy.py` | party_aux | CONF_TECH |
| B04 | Collectifs / auxiliaires | migration 0024, lettering | test_party_aux | CONF_TECH |
| B05 | Import CSV sans destruction | `import_accounts.py` | pas E2E | ECART (tests) |
| B06 | Fiches Titre VII | `fiches.py` | — | NON_VERIF exhaustivité |

---

## C. États financiers SN (art. 8, 25–34)

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| C01 | Bilan (actif/passif, N/N-1) | `build_bilan` | `test_sn_map` | VAL_METIER |
| C02 | Pas de compensation | logique sn_map | unitaire | VAL_METIER |
| C03 | Compte de résultat + SIG | `build_compte_resultat` | `test_sn_map` | VAL_METIER |
| C04 | TFT | `build_tft` + CAFG | `test_sn_map` | VAL_METIER |
| C05 | Notes annexes | notes_sn / notes_balance | partiel | ECART / VAL_METIER |
| C06 | Monnaie légale État partie | `ohada.py` + company currency | test_liasse | CONF_TECH |

**Points EC obligatoires (déjà listés matrice historique) :** postes AD–DZ / passif (185, 4xx, 478/479) ; cascade SIG → XI ; TFT (CAFG, dividendes, investissements).

---

## D. SMT (art. 11–13)

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| D01 | Seuils 60/40/30 M F CFA | `SMT_THRESHOLDS` | `test_smt` | VAL_METIER (unité / devise) |
| D02 | Situation patrimoniale | `build_situation` | `test_smt` | VAL_METIER |
| D03 | État de trésorerie | `build_etat_tresorerie` | `test_smt` | VAL_METIER |
| D04 | Bascule SN ↔ SMT | `accounting_regime` | partiel | VAL_METIER |

---

## E. Exercices / clôture / RAN

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| E01 | Exercice 12 mois civil | `ensure_company_ledger` | engines | CONF_TECH |
| E02 | Soldes d’ouverture AN | `opening.py` | `test_opening` | CONF_TECH |
| E03 | Clôture 6/7/8 → 13 | `close_exercise` | helpers only | ECART (pas E2E) |
| E04 | Affectation / réserve légale | `allocate_result`, `suggest_legal_reserve` | `test_closing` | VAL_METIER (10 %/20 %) |
| E05 | Réouverture | — | — | NON_IMPL |
| E06 | Protection exercice fermé | refuse CLOSED | — | CONF_TECH partiel |

---

## F. Opérations particulières

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| F01 | Immobilisations + DAP linéaire | assets / amortization | test_amortization | VAL_METIER |
| F02 | Autres méthodes d’amortissement | — | — | NON_IMPL |
| F03 | FX + revalorisation 478/479 | `fx.py` | `test_fx` | CONF_TECH / VAL_METIER |
| F04 | TVA nationale | — | — | HORS |
| F05 | CCA / PCA automatiques | — | — | NON_IMPL / HORS v1 doc |
| F06 | Stocks / variation | `stocks.py` | test_stocks | VAL_METIER |

---

## G. Multi-sociétés / isolation

| ID | Exigence | Implémentation | Tests | Statut |
|---|---|---|---|---|
| G01 | Plan et écritures par société | org+company FK | SAAS-03 | CONF_TECH |
| G02 | Isolation RLS | migrations ledger RLS | test_isolation | CONF_TECH |

---

## Synthèse couverture

| Statut | Ordre de grandeur |
|---|---|
| CONF_TECH | Cœur tenue + livres + FX + AN + multi-société |
| VAL_METIER | Liasse SN/SMT, notes, clôture/affectation, inventaire |
| ECART | Immutabilité ORM, CHECK SQL, close E2E, notes, Celery IT |
| NON_IMPL | Réouverture, TVA, méthodes amort. alternatives |
| HORS | Fiscalités nationales déclaratives |
