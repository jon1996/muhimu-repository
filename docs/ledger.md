# Conception du ledger SYSCOHADA

Source : *Acte uniforme relatif au droit comptable et à l’information financière* et *Système comptable OHADA* (PCGO), document de travail du dépôt (1204 pages).

Cette note fige le **domaine métier** du module `ledger`.

**Implémenté (v1)** : exercice civil + périodes mensuelles, copie PCGO classes 1–8, journaux OD/AC/VT/BQ/CA, saisie brouillon, validation partie double, immuabilité + contrepassation, snapshots de balance, grand-livre.

## Périmètre juridique (articles 1 à 24)

- Toute **entité** (personne physique ou morale visée par l’AUDCIF) tient une **comptabilité financière** (art. 1–2).
- Un seul référentiel pour les États parties : **SYSCOHADA** = Plan comptable général OHADA (PCGO) + dispositif consolidé/combiné (art. 5).
- **Hors SYSCOHADA** (à isoler plus tard par type d’entité) : banques, microfinance, marché financier, assurances, sécurité sociale, NPO (art. 5 al. 4). Notre v1 cible les entreprises commerciales / artisanales / de services.
- Qualités : **prudence, régularité, sincérité, transparence** (art. 3–4, 7).
- **Exercice** = 12 mois, **année civile** par défaut ; exceptions 1er exercice et liquidation (art. 8).
- Jeu complet d’états (art. 8, 25–33) :
  - Bilan
  - Compte de résultat (liste, soldes intermédiaires de gestion)
  - Tableau des flux de trésorerie (TFT)
  - Notes annexes
- Deux régimes (art. 11–13) :
  - **Système normal** (défaut)
  - **Système minimal de trésorerie (SMT)** sous seuils de CA HT (60 / 40 / 30 millions F CFA selon négoce / artisanat / services)
- Monnaie et langue : **unité monétaire ayant cours légal** dans l’État partie + langue officielle (art. 17-1). En zone UEMOA : **XOF**, 0 décimale.

## Organisation comptable (art. 14–24) — contraintes logicielles

Ces articles sont le cahier des charges du moteur :

1. **Enregistrement exhaustif, au jour le jour, sans retard** (art. 15). Chemin API synchrone.
2. **Date de valeur comptable** = date d’émission de la pièce interne, ou de réception de la pièce externe. Opérations de même nature / même lieu / même jour récapitulables sur une pièce unique (art. 16).
3. **Récapitulatif périodique ≤ 1 mois** (art. 16) : centralisation des journaux auxiliaires.
4. **Inventaire physique** annuel, conservé pour justifier chaque poste (art. 16).
5. **Partie double** : toute écriture débite au moins un compte et en crédite un autre ; totaux débit = crédit (art. 17-2).
6. **Pièce justificative** datée, classée, référencée dans l’écriture, conservée **10 ans** avec les livres (art. 17-3, 24).
7. **Chronologie** figée (art. 17-4).
8. Chaque enregistrement identifie **origine, imputation, contenu, référence de pièce** (art. 17-5).
9. **Plan de comptes normalisé PCGO**, subdivisible ou regroupable si les états restent produisibles (art. 17-7, 18).
10. Livres obligatoires (art. 19) :
    - **Livre-journal**
    - **Grand-livre**
    - **Balance générale** (soldes d’ouverture, cumuls débit/crédit, soldes)
    - **Livre d’inventaire** (transcription Bilan, CR, TFT + résumé d’inventaire)
11. Journaux / livres **auxiliaires** autorisés ; centralisation **au moins mensuelle** dans journal et grand-livre (art. 19).
12. **Pas de blanc ni d’altération**. Correction d’erreur **sur l’exercice en cours** : inscription **en négatif** des éléments erronés, puis enregistrement exact (art. 20). Pas d’update destructif.
13. Erreur **d’un exercice antérieur** : ajustement du **report à nouveau** + mention en notes (art. 20).
14. Traitement informatique (art. 22) — non négociable pour un SaaS :
    - entrée = origine + contenu + imputation, restituable en clair ;
    - **irréversibilité** après **validation** (période ≤ 1 mois) ;
    - **clôture informatique** au moins **trimestrielle**, au plus tard fin du trimestre suivant ;
    - pas d’insertion intercalaire ; si date de valeur dans une période déjà clôturée → enregistrer au **premier jour de la période ouverte**, en mentionnant distinctement la date de valeur ;
    - chemin de révision (audit trail) ;
    - états périodiques **numérotés et datés**.
15. Arrêté des états : **≤ 4 mois** après clôture (art. 23).

## Plan de comptes (Titre VII PCGO)

Codification **décimale**, classes 1–8 impératives, classe 9 facultative (engagements / CAGE).

| Classe | Nature | Rôle |
|---|---|---|
| 1 | Ressources durables | Capital, réserves, RAN, résultat, subventions, emprunts, provisions |
| 2 | Actif immobilisé | Incorporel, corporel, financier, amortissements (28), dépréciations (29) |
| 3 | Stocks | Marchandises, MP, en-cours, produits finis, dépréciations (39) |
| 4 | Tiers | Fournisseurs, clients, personnel, sociaux, État, groupe, HAO |
| 5 | Trésorerie | Titres, banques, monnaie électronique, caisse, virements internes (58) |
| 6 | Charges AO | Achats, transports, services, impôts, personnel, financiers, DAP |
| 7 | Produits AO | Ventes, subventions, production, autres produits, revenus financiers, reprises |
| 8 | Autres charges / produits | Cessions d’immos, HAO, participation des travailleurs, subventions d’équilibre |
| 9 | Engagements / CAGE | Plus tard, hors v1 |

Constantes utiles au moteur :

- Terminaison **9** à 2 chiffres (bilan) : dépréciations / provisions de la classe.
- Chiffre **9** en 3e/4e position : **sens inverse** (RRR, fournisseurs débiteurs 409, clients créditeurs 419), sauf classe 2.
- Parallélismes 6xx/7xx (601/701, 65/75, 81/82, 83/84…).

Chaque **Company** a son propre plan (copie paramétrable du PCGO), jamais un plan global partagé entre sociétés.

Hiérarchie du code (Titre VII, vocabulaire officiel) :

| Niveau | Longueur | Exemple | Imputable |
|---|---|---|---|
| Classe | 1 | `4` Tiers | Non |
| Compte à 2 chiffres | 2 | `41` Clients | Oui |
| Principal | 3 | `411` Clients | Oui (souvent collectif) |
| Divisionnaire | 4 | `4111` Clients nationaux | Oui |
| Subdivision d’entité | 5+ ou suffixe | `411-SOCOCIM` | Oui |

Collectifs typiques : 40/401, 41/411, 42/421, 52/521, 57/571. Catalogue officiel chargé jusqu’au **divisionnaire (4 chiffres)**, pages 223–273. Fiches Titre VII (contenu, fonctionnement, exclusions, contrôles) : pages 277–541, résolues au compte officiel le plus proche. Import CSV (fusion, jamais de suppression des comptes déjà mouvementés) : colonnes `code`, `intitulé`, `imputable`, `collectif`, `notes`.

## États financiers (art. 25–34)

**Bilan SYSCOHADA** (pas IFRS) :

- Actif : immobilisé, circulant, trésorerie-actif, écart de conversion-actif
- Passif : ressources stables, passif circulant, trésorerie-passif, écart de conversion-passif
- Capitaux propres distincts ; **pas de compensation** actif/passif ni charges/produits (art. 34)
- Bilan d’ouverture N = clôture N-1
- Colonne comparatif N-1 obligatoire

**Compte de résultat** : liste, cascade des SIG (marge, VA, EBE, RE, RAO, etc. selon PCGO). Distinguer exploitation, financier (activités ordinaires) et HAO.

**TFT** : trésorerie nette début, flux opérationnels, investissement, capitaux propres, capitaux étrangers, trésorerie nette fin.

Les soldes de balance **ne se recalculent pas** en sommant tout l’historique à chaque écran : table de mouvements + snapshots de période (cohérent avec la centralisation mensuelle).

## Modèle de données proposé (`apps.ledger`)

Tous les enregistrements portent `organization_id` + `company_id` (RLS). Montants : `NUMERIC`, précision selon `currency_code` (XOF = 0).

```
Exercise          # company, year, starts_on, ends_on, status(open|closing|closed)
AccountingPeriod  # exercise, month or quarter, status(open|validated|it_closed)
Journal           # company, code (VT, AC, BQ, CA, OD…), name, type
Account           # company, code PCGO, label, class, is_auxiliary, parent
ThirdParty        # optional aux on class 4 (client/fournisseur)
Document          # pièce justificative : number, date, storage ref, hash
Entry             # pièce comptable : journal, period, number, accounting_date,
                  # value_date, status(draft|posted), source, idempotency_key
EntryLine         # entry, account, debit, credit, third_party, lettering
BalanceSnapshot   # period, account, open_debit, open_credit, mov_debit, mov_credit
```

Règles d’écriture :

- `draft` : modifiable.
- `posted` : immuable. Correction = **contrepassation en négatif** (art. 20) puis nouvelle pièce. Pas de DELETE.
- `sum(debit) == sum(credit)` imposé en contrainte applicative + check SQL.
- Numérotation de journal **séquentielle par société / journal / exercice**, sans trou après validation.
- Après `AccountingPeriod.validated` : plus de posting dans la période (sauf première date de la période suivante si date de valeur rétroactive, art. 22-4).
- Clôture informatique trimestrielle : job Celery + sceau (hash de la séquence d’écritures).

Journaux v1 : `OD` (opérations diverses), `AC` (achats), `VT` (ventes), `BQ` (banque), `CA` (caisse). Centralisation mensuelle vers le livre-journal.

## Ordre d’implémentation du ledger

1. `Exercise` + `AccountingPeriod` + copie du PCGO (classes 1–8, comptes à 2 puis 3 chiffres).
2. `Journal` + `Entry`/`EntryLine` brouillon + validation partie double.
3. Grand-livre / balance à partir des snapshots.
4. Journaux auxiliaires ventes/achats/trésorerie.
5. États : Bilan, CR, TFT (système normal).
6. SMT (option entité sous seuil).
7. Classe 9, consolidés, IFRS parallèle (art. 8 al. 4–5) : hors v1.

## Ce que le SaaS ne doit jamais faire

- Utiliser un `float` pour un montant.
- Modifier une écriture validée.
- Poster dans une période informatiquement clôturée (sauf règle art. 22-4).
- Partager un plan de comptes ou une séquence de pièces entre deux `Company`.
- Calculer une balance en `SUM()` sur des années d’écritures à chaque requête.
