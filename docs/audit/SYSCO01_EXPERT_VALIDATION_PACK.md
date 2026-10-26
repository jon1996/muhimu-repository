# SYSCO-01 — Pack de validation expert-comptable / auditeur

**Objet :** permettre à un professionnel de la comptabilité OHADA d’examiner MUHIMU Accounting sur **données fictives** et de produire un avis écrit (PV).  
**Ce pack ne constitue pas une certification.**

---

## 1. Présentation du logiciel (résumé)

| Élément | Description |
|---|---|
| Produit | MUHIMU Accounting — SaaS comptabilité multi-sociétés |
| Référentiel visé | SYSCOHADA / PCGO / AUDCIF (zone OHADA) |
| Stack | Django + PostgreSQL (RLS) + Next.js |
| Tenue | Partie double, journaux, grand-livre, balance, snapshots |
| Liasse | Générateurs SN (bilan, CR, TFT, notes) et SMT |
| Fiscalité nationale | **Hors moteur** (TVA déclarative non couverte) |

Documents techniques associés :

- `SYSCO01_ACCOUNTING_AUDIT_REPORT.md`  
- `SYSCO01_REQUIREMENTS_MATRIX.md`  
- `SYSCO01_TEST_SCENARIOS.md`  
- `SYSCO01_FINANCIAL_STATEMENTS_REVIEW.md`  
- `docs/ledger.md`  
- `docs/audit/SYSCOHADA_COMPLIANCE_MATRIX.md`

---

## 2. Périmètre fonctionnel soumis à revue

**Inclus :** PCGO, saisie/validation, livres, ouverture/AN, clôture/affectation (code), immobilisations linéaires, FX, SN/SMT, multi-sociétés.

**Exclus / hors revue fiscale :** déclarations TVA/IS nationales ; banques / assurances (art. 5 al. 4).

**Limites techniques connues à communiquer à l’EC :**

- Pas de CHECK SQL d’équilibre (contrôle applicatif).  
- Immutabilité postable contournable hors API (`.update()`).  
- Pas de réouverture d’exercice.  
- Clôture annuelle : peu de tests E2E.  
- Notes annexes incomplètes.

---

## 3. Référentiel comptable

- AUDCIF (articles cités dans `docs/ledger.md`)  
- PCGO Titre VII (plan) + états art. 25–34  
- SMT art. 11–13 (seuils en F CFA dans le code)

---

## 4. Scénarios à faire exécuter

Voir `SYSCO01_TEST_SCENARIOS.md` (18 scénarios).

**Minimum recommandé pour PV bêta :**

| Priorité | Scénarios |
|---|---|
| Obligatoire | 1–8, 15, 17, 18 (dossier XOF) |
| Fortement conseillé | 10–11, 13–14, 16 |
| Fiscaliste pays | 9 (ou exclusion explicite) |
| SMT | Jeu CA sous seuil + bascule régime |

---

## 5. Livrables à extraire de l’application (par dossier fictif)

1. Balance générale (fin N)  
2. Grand-livre (comptes mouvementés)  
3. Journal(aux) de la période  
4. PDF livres légaux si disponible  
5. PDF liasse SN (bilan, CR, TFT, notes)  
6. Le cas échéant : liasse SMT  
7. Detail écriture de clôture / affectation  
8. Écriture FX / DAP si scénarios joués  

Comparer aux **attendus indépendants** du fichier scénarios (ne pas se fier au seul équilibre du PDF).

---

## 6. Anomalies déjà identifiées (audit logiciel)

| Réf. | Priorité | Description |
|---|---|---|
| SYSCO-01 | P0 | Mapping liasse non attesté |
| CLOSE-01 | P1 | Clôture E2E non prouvée |
| REOPEN-01 | P1 | Réouverture absente |
| ACC-02 | P1 | Contournement immutabilité ORM |
| ACC-03 | P1 | Pas de contrainte SQL D=C |
| NOTES-01 | P1 | Notes partielles |
| SMT-01 | P1 | Seuils / devise SMT |
| TAX-01 | P2/HORS | Pas de TVA nationale |
| PDF-CLAIM | P2 | Libellés « conforme SYSCOHADA » dans notes/PDF |

Correctifs **non implémentés** dans cette phase (attente autorisation).

---

## 7. Questions d’arbitrage professionnel

1. Les préfixes `sn_map` (AE…DZ, CR, TFT) correspondent-ils à l’édition PCGO / modèles officiels retenus ?  
2. Traitement des comptes 185, 419/409, 478/479 au bilan : correct ?  
3. Cascade SIG jusqu’à XI : conforme ?  
4. Construction TFT (CAFG, investissements, dividendes) : acceptable pour PME ?  
5. Quelles notes sont **minimales** pour une liasse pilote ?  
6. Réserve légale 10 % / 20 % : règles sociétés applicables par pays ?  
7. SMT : les seuils 60/40/30 M F CFA s’appliquent-ils tels quels hors zone franc ?  
8. La contrepassation couvre-t-elle suffisamment l’art. 20 pour la bêta ?  
9. Faut-il bloquer tout claim textuel de conformité dans l’UI/PDF avant PV ?

---

## 8. Grille de validation (à remplir par l’EC)

| # | Contrôle | OK | Écart | Observation |
|---|---|---|---|---|
| 1 | Partie double / équilibre jeux 1–8 | ☐ | ☐ | |
| 2 | Balance = grand-livre | ☐ | ☐ | |
| 3 | Bilan SN postes clés | ☐ | ☐ | |
| 4 | Compte de résultat / SIG | ☐ | ☐ | |
| 5 | TFT | ☐ | ☐ | |
| 6 | Notes minimales | ☐ | ☐ | |
| 7 | Ouverture AN | ☐ | ☐ | |
| 8 | Clôture + affectation | ☐ | ☐ | |
| 9 | Contrepassation | ☐ | ☐ | |
| 10 | FX / 478-479 | ☐ | ☐ | |
| 11 | DAP linéaire | ☐ | ☐ | |
| 12 | Isolation multi-sociétés (2 dossiers) | ☐ | ☐ | |
| 13 | SMT (si applicable) | ☐ | ☐ | |
| 14 | Absence de claim abusif dans PDF | ☐ | ☐ | |

### Avis

- ☐ **Validé pour bêta privée (données fictives)** sans réserve  
- ☐ **Validé pour bêta privée sous réserves** (lister)  
- ☐ **Non validé** — correctifs préalables requis  

**Réserves / recommandations :**  
…………………………………………………………………………………

**Expert-comptable / auditeur :**  
Nom : _________________ · Ordre / cabinet : _________________  
Date : ________ · Signature : _________________

---

## 9. Procédure proposée (1–2 jours EC)

1. Lire le rapport d’audit + matrice (2 h).  
2. Jouer dossier A scénarios obligatoires dans un environnement lab (1/2 j).  
3. Extraire liasses + balances ; confronter aux attendus (1/2 j).  
4. Compléter la grille + PV court (1–2 h).  
5. Restituer la liste d’écarts priorisés (P0/P1) pour correctifs logiciels.

---

## 10. Contact produit (interne)

Archiver le PV signé sous `docs/audit/` (ou espace juridique) — critère de done SYSCO-01 (plan P0).
