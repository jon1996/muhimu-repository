# PDF-CLAIM — Rapport de remédiation des mentions de conformité

**Date :** 2026-10-13  
**Périmètre :** L4 PDF-CLAIM uniquement (textes, mentions, présentation — sans logique comptable)  
**Verdict :** **CONDITIONAL GO** (bêta privée, données fictives — aligné SYSCO-01)

---

## 1. Contexte

Les chantiers ACC-01/02/03, SAAS-03, ARCH-01, SEC-P0-01, OPS-01 et CLOSE-01 restent validés en DEV/test.  
Le mapping SYSCOHADA des états financiers n’est **pas** validé par un expert-comptable : toute revendication implicite de certification ou de conformité réglementaire sur les PDF/UI était un risque juridique et produit.

---

## 2. Formulations problématiques détectées (inventaire)

| Zone | Formulation / effet | Gravité |
|------|---------------------|---------|
| `notes_sn.py` — `DEFAULT_CONFORMITY` | « établis conformément au SYSCOHADA … sans réserve » | Élevée |
| `pdf_statements.py` — pied de page | « États numérotés et dates (art. 22 AUDCIF). Generation Muhimu ERP. » (ton réglementaire sans avertissement) | Moyenne |
| `pdf_statements.py` — note 2 PDF | « A. Conformité SYSCOHADA / PCGO » | Moyenne (libellé suggestif) |
| `frontend/.../etats/page.tsx` | Description liasse SN sans mention bêta / non certifié | Moyenne |
| `frontend` login / metadata | Positionnement produit sans garde-fou bêta | Faible |
| Titres PDF « Liasse SN SYSCOHADA » | Référentiel descriptif — **conservé** avec bandeau d’avertissement | Faible (atténué) |

**Non modifié (volontairement) :** références factuelles au PCGO, Titre IX, art. 19/22 AUDCIF dans l’aide à la lecture ; documentation d’audit (`docs/audit/*`) qui **déconseille** déjà les revendications ; comptes PCGO « officiels » (source normative) ; champs `approved_on` (approbation d’exercice métier, pas certification OHADA).

---

## 3. Formulations retenues

### Bandeau PDF (tous états financiers + livres légaux)

```
DOCUMENT DE TEST - DONNEES FICTIVES
Etat genere par MUHIMU Accounting, version beta.
Presentation et correspondances comptables en cours de validation.
Document non certifie et non destine au depot reglementaire.
```

### Pied de page PDF

```
Version beta — document non certifie. Numerotation et horodatage internes MUHIMU Accounting.
```

### Note 2 — section A (UI + PDF)

- **Libellé :** « Référentiel comptable et présentation (SYSCOHADA / PCGO) »
- **Texte par défaut :** précise le référentiel visé, l’état « en cours de validation », et exclut attestation / certification / validation par expert-comptable.

### Interface bêta

Bandeau global dans `AppShell` + copy login/metadata + description page États financiers.

---

## 4. Fichiers modifiés

| Fichier | Action |
|---------|--------|
| `backend/apps/ledger/services/pdf_disclaimers.py` | **Créé** — constantes partagées |
| `backend/apps/ledger/services/notes_sn.py` | Texte par défaut note 2 |
| `backend/apps/ledger/services/pdf_statements.py` | Bandeau, pied de page, libellé note 2 |
| `backend/apps/ledger/services/pdf_books.py` | Bandeau + pied de page |
| `backend/apps/ledger/tests/test_pdf_claim.py` | **Créé** — tests PDF-CLAIM |
| `backend/apps/ledger/tests/test_pdf_statements.py` | Assertions mises à jour |
| `frontend/components/beta-disclaimer-banner.tsx` | **Créé** |
| `frontend/components/app-shell.tsx` | Bandeau bêta |
| `frontend/app/app/[orgSlug]/etats/page.tsx` | Copy + libellé note 2 |
| `frontend/app/login/page.tsx` | Mention bêta |
| `frontend/app/layout.tsx` | Metadata |

**Aucune** migration, RLS, mapping SN, règle de calcul, ni donnée DEV modifiée.

---

## 5. PDF vérifiés (génération réelle ReportLab)

Kinds testés via `render_statements_pdf` sur payload SN représentatif :

- `liasse`, `bilan`, `result`, `tft`, `notes`

Contrôles : présence du bandeau, absence des sous-chaînes interdites (`FORBIDDEN_PDF_CLAIM_SUBSTRINGS`), montants issus du payload présents dans le flux PDF bilan.

---

## 6. Tests ajoutés / mis à jour

| Module | Rôle |
|--------|------|
| `test_pdf_claim.py` | Disclaimer sur tous les kinds ; interdiction revendications ; stabilité `build_bilan` / CR / TFT ; montants dans PDF |
| `test_pdf_statements.py` | Note 2 + bandeau « DOCUMENT DE TEST » |

---

## 7. Non-régression

| Suite | Résultat |
|-------|----------|
| PDF-CLAIM + `test_pdf_statements` | 15 OK |
| Suite Django complète (docker `muhimuerp`, base de test éphémère) | **333 OK** (328 existants + 5 PDF-CLAIM) |

Inclus implicitement : CLOSE-01, ACC immutabilité/SQL, SAAS-03 et reste du projet via la suite globale.

---

## 8. Risques résiduels

1. **Données utilisateur existantes** : une note 2 déjà saisie avec l’ancien texte « conformément … sans réserve » peut encore apparaître dans le PDF jusqu’à édition manuelle (le défaut pour les **nouveaux** exercices/notes est corrigé).
2. **Titres « … SYSCOHADA »** sur les PDF : descriptifs du référentiel visé ; le bandeau beta doit rester visible à l’impression.
3. **Validation expert-comptable** : non réalisée — le verdict produit reste **CONDITIONAL GO**, pas GO production réglementaire.
4. **Emails automatiques** : aucune mention problématique trouvée dans `backend/apps` (hors tests métier `approved_on`).

---

## 9. Verdict

**CONDITIONAL GO** pour la bêta privée avec données fictives :

- Revendications de certification atténuées sur le chemin PDF/UI principal.
- Avertissement explicite sur les exports.
- Calculs, mappings et totaux inchangés (vérifiés par tests existants + PDF-CLAIM).

**NO-GO** implicite pour dépôt réglementaire ou communication « conforme / certifié SYSCOHADA » tant que l’expert-comptable n’a pas validé le mapping.

---

*En attente d’instructions pour la suite (ex. migration du texte note 2 en masse, masquage de fonctionnalités expérimentales, revue copy marketing étendue).*
