# Guide de connexion — Bêta privée MUHIMU (données fictives)

**Statut :** document préparé — **aucune invitation envoyée**.

## Prérequis

- Accès au réseau local où tourne la stack **`muhimu-beta`** (pas d’URL Internet publique).
- Navigateur récent (Chrome, Edge, Firefox).
- Certificat HTTPS **auto-signé** : accepter l’avertissement de sécurité **uniquement** si l’URL vous a été fournie par l’équipe MUHIMU.

## URL

- ERP : **`https://erp.beta.localhost:18443`** (recommandé — certificat SAN).  
  Éviter `https://127.0.0.1:18443` (erreur certificat fréquente).
- Console plateforme (si activée pour vous) : `https://console.beta.localhost:18443`.

## Comptes

Les identifiants vous seront transmis **hors dépôt Git** (fichier local ops ou canal sécurisé).

Emails types (sans mot de passe) :

- Propriétaire : `beta-test.owner@beta-test.muhimu.local`
- Comptable : `beta-test.comptable@beta-test.muhimu.local`
- Lecteur : `beta-test.viewer@beta-test.muhimu.local`

Organisation de démonstration : **`beta-test-01`**.

## Connexion

1. Ouvrir l’URL ERP.
2. Saisir email + mot de passe.
3. Choisir l’organisation **Démo BETA-TEST-01** si demandé.
4. Sélectionner la société (**SARL Fleuve Congo** ou **SARL Niari Logistique** selon votre profil).

## Déconnexion

Utiliser **Déconnexion** dans le menu utilisateur (barre latérale).

## Rappels

- **Données 100 % fictives** — République du Congo (CG), XAF.
- **Aucune certification SYSCOHADA** — PDF et écrans portent des mentions « document de test ».
- Ne pas saisir de données réelles de clients.
