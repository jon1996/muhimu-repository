# BETA_DEPLOYMENT_PLAN — Mise à jour bêta (non exécuté)

**Date :** 2026-10-13  
**Statut :** **plan uniquement** — aucune commande appliquée dans BETA-READINESS-01  
**Cible :** stack `muhimu-beta` (`docker-compose.beta.yml`, `.env.beta`)

---

## 0. Préconditions

- [ ] Autorisation écrite du responsable produit / ops
- [ ] Fenêtre maintenance communiquée aux testeurs (si instance déjà utilisée)
- [ ] Branche / tag de release identifié (commit incluant PDF-CLAIM, CLOSE-01, ACC-02/03, 333 tests verts)
- [ ] **Aucune** donnée réelle — rappel charte données fictives

---

## 1. Sauvegarde préalable

| Étape | Action | Vérification |
|-------|--------|--------------|
| 1.1 | `pg_dump` base `muhimu_beta` (format custom) vers `backups/postgres/` | SHA-256 + taille > 0 |
| 1.2 | Archive volume `beta_media` (pièces jointes) si utilisé | Liste fichiers |
| 1.3 | Copie `.env.beta` (hors git) | Secrets hors dépôt |
| 1.4 | Noter versions migrations actuelles | `django_migrations` ledger ≤ 0032 aujourd’hui |

Scripts existants : voir `docs/audit/OPS01_BACKUP_RESTORE_REPORT.md`, répertoire `backups/`.

---

## 2. Vérification des données (lecture seule)

| Contrôle | Commande / requête | Critère |
|----------|-------------------|---------|
| Volume | Compter org/sociétés/exercices | Cohérent avec charte fictive |
| Notes legacy | Voir `LEGACY_NOTES_REVIEW.md` | 0 texte problématique persisté (état audit) |
| POSTED entries | COUNT entries POSTED | Snapshot pour post-deploy |
| RLS | `relrowsecurity` sur tables tenancy/ledger | true |

**État audit 2026-10-13 :** bêta = **0 exercices** ; DEV = 5 exercices (jeux locaux).

---

## 3. Ordre des migrations

Exécution via service **`migrate`** (entrypoint propriétaire DB, pas `muhimu_app`) :

1. `docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta build migrate backend frontend console platform`
2. `docker compose … run --rm migrate` **ou** `up migrate` (selon compose actuel)
3. Migration attendue manquante : **`ledger.0033_acc03_sql_integrity`**
4. Vérifier : `SELECT name FROM django_migrations WHERE app='ledger' AND name='0033_acc03_sql_integrity';`

**Interdit :** migrations ad hoc SQL hors Django sans procédure ACC-03 documentée.

---

## 4. Déploiement du code

| Composant | DEV (référence) | Bêta (action plan) |
|-----------|-----------------|---------------------|
| Backend | volume `./backend` + image dev | **Rebuild** `muhimu-beta-api` production |
| Frontend | volume `./frontend` | **Rebuild** `muhimu-beta-web` |
| Platform | idem | **Rebuild** `muhimu-beta-platform-api` |
| Proxy nginx | config `deploy/beta/nginx.conf` | Redémarrer si certs/headers changent |

Commande type (à exécuter **sur autorisation**) :

```bash
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta up -d --build backend frontend console platform proxy
```

**Écart constaté :** images bêta du 2026-10-10 **sans** `pdf_disclaimers.py` ni bandeau frontend — rebuild **obligatoire** pour PDF-CLAIM.

---

## 5. Vérification triggers ACC-03

Sur `muhimu_beta` (tables `ledger_entry`, `ledger_entryline`) :

| Trigger attendu |
|-----------------|
| `trg_ledger_entry_forbid_posted_mutation` |
| `trg_ledger_entry_posted_balance` |
| `trg_ledger_entryline_balanced_deferred` |
| `trg_ledger_entryline_forbid_posted_substance` |

Si absent après 0033 : **STOP** — ne pas ouvrir aux testeurs.

---

## 6. Vérification RLS

| Test | Méthode |
|------|---------|
| Rôles | `muhimu_app` → `rolbypassrls = false` |
| Policies | Reprendre spot checks SAAS-03 (`test_isolation`) sur instance bêta **ou** requêtes `pg_policies` |
| Runtime | Connexion backend utilise `POSTGRES_APP_USER` |

---

## 7. Tests de fumée (post-deploy)

| # | Test | Attendu |
|---|------|---------|
| F1 | `GET /api/health` via proxy HTTPS | 200 |
| F2 | Login testeur (compte invité, pas bootstrap auto) | Session + CSRF |
| F3 | Liste sociétés + en-tête `X-Company-Id` | 200 |
| F4 | Créer brouillon écriture → valider | POSTED |
| F5 | Télécharger PDF liasse | Bandeau « DOCUMENT DE TEST » |
| F6 | Tentative DELETE écriture POSTED | 409 / immuable |
| F7 | (Optionnel) SQL direct `UPDATE ledger_entry` POSTED | Exception ACC-03 |

Suite automatisée recommandée : **`python manage.py test`** dans conteneur CI ou one-shot backend bêta sur base **clone** (pas prod test sur beta live si risque).

---

## 8. Contrôle PDF (PDF-CLAIM)

- Fichier présent : `apps/ledger/services/pdf_disclaimers.py`
- Tests : `apps.ledger.tests.test_pdf_claim`
- UI : `components/beta-disclaimer-banner.tsx` visible dans ERP

---

## 9. Vérification clôture (CLOSE-01)

Sur jeu **fictif dédié** (pas données client) :

- `preview_close` → `close_exercise` → `allocate_result` → `post_opening`
- Vérifier absence endpoint réouverture

Tests de référence : `apps.ledger.tests.test_close_e2e` (19 scénarios).

---

## 10. Retour arrière (rollback)

| Scénario | Action |
|----------|--------|
| Échec migrate | Restaurer dump pré-migrate ; ne pas laisser 0033 partielle |
| Bug code seul | Redéployer image N-1 (tag conservé) |
| Corruption données | Restore `pg_dump` + media backup |
| RLS / triggers | Restore garantit état cohérent ; re-jouer migrate seulement après fix |

Documenter dans ticket : heure, SHA image, nom backup, opérateur.

---

## 11. Durée estimée (lab)

| Phase | Durée indicative |
|-------|------------------|
| Backup | 5–15 min |
| Build + migrate | 10–25 min |
| Fumée + PDF | 15–30 min |
| **Total** | ~1 h |

---

*Plan préparé pour décision — exécution interdite sans autorisation explicite post BETA-READINESS-01.*
