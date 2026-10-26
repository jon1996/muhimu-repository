# BETA-UAT-01 — Validation manuelle et sécurité des parcours (bêta locale)

**Date :** 2026-10-14  
**Cible :** `muhimu-beta` / `muhimu_beta` · jeu **`beta-test-01`** (BETA-TEST-01)  
**Références :** `BETA_TEST01_REPORT.md`, `BETA_DEPLOY01_REPORT.md`, `BETA_FEATURE_SCOPE.md`

---

## Verdict

| Verdict | Signification |
|---------|----------------|
| **CONDITIONAL GO** | Contrôles API / modèle / intégrité / docs testeurs **OK** avec réserves ; **ouverture testeurs : NO-GO** tant que l’**UAT navigateur humain** n’est pas faite et que l’**écart org SME vs parcours « 2 dossiers »** n’est pas tranché produit. |

---

## Phase 1 — Organisations SME vs CABINET

### Comportement **spécifié** (code — non modifié)

| Type | Règle applicative (`tenancy/middleware.py`) | Intention |
|------|---------------------------------------------|-----------|
| **SME (PME)** | Tout membre actif voit **toutes** les sociétés de l’org (`user_can_access_company` → `True` si `OrganizationType.SME`) | **Intentionnel** — PME mono/multi-société sans granularité `CompanyAccess` |
| **SME** | `companies_queryset_for` : idem pour rôles non admin | Liste sociétés = toutes les sociétés actives de l’org |
| **CABINET** | Accès société via **`CompanyAccess`** (sauf owner/admin) | **Intentionnel** — dossiers clients séparés |
| **CABINET** | RLS PostgreSQL : `test_rls_hides_unassigned_company_rows_within_cabinet` (suite DEV) | Défense en profondeur **company-level** |

### État **réel** sur la bêta (`beta-test-01`)

| Constats | Preuve |
|----------|--------|
| Type org en base = **`sme`** | `SELECT type FROM tenancy_organization WHERE slug='beta-test-01'` |
| Lignes **`CompanyAccess`** présentes (Fleuve / Niari) | Matrice SQL 2026-10-14 |
| **`user_can_access_company`** : `isol` viewer → **True** sur Fleuve **et** Niari | Commande `run_beta_uat01_probes` |
| **API** `GET /api/ledger/entries` : `isol` → **200** sur **les deux** sociétés | Idem |

**Conclusion SME :** pour une org **PME**, l’accès à toutes les sociétés est **conforme au code**, pas une anomalie logicielle.

**Conclusion CABINET sur bêta :** le jeu `beta-test-01` **ne se comporte pas comme un cabinet** tant que `type=sme`. Les lignes `CompanyAccess` **ne restreignent pas** l’API pour les rôles non admin. **Écart** avec le scénario BETA-TEST-01 « isolation dossier Niari » si l’org reste SME.

### Risques résiduels (Phase 1)

| Risque | Gravité | Mitigation proposée (sans exécution ici) |
|--------|---------|------------------------------------------|
| Testeurs « isol » voient les 2 sociétés | **Moyenne** | Décision produit : passer l’org en **`cabinet`** + re-provision **ou** ne garder qu’**une** société pour le pilote PME |
| Confusion doc BETA-TEST-01 (mention cabinet) vs DB SME | **Faible** | Aligner doc + type org après validation écrite |

**Aucune modification du modèle de permissions** n’a été effectuée dans BETA-UAT-01.

---

## Phase 2 — Parcours utilisateur (UI réelle)

### Environnement

- Tentative d’accès navigateur automatisé : `https://127.0.0.1:18443/login` et `https://localhost:18443/login` → **échec certificat / chrome-error** (self-signed, hôte non configuré dans l’outil).
- **Les tests API ci-dessous ne remplacent pas** une session ERP dans le navigateur (cookies, CSRF, en-têtes `X-Company-Id` posés par le frontend).

### Parcours — statut

| # | Parcours | UI manuelle | Contrôle indirect (API / SQL) |
|---|----------|-------------|-------------------------------|
| 1 | Connexion / déconnexion | **Non vérifié** | Login API **200** (sonde owner) |
| 2 | Accès société autorisée | **Non vérifié** | Entries **200** avec `X-Company-Id` |
| 3 | Plan comptable | **Non vérifié** | 1396 comptes SYSCOHADA (TEST-01) |
| 4 | Journaux | **Non vérifié** | 7 journaux / société (SQL) |
| 5 | Saisie écriture | **Non vérifié** | Couvert par BETA-TEST-01 S04–S05 |
| 6 | Validation | **Non vérifié** | S06 TEST-01 |
| 7 | Grand livre | **Non vérifié** | S08 TEST-01 |
| 8 | Balance | **Non vérifié** | S09 + Σ posted équilibré (SQL) |
| 9 | PDF + avertissement | **Non vérifié** | PDF **200** + `DOCUMENT DE TEST` (sonde) |
| 10 | Fonctions expérimentales | **Non vérifié** | Flags `false` dans `/api/ledger/beta-scope` |
| 11 | Masquage exclus | **Non vérifié** | Menu : à valider humain ; API consolidation **403** |
| 12 | Refus accès non autorisé | **Non vérifié UI** | Viewer post → **403** (TEST-01) ; **isol + SME** → accès **non** restreint (cf. Phase 1) |
| 13 | Exercice **2025** clôturé | **Non vérifié UI** | SQL : `status=closed`, 2 écritures posted |
| 14 | Exercice **2026** ouvert | **Non vérifié UI** | SQL : `status=open`, 7 + 1 écritures |

### Étapes **humaines** restantes (checklist)

1. Hosts : `127.0.0.1 erp.beta.localhost` (si requis).
2. Accepter certificat bêta.
3. Exécuter `GUIDE_TEST_COMPTABLE.md` avec **owner**, **comptable**, **viewer**.
4. Vérifier menu (absence consolidés / classe 9 / RSE) et bandeau bêta.
5. Confirmer sélecteur de société vs profil **isol**.

---

## Phase 3 — Sécurité

| Contrôle | Résultat |
|----------|----------|
| Exposition Internet | **Pas de déploiement distant** ; proxy écoute **`0.0.0.0:18080/18443`** → accessible **LAN hôte**, pas une bêta « Internet » |
| Secrets dans Git | Emails test dans repo ; **mot de passe par défaut** `BetaTest01!` dans `provision.py` (**lab**) — **à remplacer** via `BETA_TEST01_DEFAULT_PASSWORD` avant testeurs ; pas de `.env.beta` versionné |
| Logs | Pas d’audit exhaustif des logs conteneurs ; procédure ops : ne pas logger les POST login en clair |
| Privilèges comptes test | `is_staff=false`, `is_superuser=false` (SQL) |
| BETA-SCOPE API | consolidation **403** ; flags tous **false** (sonde) |
| RLS / rôles PG | `muhimu_app` **NOBYPASSRLS** ; 4 triggers ACC-03 ; inchangé |
| PDF-CLAIM | Présent sur PDF API (sonde) |
| Contournement CABINET | **Non applicable** sur bêta actuelle (org **SME**) ; tests DEV **CABINET+RLS** passent en CI |

---

## Phase 4 — Intégrité des données (lecture seule)

| Contrôle | Attendu | Obtenu |
|----------|---------|--------|
| Σ posted Fleuve | D = C | **3 250 000** / **3 250 000** XAF |
| Σ posted Niari | D = C | **250 000** / **250 000** XAF |
| Exercice 2025 Fleuve | Clôturé | **closed**, 2 écritures |
| Exercice 2026 | Ouvert | **open** |
| Re-provisioning | Interdit | **Non exécuté** |
| Nouvelle clôture | Interdit | **Non exécutée** |

---

## Phase 5 — Documents testeurs (préparés, non envoyés)

| Document | Chemin |
|----------|--------|
| Guide connexion | `docs/beta-testers/GUIDE_CONNEXION.md` |
| Guide test comptable | `docs/beta-testers/GUIDE_TEST_COMPTABLE.md` |
| Grille anomalies | `docs/beta-testers/GRILLE_ANOMALIES.md` |
| Fonctionnalités autorisées / exclues | `docs/beta-testers/FONCTIONNALITES_BETA.md` |
| Questionnaire expert-comptable | `docs/beta-testers/QUESTIONNAIRE_EXPERT_COMPTABLE.md` |
| Emails (sans mots de passe) | `docs/audit/BETA_TEST01_CREDENTIALS.example.md` |

---

## Anomalies bloquantes (ouverture testeurs)

| ID | Anomalie | Bloquant ? |
|----|----------|------------|
| U1 | **UAT navigateur non réalisée** | **Oui** (parcours 1–14 UI) |
| U2 | Org **`beta-test-01` en SME** vs scénario « 2 dossiers isolés » | **Oui** si testeurs isolés par dossier |
| U3 | Mot de passe labo dans code source (`provision.py`) | **Conditionnel** — rotation env avant GO |

---

## Outils / preuves

- Sonde read-only : `python manage.py run_beta_uat01_probes --confirm-target` (rôle PG `muhimu`, one-shot).
- Sauvegarde disponible : `backups/postgres/muhimu_beta_20261014_test01_pre.dump`.

---

## Restrictions respectées

Aucun accès Internet, invitation, deploy, migration, changement RLS, modification SYSCOHADA, prune, suppression volume, modification DEV, données réelles.

---

**BETA-UAT-01 : CONDITIONAL GO** (préparation + contrôles techniques).  
**Ouverture testeurs : STOP — en attente de votre autorisation écrite et clôture U1/U2.**
