# BETA-TEST-01 — Comptes de test (exemple — sans secrets)

**Fichier local non versionné :** copier vers `BETA_TEST01_CREDENTIALS.local.md` et renseigner le mot de passe issu du provisioning.

| Email | Rôle org | Accès sociétés | Usage |
|-------|----------|----------------|-------|
| `beta-test.owner@beta-test.muhimu.local` | Propriétaire | Fleuve Congo + Niari Logistique | Scénarios complets, clôture |
| `beta-test.comptable@beta-test.muhimu.local` | Comptable | Fleuve Congo | Saisie / validation |
| `beta-test.viewer@beta-test.muhimu.local` | Lecteur | Fleuve Congo | Permissions lecture seule |
| `beta-test.isol@beta-test.muhimu.local` | Lecteur | Niari Logistique uniquement | Test isolation |

**Mot de passe :** uniquement via **`BETA_TEST01_DEFAULT_PASSWORD`** dans `.env.beta` (ops local). Aucun défaut dans le code applicatif.

**Aucun compte superuser** n'est créé pour ces utilisateurs.
