# Checklist UAT navigateur — Bêta locale (14 parcours)

**URL ERP :** `https://erp.beta.localhost:18443`  
**Ne pas utiliser** `https://127.0.0.1:18443` (certificat SAN : `erp.beta.localhost`, `localhost`).

**Mot de passe :** valeur de `BETA_TEST01_DEFAULT_PASSWORD` dans votre `.env.beta` local (**ne jamais commiter**).

| # | Action | Compte | Résultat attendu | OK |
|---|--------|--------|------------------|-----|
| 1 | Ouvrir `/login`, se connecter, se déconnecter | owner | Session OK, retour login | |
| 2 | Choisir **SARL Fleuve Congo** | comptable | Accès autorisé | |
| 3 | Menu **Plan comptable** | comptable | Liste PCGO | |
| 4 | **Journaux** | comptable | OD, AC, … | |
| 5 | Nouvelle écriture équilibrée fictive | comptable | Brouillon enregistré | |
| 6 | **Valider** l'écriture | comptable | Statut validé | |
| 7 | **Grand livre** (compte mouvementé) | comptable | Lignes visibles | |
| 8 | **Balance** période courante | comptable | Débit = crédit | |
| 9 | **PDF** état financier | comptable | Téléchargement + bandeau « DOCUMENT DE TEST » | |
| 10 | Menu | owner | Pas de consolidés / classe 9 / RSE si exclus | |
| 11 | URL directe `/app/.../consolides` (si connu) | owner | Blocage ou 403 | |
| 12 | Tentative validation écriture | viewer | Refus | |
| 13 | Exercice **2025** (consultation) | owner | Clôturé, lecture | |
| 14 | Exercice **2026** | owner | Ouvert, saisie possible | |
| 15 | Sélecteur société **Niari** | isol | OK ; **Fleuve** absent ou inaccessible | |
| 16 | Tentative **Fleuve** avec compte isol | isol | Refus UI ou liste vide | |

**Preuve :** capture d'écran horodatée + email testeur dans `GRILLE_ANOMALIES.md`.
