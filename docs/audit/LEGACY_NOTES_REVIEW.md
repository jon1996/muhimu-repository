# LEGACY_NOTES_REVIEW — Notes 2 historiques (PDF-CLAIM / BETA-READINESS-01)

**Date :** 2026-10-13  
**Mode :** lecture seule · **aucune note modifiée**  
**Périmètre données :** PostgreSQL DEV (`muhimu`, projet `muhimuerp`) et bêta (`muhimu_beta`, projet `muhimu-beta`)

---

## 1. Modèle et personnalisation

| Élément | Détail |
|---------|--------|
| Stockage | Champ `ledger_exercise.notes_annexes` (JSON texte, notes 1–36) |
| Note 2 | Sections `conformity`, `methods`, `derogations`, `extra` (Titre IX) |
| Défaut applicatif | Si champ vide → `parse_notes()` injecte `DEFAULT_CONFORMITY` depuis le **code** (`notes_sn.py`, corrigé PDF-CLAIM le 2026-10-13) |
| Personnalisation | Oui — PATCH `/api/ledger/exercise/notes` (rôle writer : owner / admin / accountant) |
| Horodatage exercice | Pas de `updated_at` sur `Exercise` ; pas de table d’historique des révisions de notes |

---

## 2. Requêtes d’inventaire (sans contenu confidentiel)

Critères SQL (ILIKE) : `conform`, `certif`, `expert-comptable`, `sans réserve`, `sans reserve`.

| Environnement | Exercices total | `notes_annexes` non vides | Correspondances critères problématiques |
|---------------|-----------------|---------------------------|----------------------------------------|
| DEV | 5 | **0** | **0** |
| Bêta | 0 | **0** | **0** |

**Conclusion :** aucune note 2 **persistée** avec formulation legacy dans les bases actuelles. Les risques résiduels concernent :

1. **Futurs enregistrements** saisis manuellement avec un libellé de certification.
2. **Texte par défaut en mémoire** (déjà corrigé dans le dépôt DEV ; **non déployé** sur l’image bêta au moment de l’audit — voir `BETA_READINESS_REPORT.md`).

---

## 3. Typologie (structure — sans extraire de données métier)

Pour tout enregistrement futur détecté, le rapport opérationnel utilisera :

| Champ rapport | Description |
|---------------|-------------|
| `org_ref` | Identifiant anonyme (ex. hash 8 car. de l’UUID organisation) |
| `company_ref` | Identifiant anonyme société |
| `exercise_year` | Année fiscale |
| `note_type` | Toujours « note 2 — règles et méthodes » si `conformity` concerné |
| `pattern` | Catégorie (`conformement_sans_reserve`, `certifie`, `expert_comptable`, autre) |
| `customized` | `true` si JSON diffère du défaut sérialisé à la date PDF-CLAIM |
| `source` | `persisted` vs `runtime_default` |

*Inventaire actuel : **0 ligne** à lister.*

---

## 4. Trois traitements proposés (sans exécution)

### A. Avertissement obligatoire à l’export

- **Principe :** conserver le texte utilisateur mais **préfixer** le PDF (déjà partiellement fait via bandeau beta global PDF-CLAIM).
- **Renforcement possible :** si `conformity` matche une liste de motifs legacy → bloc additionnel dans le PDF notes + toast UI avant téléchargement.
- **Avantages :** zéro migration ; traçabilité du texte saisi par le testeur.
- **Inconvénients :** le libellé problématique reste visible dans le corps de la note.

### B. Révision manuelle + historique

- **Principe :** workflow UI « revue conformité note 2 » réservé owner/admin ; journal d’audit (`record_audit`) sur PATCH notes.
- **Avantages :** adapté pilote EC ; pas de script de masse.
- **Inconvénients :** nécessite discipline utilisateur ; pas d’historique de versions aujourd’hui (à concevoir).

### C. Migration ciblée (sur autorisation uniquement)

- **Périmètre strict :** remplacer **uniquement** le texte **identique byte-à-byte** à l’ancien `DEFAULT_CONFORMITY` PDF-CLAIM (chaîne historique « établis conformément … sans réserve »).
- **Prérequis :** sauvegarde `pg_dump` + fenêtre maintenance + rapport de comptage avant/après.
- **État actuel :** **0 enregistrement** éligible sur DEV et bêta → migration **non nécessaire** aujourd’hui.
- **Avantages :** nettoyage silencieux des défauts figés en base.
- **Inconvénients :** ne couvre pas les variantes rédigées par l’utilisateur.

---

## 5. Recommandation BETA-READINESS-01

| Priorité | Action |
|----------|--------|
| P0 | Déployer le **code PDF-CLAIM** sur bêta (défaut note 2 + bandeau PDF) — voir plan de déploiement |
| P1 | Adopter **A + détection** pour tout futur PATCH `conformity` contenant motifs interdits (alerte, pas blocage saisie) |
| P2 | Réserver **C** à une autorisation explicite si un scan post-lancement trouve des défauts legacy persistés |

**Aucune modification de note exécutée dans le cadre de cet audit.**
