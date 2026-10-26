# Fonctionnalités autorisées et exclues — Bêta privée

Référence technique : `docs/audit/BETA_FEATURE_SCOPE.md`.

## Autorisé (cœur pilote)

- Authentification ERP, multi-société (selon type d’organisation).
- Plan comptable PCGO / SYSCOHADA (descriptif).
- Saisie, validation, grand livre, balance.
- États et PDF **avec disclaimers** (non certifiés).
- Clôture / affectation / à-nouveaux (jeu fictif).
- Journal d’audit (rôles autorisés).

## Exclu (BETA-SCOPE — désactivé)

| Domaine | Flag |
|---------|------|
| Consolidation / combiné | `consolidation` |
| Classe 9 / CAGE | `class9_cage` |
| RSE / ESG | `esg` |
| Escompte | `escompte` |

Toute réactivation nécessite décision produit + redeploy.

## Non revendiqué

- Certification SYSCOHADA / OHADA.
- Dépôt réglementaire.
- Attestation expert-comptable.
