# SYSCO-01 — Revue des états financiers (implémentation logicielle)

**Avertissement :** un état **affiché** ou **équilibré** n’est pas « conforme SYSCOHADA ». Cette revue décrit **ce que le code produit** et les **hypothèses** à faire valider par un EC.

Sources code : `sn_map.py`, `smt_map.py`, `statements.py`, `notes_sn.py`, `notes_balance.py`, `pdf_statements.py`.

---

## 1. États disponibles

| État | Générateur | PDF | Comparatif N/N-1 | Régime |
|---|---|---|---|---|
| Bilan SN | `build_bilan` | oui | oui (prior_rows) | SN |
| Compte de résultat / SIG | `build_compte_resultat` | oui | oui | SN |
| TFT | `build_tft` | oui | via métriques | SN |
| Notes annexes | `notes_sn` + métier | partiel | variable | SN |
| Situation SMT | `build_situation` | oui | limité | SMT |
| État de trésorerie SMT | `build_etat_tresorerie` | oui | — | SMT |
| Liasse consolidée / combinée | labels + consolidation | partiel | — | option |

Orchestration : `statements.build_statements` bascule selon `accounting_regime` (`sn` / `smt`).

---

## 2. Bilan SN

### Sources
Soldes / mouvements de balance (rows) agrégés par **préfixes de comptes PCGO** dans `bilan_amounts()`.

### Regroupements (extrait)

| Code | Libellé (layout) | Logique code (résumé) |
|---|---|---|
| AE–AH | Immos incorporelles | 21x / 218… − 28x/29x |
| AJ–AN, AP | Immos corporelles | 22–25… − amort./dép. |
| AR–AS | Immos financières | 26–27 − 296/297 |
| BB | Stocks | 31–38 − 39 |
| BI | Clients | 41 hors 419 − 491 |
| BJ | Autres créances | 185, 42–47 hors 478/479 |
| BS | Trésorerie actif | 52–57, 581/582… |
| BU / DV | Écarts conversion | 478 / 479 |
| CA–CM | Capitaux propres | 10x–15x… |
| DJ | Fournisseurs | 40 hors 409 |
| Totaux AZ, BK, BZ / DF, DP, DZ | Agrégations | `add(...)` |

### Signes
- Actif : net débit (brut − amort./dépréciations).  
- Passif : net crédit ; certains postes via `_minus_debit` (ex. 109).  
- Postes **185 / 4xx / 478 / 479** : **validation EC obligatoire** (historique matrice).

### Totaux
Le code agrège AZ/BK/BZ et DF/DP/DZ. L’équilibre bilan doit être confronté à un jeu indépendant (scénarios SYSCO-01), pas seulement au rendu PDF.

### Rubriques / risques
- Exactitude de chaque préfixe vs édition PCGO de référence du dépôt.  
- Traitement « dont immeubles de placement » (AJ_P, AK_P).  
- Texte PDF pouvant suggérer une conformité non attestée (`notes_sn` / libellés liasse) — **à neutraliser en communication**.

---

## 3. Compte de résultat / SIG

### Sources
`_CR_SPECS` / `_CR_LAYOUT` : produits (7/8) et charges (6/8) par préfixes ; cascade SIG jusqu’au résultat.

### Points d’attention EC
1. Cascade des SIG jusqu’à **XI** (résultat net).  
2. Séparation AO / financier / HAO.  
3. Cohérence avec clôture 6/7/8 → 13 (`closing.py` + `cr_amounts`).  
4. Comparatif N-1 après clôture (restauration PnL pour affichage — logique `restore` dans closing/tests).

### Formules
Implémentées en Python (sommes nettes / mouvements) — **recalcul indépendant requis** sur jeu fictif avant PV.

---

## 4. TFT

### Sources
`build_tft` : CAFG (`cafg`), variation BFR, investissements (dont registre immos), financements, dividendes (FN), variation trésorerie.

### Hypothèses logicielles
- Classification des flux dérivée des comptes / sources d’écritures.  
- Investissements : contribution `tft_investment_from_register` (immobilisations).  
- Certaines sources exclues du flux de trésorerie SMT (`CASH_SKIP_SOURCES`) — analogue conceptuel à surveiller en SN.

### Validation EC
Construction CAFG, dividendes, investissements, réconciliation trésorerie début/fin vs bilans.

---

## 5. Notes annexes

| Nature | État |
|---|---|
| Squelette notes 1–36 | Présent (`notes_sn`) |
| Notes calculées (1, 3, 6, 7, 11, 17, 31, 34–36, etc.) | Partielles (`notes_balance` + métier) |
| Remplissage utilisateur | Nécessaire pour beaucoup de notes |
| Phrase type « conformément au SYSCOHADA… sans réserve » | **Risque de sur-affirmation** — à faire valider / édulcorer avant bêta publique |

**Minimum pilote EC :** confirmer le sous-ensemble de notes obligatoires pour une liasse PME fictive.

---

## 6. SMT

| Élément | Implémentation | Hypothèse à valider |
|---|---|---|
| Seuils | 60 / 40 / 30 millions | Unité = F CFA ; activité trade/craft/services |
| Situation | Postes IA–IE / PA–… | Mapping préfixes |
| État de trésorerie | Recettes/dépenses classe 5 | Exclusion sources listées |

Ne pas déclarer éligibilité SMT pour un dossier CDF sans reformulation des seuils (documentés en F CFA dans le code).

---

## 7. Jeux de référence recommandés (indépendants du moteur)

1. **Dossier A XOF négoce** — scénarios 1–8 + 18 (`SYSCO01_TEST_SCENARIOS.md`) : calculer à la main bilan synthétique, CR, trésorerie.  
2. **Dossier B CDF services** — même structure, sans TVA UEMOA.  
3. **Jeu FX** — une facture devise + reval 478/479.  
4. **Jeu clôture** — charges/produits puis close + affectation (réserve).

Comparer **ligne à ligne** les codes SN (AE, BI, CA, TA… XI, flux TFT) — pas seulement le total.

---

## 8. Verdict revue états

| État | Maturité logicielle | Attestation |
|---|---|---|
| Livres (journal, GL, balance) | Élevée | Non requise pour claim SYSCO ; utiles EC |
| Bilan / CR / TFT | Moyenne–élevée (code + tests unitaires) | **Requise** |
| Notes | Faible–moyenne | **Requise** |
| SMT | Moyenne | **Requise** |

**Conclusion :** génération opérationnelle pour bêta fictive ; **conformité non déclarable** sans PV EC.
