# SYSCO-01 — Scénarios de test comptables (résultats attendus indépendants)

**Usage :** jeux **fictifs** à faire exécuter dans MUHIMU puis comparer aux attendus ci-dessous (calculés hors application).  
**Devise de référence dossier A :** **XOF** (0 décimale) — État membre UEMOA (ex. Côte d’Ivoire).  
**Dossier B (recommandé en complément) :** **CDF** (2 décimales) — RDC, services.

**Hypothèses fiscales (scénario 9 uniquement) :**  
Le SYSCOHADA ne fixe pas les taux de TVA nationaux. Le scénario 9 utilise un **exemple pédagogique UEMOA** à **18 %** (taux courant fréquemment cité pour plusieurs États UEMOA — **à confirmer par un fiscaliste du pays d’implantation**).  
**Ne pas** appliquer ce taux à la RDC, au Cameroun, etc. sans source locale.

Comptes : codes **PCGO** (catalogue MUHIMU / Titre VII). Journal : OD / AC / VT / BQ selon nature.

---

## Dossier A — PME négoce XOF (fictif)

**Société :** SARL DEMO Négoce · Capital 5 000 000 XOF · Exercice N civil · Régime SN.

### 1. Apport initial en capital (AN / OD)

| Compte | Libellé | Débit | Crédit |
|---|---|---:|---:|
| 521 | Banques locales | 5 000 000 | |
| 101 | Capital social | | 5 000 000 |

**Attendu :** balance D=C=5 000 000 ; trésorerie 5 000 000 ; CP 5 000 000.

### 2. Achat marchandises au comptant

Achat 1 000 000 XOF HT payé banque (hors TVA pour scénarios 2–8).

| Compte | Débit | Crédit |
|---|---:|---:|
| 601 | 1 000 000 | |
| 521 | | 1 000 000 |

### 3. Achat à crédit fournisseur

Achat 800 000 XOF.

| Compte | Débit | Crédit |
|---|---:|---:|
| 601 | 800 000 | |
| 401 | | 800 000 |

### 4. Vente au comptant

Vente 1 500 000 XOF.

| Compte | Débit | Crédit |
|---|---:|---:|
| 521 | 1 500 000 | |
| 701 | | 1 500 000 |

### 5. Vente à crédit client

Vente 600 000 XOF.

| Compte | Débit | Crédit |
|---|---:|---:|
| 411 | 600 000 | |
| 701 | | 600 000 |

### 6. Encaissement client

Encaissement 600 000.

| Compte | Débit | Crédit |
|---|---:|---:|
| 521 | 600 000 | |
| 411 | | 600 000 |

### 7. Paiement fournisseur

Paiement 800 000.

| Compte | Débit | Crédit |
|---|---:|---:|
| 401 | 800 000 | |
| 521 | | 800 000 |

### 8. Charges d’exploitation

Loyer 200 000 payé banque.

| Compte | Débit | Crédit |
|---|---:|---:|
| 622 | 200 000 | |
| 521 | | 200 000 |

*(622 = locations — vérifier intitulé exact PCGO dans le plan société.)*

### 9. TVA collectée / déductible (contexte fiscal **explicite**)

**Contexte :** exemple UEMOA **18 %** — **validation fiscaliste locale obligatoire**.

Achat 1 000 000 HT + TVA 180 000 ; vente 2 000 000 HT + TVA 360 000 ; règlement banque.

Achat :

| Compte | Débit | Crédit |
|---|---:|---:|
| 601 | 1 000 000 | |
| 445 | 180 000 | |
| 401 ou 521 | | 1 180 000 |

Vente :

| Compte | Débit | Crédit |
|---|---:|---:|
| 411 ou 521 | 2 360 000 | |
| 701 | | 2 000 000 |
| 443 | | 360 000 |

**Attendu logiciel :** équilibre D/C ; **pas** de génération automatique de déclaration TVA (fonction **absente** — HORS).  
Les numéros 443/445 sont des **hypothèses de subdivision** à aligner sur le plan société et la doctrine fiscale du pays.

### 10. Acquisition d’immobilisation

Matériel 2 000 000 payé banque → 24xx / 521.

### 11. Dotation aux amortissements

Méthode **linéaire** uniquement dans MUHIMU.  
Exemple : 2 000 000 sur 5 ans, année pleine → DAP 400 000.

| Compte | Débit | Crédit |
|---|---:|---:|
| 681 | 400 000 | |
| 28xx | | 400 000 |

**Attendu :** moteur `amortization.linear_charge` ; pas d’amortissement dégressif.

### 12. Écriture de régularisation

Exemple CCA : charge payée d’avance 120 000 (1 an), 3 mois à reporter → 30 000 en 476 / 6xx (schéma classique).  
**Statut produit :** pas de moteur automatique CCA/PCA — saisie manuelle OD attendue.

### 13. Opération en devise

Facture fournisseur 1 000 EUR, cours 655,957 XOF → 655 957 XOF (0 décimale).  
Comptes 401 / 6xx + montants devise sur lignes.

### 14. Différence de change

Revalorisation fin d’exercice via comptes **478 / 479** (implémenté `fx.post_revalue`).  
Attendu : écriture OD source `fx_reval` ; soldes 478/479 cohérents avec écart.

### 15. Clôture d’exercice

Attendu métier (AUDCIF / PCGO + `closing.close_exercise`) :

- Transfert classes 6/7/8 → 13 (résultat)  
- Exercice → CLOSED  
- Périodes scellées si flux IT suivi  

**Statut tests :** helpers présents ; **E2E close à faire valider** (CLOSE-01).

### 16. Réouverture et report à nouveau

Attendu : AN sur journal AN ; BS classes 1–5 (+13) ; 6/7/8 non repris en AN.  
**Réouverture d’un exercice CLOSED :** **non implémentée** (REOPEN-01) — scénario de non-régression négatif attendu (refus).

### 17. Correction d’écriture

Exercice courant : contrepassation (`reverse_entry`) puis nouvelle écriture exacte (art. 20).  
**Attendu :** écriture d’origine inchangée ; lien de contrepassation ; pas d’update destructif via UI/API.

### 18. Production des états financiers

Générer : balance, grand-livre, bilan SN, CR, TFT, notes, PDF liasse.  
Comparer aux totaux indépendants du § « Contrôles » ci-dessous et à la revue `SYSCO01_FINANCIAL_STATEMENTS_REVIEW.md`.

---

## Contrôles transverses après enchaînement 1–8 (hors TVA)

Calcul indépendant (ordre 1→8, XOF) :

| Indicateur | Attendu |
|---|---:|
| Σ mouvements D = C | Toujours |
| Banque nette (521) | 5 000 000 −1 000 000 +1 500 000 +600 000 −800 000 −200 000 = **5 100 000** |
| Clients (411) | 0 après encaissement |
| Fournisseurs (401) | 0 après paiement |
| Achats 601 | 1 800 000 |
| Ventes 701 | 2 100 000 |
| Charges 622 | 200 000 |

*(Recalculer si l’ordre d’exécution ou les montants changent.)*

---

## Dossier B — Services CDF (fictif)

Même logique avec montants en **CDF** (2 décimales), pays **CD**, régime SN ou SMT selon CA.  
**Ne pas** réutiliser le taux TVA 18 % UEMOA. Scénario TVA : **à définir avec un fiscaliste RDC** ou **exclure** de la bêta.

---

## Matrice scénario ↔ capacité MUHIMU

| # | Supporté API/moteur | Test auto existant | Validation EC |
|---|---|---|---|
| 1–8 | Oui | Indirect / engines | Oui (jeux fictifs) |
| 9 | Saisie manuelle possible ; pas de moteur TVA | Non | Fiscaliste pays |
| 10–11 | Oui (linéaire) | amortissement | Oui |
| 12 | Manuel | Non | Oui |
| 13–14 | Oui | `test_fx` | Oui |
| 15 | Oui code / E2E faible | helpers | **Obligatoire** |
| 16 | AN oui ; reopen non | opening | Oui |
| 17 | Contrepassation oui | indirect | Oui |
| 18 | Oui génération | sn_map / PDF | **Obligatoire** |
