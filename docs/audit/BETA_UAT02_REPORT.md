# BETA-UAT-02 — Levée des bloquants U1 / U2 et réserves sécurité

**Date :** 2026-10-14  
**Cible :** `muhimu-beta` / organisation fictive **`beta-test-01`** uniquement  
**Références :** `BETA_UAT01_REPORT.md`, `BETA_TEST01_REPORT.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | **U2 levé** (org **CABINET** + isolation API validée). **U1 validé** sur le périmètre testé (**14 parcours métier** confirmés manuellement). **Réserve :** politique de session (pas d’idle timeout / fermeture navigateur en bêta tant que SEC-SESSION-01 n’est pas déployé). **Ouverture testeurs : NO-GO** sans votre GO écrit explicite. |

---

## 1. U2 — Conversion SME → CABINET

### Précontrôles (avant modification)

| Contrôle | Résultat |
|----------|----------|
| Organisations en base | **1 seule** : `beta-test-01` |
| Type initial | **`sme`** |
| Sauvegarde restaurable | **`backups/postgres/muhimu_beta_uat02_pre.dump`** (~363 KB) + `muhimu_beta_20261014_test01_pre.dump` |
| Dossiers hors périmètre | **Aucun** autre org / société |

### Conséquences documentées (SME → CABINET)

| Aspect | Avant (SME) | Après (CABINET) |
|--------|-------------|-----------------|
| Visibilité sociétés (API) | Tous les membres → **toutes** les sociétés | Membres non admin → **`CompanyAccess`** obligatoire |
| Modèle code / RLS | Inchangé | Inchangé (pas de migration, pas de changement de policies) |
| Données comptables | Écritures posted existantes | **Conservées** (comptages contrôlés post-conversion) |
| Owner / admin | Accès implicite tous dossiers | **Identique** |

### Changements exécutés

| Action | Détail |
|--------|--------|
| Commande | `convert_beta_test01_cabinet --confirm-target` (rôle PG `muhimu`) |
| Type org | `sme` → **`cabinet`** |
| `CompanyAccess` | Reset ciblé puis : Fleuve → owner, comptable, viewer ; Niari → owner, **isol** |
| `DemoGrant` | `access_cabinet=true` (org demo) |
| Périmètre | **Uniquement** `beta-test-01` |

### Vérifications isolation (API — `run_beta_uat01_probes`)

| Utilisateur | Fleuve (main) | Niari (isol) | Conforme |
|-------------|---------------|--------------|----------|
| **owner** | 200 | 200 | Multi-dossiers OK |
| **isol** | **400** (refus) | 200 | OK |
| **viewer** | 200 | **400** (refus) | OK |

*(400 = société non autorisée / en-tête refusé — comportement attendu cabinet.)*

### Intégrité comptable

| Société | Σ débit = Σ crédit (posted) | Écritures posted (post-tests) |
|---------|------------------------------|-------------------------------|
| SARL Fleuve Congo | **3 300 000 / 3 300 000** XAF | Équilibre préservé |
| SARL Niari Logistique | **250 000 / 250 000** XAF | Inchangé |

Légère hausse Fleuve vs UAT-01 : **ré-exécution scénarios** (écritures test supplémentaires), **sans** reprovisioning destructif.

### Scénarios automatisés post-conversion

**`run_beta_test01_scenarios` : 18 / 18 OK** (ajustement S12 : refus **400/403/404** pour accès dossier interdit).

---

## 2. U1 — Parcours navigateur

### Diagnostic échec UAT-01

| Cause | Détail |
|-------|--------|
| URL | `https://127.0.0.1:18443` → **chrome-error** (certificat SAN) |
| Certificat | Self-signed ; SAN = `erp.beta.localhost`, `console.beta.localhost`, `localhost`, `127.0.0.1` (`deploy/beta/generate-certs.sh`) |
| Solution | Utiliser **`https://erp.beta.localhost:18443`** (résolution `.localhost` → loopback) |
| TLS | **Non** désactivé globalement |

### Preuves navigateur (2026-10-14)

| Élément | Résultat |
|---------|----------|
| `GET https://erp.beta.localhost:18443/login` | **200** — page « Muhimu ERP », formulaire Email / Mot de passe |
| Capture | Screenshot session UAT-02 (login + mention bêta fictive / non certifié) |

### Parcours 1–14 — statut

| Statut | Détail |
|--------|--------|
| **Validé (2026-10-15)** | **14 parcours métier** exécutés manuellement via UI (connexion, déconnexion, compta, PDF, masquage features, isolation société, exercices 2025/2026). |
| **Réserve session** | Sessions longues côté bêta : `SESSION_COOKIE_AGE=43200`, pas d’expiration inactivité ni cookie « session navigateur » — traité par **SEC-SESSION-01** (DEV/test), **non appliqué à la bêta** sans autorisation. |
| **Référence checklist** | **`docs/beta-testers/UAT_NAVIGATEUR_CHECKLIST.md`** |

**Mot de passe :** lu depuis **`.env.beta` local** par le testeur — l’agent **n’affiche pas** le secret dans les logs / rapports.

---

## 3. Sécurité des identifiants

| Contrôle | Résultat |
|----------|----------|
| Mot de passe par défaut dans le code | **Supprimé** — `default_password()` **exige** `BETA_TEST01_DEFAULT_PASSWORD` |
| Git | `.env.beta` **non** versionné ; variable documentée dans `.env.beta.example` |
| Rapports | **Aucun** secret publié (UAT-02) |
| Rotation | `provision_beta_test01 --rotate-passwords` exécuté après ajout env |
| Comptes test | `is_staff=false`, `is_superuser=false` |
| Ancien labo `BetaTest01!` | **Retiré** du code ; mention historique uniquement dans UAT-01 |

Distribution ops : transmettre le mot de passe **hors Git** (fichier local ops / canal sécurisé).

---

## 4. Exposition réseau

| Contrôle | Résultat |
|----------|----------|
| Internet / VPS | **Aucun** déploiement distant |
| Binding proxy (inspect Docker) | **`127.0.0.1:18080`** et **`127.0.0.1:18443`** (`docker-compose.beta.yml` BETA-UAT-02) |
| DEV / autres stacks | **Non modifiés** |
| Pare-feu OS | Non audité exhaustivement ; écoute **loopback** côté Docker |

**Note Windows :** `netstat` peut afficher des lignes `0.0.0.0:18443` selon le stack Docker Desktop ; **`HostIp: 127.0.0.1`** dans `docker inspect` fait foi pour la publication hôte.

---

## 5. Contrôles post-UAT-02 (non destructifs)

| Contrôle | Résultat |
|----------|----------|
| 18 scénarios BETA-TEST-01 | **18/18 OK** |
| Triggers ACC-03 | **4** |
| RLS | Inchangée (`muhimu_app` NOBYPASSRLS) |
| BETA-SCOPE | consolidation **403** ; flags **false** |
| PDF-CLAIM | **200** + mention « DOCUMENT DE TEST » (sonde) |
| Migrations / volumes / DEV | **Aucun** changement |

---

## Anomalies / risques résiduels

| ID | Sujet | Gravité |
|----|-------|---------|
| R1 | **Session bêta** — politique 12 h / 30 min idle / fermeture navigateur non déployée | **Moyen** (SEC-SESSION-01 en attente GO bêta) |
| R2 | Distribution mot de passe testeurs | Ops — hors Git |
| R3 | Certificat self-signed — procédure d’acceptation navigateur | Faible (doc checklist) |

---

## Fichiers / commandes ajoutés ou modifiés

| Élément | Rôle |
|---------|------|
| `convert_beta_test01_cabinet` | Conversion org fictive |
| `BETA_TEST01_DEFAULT_PASSWORD` | Secret ops (.env.beta) |
| `docker-compose.beta.yml` | Ports proxy loopback |
| `UAT_NAVIGATEUR_CHECKLIST.md` | Clôture U1 humaine |

---

## Restrictions respectées

Pas d’ouverture testeurs, deploy distant, migration, changement RLS/SYSCOHADA, prune, suppression volume, modification DEV, données réelles.

---

**BETA-UAT-02 : CONDITIONAL GO (U1 validé avec réserve session).**  
**Invitation testeurs : STOP — en attente de votre GO écrit.**
