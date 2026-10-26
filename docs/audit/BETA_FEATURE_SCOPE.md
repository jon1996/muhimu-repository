# BETA_FEATURE_SCOPE — Périmètre fonctionnel bêta privée

**Date :** 2026-10-13  
**Référence tests :** suite Django **333 OK** (DEV, 2026-10-13)  
**Légende :** ✅ fonctionnel testé · ⚠️ fonctionnel sous réserve · 🧪 expérimental · 🚧 incomplet · 🚫 hors 1ʳᵉ bêta

---

## 1. Synthèse recommandée (1ʳᵉ bêta testeurs)

| Inclure | Exclure ou restreindre |
|---------|-------------------------|
| Journal, plan PCGO, balance, grand-livre | Consolidation 🚫 |
| États SN/SMT + PDF (avec disclaimers) | Classe 9 / CAGE avancé 🚫 |
| Notes annexes (saisie + PDF) | RSE / ESG 🧪 🚫 |
| Tiers, lettrage, échéances | Escompte 🧪 |
| Trésorerie (banque, caisse, pointage) | Mise en équivalence (consolidation) 🚧 |
| Immobilisations + amortissements | Fiscalité nationale dédiée (absent) — N/A |
| Clôture + affectation + à-nouveaux | Réouverture d’exercice (volontairement absente) |
| Inventaire stocks (via clôture) | Console platform ops (staff only, hors ERP testeurs) |
| Livres légaux PDF | |
| Devises / réévaluation | |
| Engagements (hors class9 auto) | |
| Organisation / identité liasse | |
| Audit log (rôles auditor+) | |

---

## 2. Inventaire frontend (routes `/app/[orgSlug]/…`)

| Route | Fonction | Classe | Tests / remarques |
|-------|----------|--------|-------------------|
| `/` | Tableau de bord | ✅ | Usage général |
| `/journal`, `/journal/nouveau`, `/journal/[id]` | Saisie écritures | ✅ | `test_immutability`, posting |
| `/plan-comptable` | PCGO + comptes | ✅ | import/sync |
| `/balance` | Balance générale | ✅ | ACC-01 snapshots |
| `/grand-livre` | Grand-livre | ✅ | |
| `/etats` | États SN/SMT + notes + PDF | ⚠️ | PDF-CLAIM OK en **code DEV** ; mapping EC non validé (SYSCO-01) |
| `/livres` | Livres légaux PDF | ⚠️ | Bandeau beta (DEV) |
| `/consolides` | Consolidation / combiné | 🧪 🚫 | `test_consolidation` — pas de validation EC ; API ouverte |
| `/tiers` | Auxiliaires, lettrage | ✅ | `test_lettering`, `test_party_aux` |
| `/tresorerie` | Banque, OFX, caisse | ✅ | `test_bank_rec`, `test_cash`, `test_ofx` |
| `/immobilisations` | Actifs, dotations | ⚠️ | `test_amortization` — prorata simplifié |
| `/engagements` | Hors bilan | ⚠️ | `test_commitments` |
| `/classe-9` | Synthèse classe 9 | 🧪 🚫 | `test_class9` — périmètre restreint recommandé |
| `/cloture` | Clôture, affectation, stocks | ✅ | CLOSE-01 (19 E2E) |
| `/devises` | FX + réévaluation | ⚠️ | `test_fx` |
| `/rse` | Rapport ESG | 🧪 🚫 | `test_esg` — note 35 indicative |
| `/organisation` | Identité Titre IX | ✅ | Gate identité |
| `/audit` | Journal d’audit | ✅ | Rôle auditor+ |

**Réouverture :** aucune route ; API sans `reopen_exercise` (politique R0+R2, test CLOSE-01).

**Balance auxiliaire :** intégrée tiers / lettrage (`/api/ledger/parties/open`), pas de page dédiée — ✅ sous réserve UX.

**Fiscalité nationale :** pas de module TVA/DGI pays ; seulement champs identité (`tax_regime`, etc.) — 🚧 incomplet par design.

---

## 3. Inventaire API (contrôle d’accès)

Modèle d’accès (`tenancy/access.py`) :

| Helper | Rôles |
|--------|-------|
| `require_company` | Tout membre + en-tête société (lecture large) |
| `require_writer` | owner, admin, accountant |
| `require_admin` | owner, admin |
| `require_org_writer` | setup org |

**Constat important :** de nombreuses lectures sensibles (états, PDF, consolidation) utilisent **`require_company` uniquement** → rôle **viewer** et **auditor** peuvent télécharger PDF et lire consolidation.

| Domaine API | Écriture | Lecture | Classe bêta |
|-------------|----------|---------|-------------|
| `/ledger/entries/*` | writer | company | ✅ |
| `/ledger/statements`, `/statements/pdf` | — | company | ⚠️ disclaimers requis |
| `/ledger/exercise/close`, `allocate` | writer | — | ✅ |
| `/ledger/exercise/notes` | writer | — | ⚠️ texte conformity |
| `/ledger/opening/*` | writer | company | ✅ |
| `/ledger/inventories/*` | writer | company | ✅ |
| `/ledger/consolidation/*` | writer (création) | company | 🚫 masquer + 403 recommandé |
| `/ledger/cage/*`, `/class9` | writer / company | 🚫 |
| `/ledger/esg` | writer | company | 🚫 |
| `/ledger/escompte/*` | company preview / writer post | 🧪 🚫 |
| `/ledger/assets/*` | writer | company | ⚠️ |
| `/ledger/fx/*` | writer | company | ⚠️ |
| `/ledger/books/pdf` | — | company | ⚠️ |

**Stocks :** API inventaires + variation (`test_stocks`) — UI dans **Clôture**, pas menu dédié.

---

## 4. Proposition feature flags (à implémenter sur autorisation)

Objectif : **refus API + masquage UI** (pas boutons seuls).

| Flag env (proposition) | Effet |
|------------------------|-------|
| `BETA_FEATURES_CONSOLIDATION=0` | 404/403 sur `/api/ledger/consolidation/*` ; retirer nav « Consolidés » |
| `BETA_FEATURES_CLASS9_CAGE=0` | 403 cage/class9/commitment.class9 |
| `BETA_FEATURES_ESG=0` | 403 `/ledger/esg` ; masquer `/rse` |
| `BETA_FEATURES_ESCOMPTE=0` | 403 escompte preview/post |
| `BETA_REQUIRE_PDF_DISCLAIMER=1` | (déjà code) refuser génération PDF si module absent — garde-fou CI |

Middleware optionnel : liste blanche de prefixes `/api/ledger/` pour rôle viewer (lecture seule journal/balance/états **sans** PATCH).

---

## 5. Matrice risque / message testeur

| Fonction | Message bêta suggéré |
|----------|----------------------|
| États financiers | Données fictives ; non certifié ; mapping en validation |
| Consolidation | Non proposé en bêta 1 |
| Classe 9 / CAGE | Experimental — hors périmètre pilote |
| RSE | Indicateurs non auditables |
| Clôture | Irréversible sans support (pas de réouverture self-service) |

---

*Document d’audit — aucune modification produit dans BETA-READINESS-01.*
