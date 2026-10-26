# BETA-SCOPE-01 — Rapport d’implémentation feature flags

**Date :** 2026-10-14  
**Périmètre :** code + tests DEV/test uniquement · **aucun déploiement bêta**  
**Référence :** `BETA_FEATURE_SCOPE.md`, `BETA_READINESS_REPORT.md`

---

## Verdict

**GO** pour intégration DEV/test : restrictions API + UI cohérentes, défauts sécurisés en mode restrict, suite **345 tests OK** (333 + 12 BETA-SCOPE).

**CONDITIONAL GO** pour activation en stack bêta : nécessite **rebuild + redeploy** autorisé (hors périmètre de ce chantier).

---

## 1. Fonctionnalités couvertes

| Feature flag | Domaine | Statut bêta par défaut (`BETA_SCOPE_RESTRICT=1`) |
|--------------|---------|---------------------------------------------------|
| `consolidation` | Groupes consolidés / combinés, PDF | **Désactivé** |
| `class9_cage` | Classe 9, CAGE, POST commitment `/class9` | **Désactivé** |
| `esg` | RSE / note 35 | **Désactivé** |
| `escompte` | Preview escompte + side-effects post/reverse | **Désactivé** |

**Non modifié (volontairement) :** réouverture d’exercice (absente, R0+R2) ; cœur comptable (journal, balance, clôture, états PDF avec disclaimers PDF-CLAIM) ; fiscalité nationale (inexistante).

---

## 2. Configuration centralisée

| Fichier | Rôle |
|---------|------|
| `backend/config/settings.py` | `BETA_SCOPE_RESTRICT` (défaut : `not DEBUG`), dict `BETA_FEATURES` |
| `backend/apps/ledger/beta_scope.py` | `require_beta_feature()`, `beta_scope_payload()`, constantes |
| `.env.beta.example` | Documentation variables `BETA_FEATURES_*` |

**Sémantique :**

- Variable explicite `BETA_FEATURES_<NAME>=1` → fonctionnalité **activée**.
- Variable `=0` → **désactivée**.
- Variable absente + `BETA_SCOPE_RESTRICT=0` (DEV typique) → **activée** (non-régression).
- Variable absente + `BETA_SCOPE_RESTRICT=1` (bêta `DEBUG=0`) → **désactivée** (sécurisé).

---

## 3. Endpoints protégés (403 si désactivé)

| Préfixe / route | Flag |
|-----------------|------|
| `GET/POST/PATCH/DELETE /api/ledger/consolidation…` | `consolidation` |
| `GET /api/ledger/consolidation/{id}/pdf` | `consolidation` |
| `GET /api/ledger/class9` | `class9_cage` |
| `GET/POST/PATCH /api/ledger/cage…` | `class9_cage` |
| `POST /api/ledger/commitments/{id}/class9` | `class9_cage` |
| `GET/PUT /api/ledger/esg` | `esg` |
| `POST /api/ledger/escompte/preview` | `escompte` |

**Effets escompte (sans endpoint dédié) :** `sync_discount_commitment` / `close_discount_for_entry` ignorés si `escompte` désactivé (validation d’écriture inchangée).

**Découverte UI :** `GET /api/ledger/beta-scope` (membre authentifié, sans société requise).

---

## 4. Frontend

| Élément | Comportement |
|---------|--------------|
| `lib/beta-scope.ts` | Types + filtre navigation |
| `components/beta-scope-context.tsx` | Contexte partagé |
| `components/beta-scope-gate.tsx` | Blocage accès direct URL |
| `components/app-shell.tsx` | Charge `/beta-scope`, filtre menu |
| Pages `consolides`, `classe-9`, `rse` | Gate feature |
| `entry-form.tsx` | Masque escompte ; pas d’appel CAGE si off |
| `engagements/page.tsx` | Masque colonne / bouton 90/91 si off |

---

## 5. Tests ajoutés

**Module :** `backend/apps/ledger/tests/test_beta_scope.py` (12 tests)

| Cas | Vérification |
|-----|--------------|
| Settings DEV-like | Features ouvertes si `BETA_SCOPE_RESTRICT=False` |
| Settings bêta-like | Features fermées si dict RESTRICTED |
| API consolidation / class9 / cage / esg / escompte | **403** quand désactivé |
| Balance + PDF états | Toujours accessibles (200 ou 400 métier) |
| Flag réactivé | Consolidation **200** |
| Spoof company autre org | **400/403** (isolation inchangée) |

---

## 6. Non-régression

```
Ran 345 tests in ~561s — OK
```

Inclut CLOSE-01, PDF-CLAIM, SAAS-03, ACC, etc.

---

## 7. Anomalies / limites résiduelles

| ID | Description | Gravité |
|----|-------------|---------|
| R1 | Stack **muhimu-beta** non mise à jour (pas de deploy autorisé) | Attendu |
| R2 | Viewer peut encore lire balance/états (by design `require_company`) | Faible |
| R3 | Services métier (ex. `test_consolidation`) restent appelables hors HTTP | Acceptable |
| R4 | Frontend hors `AppShell` (login) n’expose pas le scope | N/A |

---

## 8. Actions post-validation (sur instruction)

1. Rebuild images bêta + redeploy (voir `BETA_DEPLOYMENT_PLAN.md`).
2. Vérifier fumée : menu sans Consolidés/RSE/Classe 9 ; API 403 sur routes ci-dessus.
3. Optionnel : activer une feature pilote via `BETA_FEATURES_*=1` sur une org de test.

---

*En attente de validation avant toute opération sur l’environnement bêta.*
