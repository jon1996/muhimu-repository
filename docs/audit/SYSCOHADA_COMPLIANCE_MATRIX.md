# Matrice de conformité SYSCOHADA

**Avertissement :** ce document évalue l’**implémentation logicielle** par rapport aux exigences décrites dans `docs/ledger.md` et le code. Il ne constitue **pas** une attestation de conformité juridique. Toute affirmation « conforme SYSCOHADA » exige une validation écrite d’expert-comptable.

**Légende état :**  
`VALIDÉ` = implémenté + tests automatisés verts couvrant le cœur  
`PARTIEL` = code présent, couverture ou règles incomplètes  
`NON TESTÉ` = code présent, peu/pas de tests dédiés  
`ABSENT` = non trouvé  
`HORS PÉRIMÈTRE` = volontairement hors v1 / fiscalité nationale

---

## 1. Plan comptable

| Exigence | État | Preuve code | Preuve test | Validation EC |
|---|---|---|---|---|
| Classes 1–8 PCGO | VALIDÉ (catalogue) | `pcgo.py` (~1396 comptes) | setup via engines DB | Vérifier exhaustivité édition |
| Classe 9 engagements / CAGE | PARTIEL | `cage.py`, comptes 9xxx | `test_cage.py` | Oui |
| Hiérarchie / niveaux | VALIDÉ | `taxonomy.py`, `AccountLevel` | party aux / taxonomy indirect | — |
| Collectifs / auxiliaires | VALIDÉ | `lettering.py`, migration 0024 | `test_party_aux.py` | Oui |
| Comptes personnalisables (import) | VALIDÉ | `import_accounts.py` | non dédié import CSV E2E | — |
| Comptes actifs / désactivés | PARTIEL | `is_active` filtré au posting | — | — |
| Nature / sens des comptes | PARTIEL | `AccountSense`, `classify` | class9 / taxonomy | Oui |

## 2. Écritures comptables

| Exigence | État | Preuve | Test | Validation EC |
|---|---|---|---|---|
| Équilibre débit/crédit | PARTIEL | `assert_double_entry` (app only) | class9, escompte, fx | Ajouter CHECK SQL |
| Dates comptable / valeur | VALIDÉ | `Entry`, `resolve_period` | opening, fx | — |
| Numérotation pièces | VALIDÉ | `JournalSequence` + `select_for_update` | PDF books / demo | — |
| Journaux | VALIDÉ | OD/AC/VT/BQ/CA (+AN) | demo, books | — |
| Saisie manuelle brouillon | VALIDÉ | `create_draft` / `update_draft` | plusieurs engines | — |
| Validation immuable | PARTIEL | `Entry.save` bloque ; `.update()` contourne | `test_due_on` | — |
| Contrepassation | VALIDÉ | `reverse_entry` | indirect | Oui |
| Périodes clôturées / art. 22-4 | VALIDÉ | `resolve_period` | — | Oui |
| Cohérence écritures ↔ soldes | PARTIEL | snapshots | opening | **P0 concurrence** |

## 3. Documents et états

| État | État impl. | Preuve | Test | Validation EC |
|---|---|---|---|---|
| Journal / livres PDF | VALIDÉ | `pdf_books.py` | `test_pdf_books.py` | Oui |
| Grand-livre | VALIDÉ | `general_ledger` | PDF books | Oui |
| Balance générale | VALIDÉ | `trial_balance` | opening, books | Oui |
| Balance auxiliaire | PARTIEL | lettrage / open items | lettering notes | Oui |
| Bilan SN | PARTIEL | `sn_map.build_bilan` | `test_sn_map` | **Obligatoire** |
| Compte de résultat / SIG | PARTIEL | `build_compte_resultat` | `test_sn_map` | **Obligatoire** |
| TFT | PARTIEL | `build_tft` | `test_sn_map` | **Obligatoire** |
| Notes annexes | PARTIEL | notes_sn / notes_balance / notes métier | plusieurs | Exhaustivité |
| SMT | PARTIEL | `smt_map.py` | `test_smt`, PDF | Seuils |

## 4. Exercices et clôtures

| Exigence | État | Preuve | Test |
|---|---|---|---|
| Exercice civil 12 mois | VALIDÉ | `ensure_company_ledger` | engines |
| Soldes d’ouverture / AN | VALIDÉ | `opening.py` | `test_opening.py` |
| Clôture périodes + sceau | VALIDÉ | `periods.py` | — |
| Clôture annuelle + affectation | PARTIEL | `closing.py` | helpers `test_closing` (pas E2E close) |
| Réouverture contrôlée | ABSENT | — | — |
| Protection exercice fermé | PARTIEL | `post_entry` refuse CLOSED | — |

## 5. Opérations particulières

| Domaine | État | Commentaire |
|---|---|---|
| Immobilisations / amortissements | PARTIEL | `assets.py` + tests amortissement |
| Provisions / dépréciations | PARTIEL | comptes PCGO ; pas de moteur générique |
| CCA / PCA | ABSENT / HORS PÉRIMÈTRE v1 documenté | À confirmer produit |
| Inventaire physique | PARTIEL | `InventoryCampaign`, stocks |
| Devises / écarts | VALIDÉ | `fx.py` + `test_fx.py` |
| TVA / taxes pays | HORS PÉRIMÈTRE | identité / régime fiscal seulement |
| Tiers | VALIDÉ | ThirdParty + lettrage |

## 6. Points nécessitant validation expert-comptable (bloquants communication)

1. Mapping postes bilan AD–DZ et passif (signes 185, 4xx, 478/479…).
2. Cascade SIG et résultat XI.
3. Construction TFT (CAFG, FN dividendes, investissements).
4. Notes obligatoires minimales pour une liasse pilote.
5. Règles de clôture 6/7/8 → 13 et affectation (réserve légale 10 % / 20 %).
6. Traitement SMT vs SN selon seuils.

**Statut conformité globale :** **NON ATTESTÉE** — implémentation avancée, preuves logicielles partielles, validation métier manquante.
