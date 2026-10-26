# Guide de test comptable — Bêta privée

**Jeu :** organisation `beta-test-01` (données BETA-TEST-01).

## Parcours suggéré (comptable / owner)

1. **Plan comptable** — Vérifier la présence des comptes PCGO (classe 1 à 7).
2. **Journaux** — Lister OD, AC, etc.
3. **Écriture fictive** — Brouillon équilibré (ex. banque / produit), montant symbolique (ex. 10 000 XAF).
4. **Validation** — Passer le brouillon en **validé (POSTED)**.
5. **Grand livre** — Consulter le compte utilisé.
6. **Balance** — Vérifier équilibre débit = crédit sur la période.
7. **PDF** — Télécharger un état (bilan ou compte de résultat) et confirmer la bannière **« DOCUMENT DE TEST »**.
8. **Exercice 2026** — Opérations courantes ouvertes.
9. **Exercice 2025** — Consultation seule (exercice **clôturé** sur le jeu Fleuve Congo).

## Parcours lecteur

- Même consultation **sans** validation ni saisie (doit être refusée).

## Hors périmètre (doit être absent ou refusé)

- Consolidation / combiné.
- Classe 9 / CAGE avancé.
- RSE / ESG.
- Escompte (preview et écritures type effet).

## Montants de référence (seed existant)

| Société | Référence |
|---------|-----------|
| SARL Fleuve Congo | Vente seed **1 000 000 XAF** ; clôture 2025 avec résultat **200 000 XAF** |
| SARL Niari Logistique | Vente seed **250 000 XAF** |

Ne pas recréer de clôture sur 2025.
