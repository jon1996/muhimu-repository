# POST-SYSCO-01 — Plan de remédiation technique

**Date :** 2026-10-13  
**Nature :** plan **lecture seule** — aucun correctif implémenté  
**Base :** audit SYSCO-01 (`docs/audit/SYSCO01_*.md`) · code `backend/apps/ledger/**`  
**Avertissement :** ce plan **n’est pas** une certification SYSCOHADA / AUDCIF.

---

## 0. Synthèse exécutive

| Priorité | Ticket | Nature | Arbitrage EC ? | Complexité |
|---|---|---|---|---|
| P0 métier | SYSCO-01 | Mapping liasse | **Oui** (bloquant claim) | M–L |
| P1 tech | ACC-02 | Immutabilité écritures | Non (whitelist annotations) | M |
| P1 tech | ACC-03 | Intégrité D/C durable | Non (design technique) | M–L |
| P1 QA | CLOSE-01 | Clôture E2E | Partiel (jeux attendus) | M |
| P1 métier | REOPEN-01 | Réouverture | **Oui** (politique) | S–L selon option |
| P1 métier | NOTES-01 / SMT-01 | Notes & SMT | **Oui** | M |

**Ordre recommandé de réalisation (après autorisation) :**  
1) ACC-02 → 2) ACC-03 → 3) CLOSE-01 (tests E2E) → 4) hardening admin / wording PDF → 5) pack EC (SYSCO-01 / NOTES / SMT / REOPEN) → 6) correctifs mapping uniquement après PV.

**Verdict bêta actuelle :** inchangé — **CONDITIONAL GO** données fictives · **NO-GO** claim conformité.

---

## 1. ACC-02 — Immutabilité des écritures validées

### 1.1 Protection actuelle

| Couche | Comportement | Fichier |
|---|---|---|
| `Entry.save` | Refuse toute réécriture si statut DB déjà `posted`, sauf `allow_posted_write=True` | `models.py` |
| `EntryLine.save` | Refuse si l’écriture parente est `posted` | `models.py` |
| API update/delete | `update_draft` / `DELETE /entries` refusent hors brouillon | `posting.py`, `api.py` |
| Transition légitime | `post_entry` appelle `save(allow_posted_write=True)` une fois | `posting.py` |
| Correction légitime | `reverse_entry` crée une **nouvelle** écriture (montants négatifs) puis la poste | `posting.py` |

**Preuve d’écart documentée :** `tests/test_due_on.py`  
- `Entry.objects.filter(...).update(status=POSTED)` contourne `save`.  
- `set_line_due` utilise `EntryLine.objects.filter(...).update(due_on=...)` sur ligne liée à une écriture postée — **accepté aujourd’hui** pour les annotations.

### 1.2 Cartographie des voies de modification

#### A. Voies qui altèrent la **substance comptable** (montants, comptes, dates, statut, journal)

| Voie | Risque actuel | Commentaire |
|---|---|---|
| `Model.save()` | Faible | Bloqué pour `POSTED` |
| `QuerySet.update()` sur `Entry` / `EntryLine` | **Élevé** | Bypass total du `save` |
| `bulk_update()` | **Élevé** | Aucun usage ledger sur Entry/EntryLine aujourd’hui ; à interdire |
| `bulk_create` + `delete` via `_replace_lines` | Moyen | Réservé aux brouillons ; pas de garde-fou si appel hors service |
| SQL direct / `cursor.execute` | Faible (pas dans ledger) | Possible via shell / ops |
| API publique | Faible | Chemins métier contrôlés |
| Services internes (`closing`, `opening`, `fx`, `demo`, …) | Faible | Passent par `create_draft` / `post_entry` / `reverse_entry` |
| Imports comptes | N/A | `import_accounts` ne crée pas d’écritures |
| Django Admin `Entry` / inline | Moyen | `save` bloque les montants ; statut / champs Entry éditables tant que `save` déclenché ; shell admin toujours possible |
| Management commands | Faible | Pas de commandes mutantes Entry observées (hors sync PCGO) |
| Tests | Intentionnel | `.update(status=POSTED)` dans fixtures |

#### B. Voies qui modifient des **annotations** sur lignes postées (volontaires aujourd’hui)

| Champ | Service | Usage |
|---|---|---|
| `due_on` | `lettering.set_line_due` | Échéance auxiliaire |
| `lettering` | `lettering` letter / unletter | Lettrage |
| `third_party_id` | `lettering` bind | Rattachement tiers |
| `bank_pointage` | `bank_rec` | Pointage bancaire |

Ces champs ne changent pas D/C ni le compte — mais **contournent** le même mécanisme d’immutabilité. Toute remédiation doit **whitelist** ces annotations (ou les extraire dans une table séparée).

### 1.3 Protection proposée (sans l’implémenter)

#### Couche applicative (prioritaire, complexité M)

1. **Manager / QuerySet custom** sur `Entry` et `EntryLine` :
   - Surcharger `update()`, `bulk_update()`, éventuellement `delete()` pour lignes liées à `POSTED`.
   - Lever `ValidationError` / `ProtectedError` sauf :
     - `allow_posted_write=True` (transition `post_entry` uniquement) ;
     - whitelist d’annotations : `due_on`, `lettering`, `bank_pointage`, `third_party_id` (liste figée + revue).
2. **Interdire** `_replace_lines` si `entry.status == POSTED` (garde explicite même si déjà protégé en amont).
3. **Admin** : `readonly_fields` pour tous les champs substance dès `POSTED` ; désactiver delete ; documenter « corrections = contrepassation ».
4. **Service unique** `mutate_posted_annotation(line, fields)` pour lettrage / pointage / échéance — seul chemin autorisé hors `reverse_entry`.
5. **AuditLog** obligatoire sur annotations et sur `reverse_entry` (déjà partiel).

#### Couche PostgreSQL (recommandée en phase 2, complexité M–L)

Options (non exclusives) :

| Option | Principe | Avantage | Limite |
|---|---|---|---|
| **P1a** Trigger `BEFORE UPDATE` sur `ledger_entry` | Refuse UPDATE si `OLD.status='posted'` sauf colonnes techniques vides | Contre shell/SQL | Doit autoriser… rien, ou colonnes metadata nulles sur Entry |
| **P1b** Trigger `BEFORE UPDATE` sur `ledger_entryline` | Refuse UPDATE des colonnes substance (`debit`,`credit`,`account_id`,…) ; autorise whitelist | Aligné métier | Maintenance liste colonnes |
| **P1c** Rôle DB `muhimu_app` sans UPDATE sur tables Entry/Line | Droits SQL | Fort | Casse annotations tant qu’elles restent sur EntryLine |
| **P1d** Table `EntryLineAnnotation` | Sépare lettrage/pointage/échéance | Immutabilité stricte des lignes | Migration + refactor lettering/bank_rec |

**Recommandation plan :**  
- Sprint technique 1 : QuerySet + admin + garde `_replace_lines` (**sans migration**).  
- Sprint technique 2 (après autorisation migrations) : triggers P1b **ou** extraction annotations P1d.  
- Ne pas retirer `allow_posted_write` de `post_entry` (seul chemin de passage DRAFT→POSTED).

### 1.4 Mécanismes légitimes de correction (à conserver)

| Cas | Mécanisme | Règle |
|---|---|---|
| Erreur exercice courant | `reverse_entry` + nouvelle écriture | Art. 20 — origine intacte |
| Erreur après clôture | Voir §4 REOPEN — **pas d’update** | Décision EC |
| Annotation auxiliaire | Whitelist `update` | Pas de changement de solde |

### 1.5 Fichiers concernés (futurs)

- `backend/apps/ledger/models.py` (managers)  
- `backend/apps/ledger/services/posting.py`  
- `backend/apps/ledger/services/lettering.py`  
- `backend/apps/ledger/services/bank_rec.py`  
- `backend/apps/ledger/admin.py`  
- `backend/apps/ledger/tests/test_due_on.py` (+ nouveaux tests immutabilité)  
- Migration SQL éventuelle (phase 2, hors scope immédiat)

### 1.6 Critères d’acceptation ACC-02

- [ ] `Entry/EntryLine.objects.filter(...).update(debit=…)` / `status=…` / `account_id=…` **refuse** sur écriture postée.  
- [ ] `bulk_update` substance **refuse**.  
- [ ] `set_line_due` / lettering / pointage **continuent** de fonctionner.  
- [ ] `post_entry` et `reverse_entry` **inchangés** fonctionnellement.  
- [ ] Admin ne peut pas altérer une écriture postée.  
- [ ] Tests négatifs + non-régression lettering/bank_rec.

### 1.7 Risques ACC-02

- Casser lettrage / rapprochement si whitelist trop stricte.  
- Faux sentiment de sécurité sans couche SQL (shell superuser).  
- Perf négligeable sur `update` annoté.

---

## 2. ACC-03 — Intégrité débit / crédit

### 2.1 Contrôles existants

| Étape | Contrôle | Limite |
|---|---|---|
| `create_draft` / `update_draft` | `assert_double_entry` | Applicatif |
| `post_entry` | Re-contrôle avant POSTED + snapshots | Applicatif |
| Ligne unitaire | Interdit débit **et** crédit non nuls | Applicatif |
| Contrainte SQL multi-lignes | **Absente** | CHECK simple impossible |
| Snapshots | ACC-01 `F()` + verrou période | Cohérence mouvements ≠ équilibre écriture |
| Concurrence post | `test_snapshot_concurrency` | Solide pour soldes |

`assert_double_entry` : ≥2 lignes, ΣD=ΣC, total ≠0, classe 9 non mélangée.

### 2.2 Pourquoi pas un CHECK SQL inter-lignes

Un `CHECK` sur une ligne ne voit pas les autres. Un `CHECK` sur `Entry` nécessiterait des totaux dénormalisés. Toute solution multi-lignes doit être un **trigger / contrainte différée / procédure transactionnelle**.

### 2.3 Mécanismes proposés

#### Option A — Totaux dénormalisés + CHECK sur `Entry` (complexité M)

1. Colonnes `total_debit`, `total_credit` sur `Entry` (maintenues dans la même transaction que les lignes).  
2. `CHECK (status <> 'posted' OR total_debit = total_credit)`.  
3. `CHECK (status <> 'posted' OR total_debit > 0)`.  
4. Trigger sur `EntryLine` qui refuse INSERT/UPDATE/DELETE si parent `posted` (substance) — joint ACC-02.

**Avantage :** contrainte SQL lisible, indexable.  
**Risque :** dérive si totaux mal recalculés → recalcul obligatoire dans `post_entry` / `_replace_lines`.

#### Option B — Constraint trigger DEFERRABLE (complexité M–L)

```
CREATE CONSTRAINT TRIGGER trg_entry_balanced
  AFTER INSERT OR UPDATE OR DELETE ON ledger_entryline
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION ledger_assert_entry_balanced();
```

Fonction : si `entry.status = 'posted'`, `SUM(debit) = SUM(credit)` sinon `RAISE`.  
À la fin de transaction (`post_entry` atomique), l’équilibre est garanti même pendant les inserts intermédiaires.

**Avantage :** pas de dénormalisation.  
**Risque :** perf sur gros lots ; attention aux annotations UPDATE (ne doivent pas déclencher le check inutilement — `WHEN` sur colonnes substance).

#### Option C — Procédure / fonction RPC `post_entry_sql` (complexité L)

Toute validation passe par une fonction PL/pgSQL qui vérifie l’équilibre puis pose le statut.  
**Avantage :** une porte d’entrée DB.  
**Inconvénient :** double maintenance Django / SQL — **non recommandé** en premier choix.

**Recommandation plan :** **Option B** (trigger différé) + garde applicative existante + (optionnel) totaux dénormalisés en lecture pour diagnostics. Option A en complément si besoin de CHECK simple visible dans le schéma.

### 2.4 Tests à prévoir

| Famille | Scénario |
|---|---|
| Unitaire | Draft déséquilibré → 400 |
| Unitaire | Post déséquilibré (corruption lignes) → refus app + refus SQL |
| Concurrence | 2 posts parallèles même période (déjà ACC-01) + post + reverse |
| Import / demo | `seed_demo` reste équilibré |
| Rollback | Exception après insert lignes avant status POSTED → rien de posté, pas de snapshot |
| Annotation | Update `lettering` ne casse pas le trigger |
| Shell négatif | UPDATE manuel d’un montant → exception SQL |

### 2.5 Fichiers concernés (futurs)

- `services/posting.py`, `services/balance.py`  
- Migration SQL trigger (phase autorisée)  
- `tests/test_snapshot_concurrency.py` (+ nouveau `test_entry_balance_integrity.py`)

### 2.6 Critères d’acceptation ACC-03

- [ ] Impossible d’avoir une écriture `posted` avec ΣD ≠ ΣC, y compris via SQL app role.  
- [ ] `post_entry` / `reverse_entry` / clôture / AN / FX inchangés fonctionnellement.  
- [ ] Rollback transactionnel prouvé.  
- [ ] Perf acceptable sur jeu démo (cible : pas de régression > 20 % sur post batch).

### 2.7 Risques ACC-03

- Trigger mal cadré qui bloque les annotations.  
- Migration sur données existantes : scanner les écritures postées avant d’activer (script read-only de détection).  
- Environnements sans droits DDL (bêta) : déployer via migration Django standard.

---

## 3. CLOSE-01 — Clôture de bout en bout

### 3.1 Cartographie du processus

| # | Étape métier | État actuel | Code / API |
|---|---|---|---|
| 1 | Précontrôles (brouillons, période, statut) | **Partiel** | `preview_close` |
| 2 | Validation période(s) mensuelle(s) | **Existe** (hors close auto) | `validate_period` |
| 3 | Clôture IT + sceau | **Existe** (manuel, non chaîné) | `it_close_period` |
| 4 | Balance avant clôture | **Via** `trial_balance` dans preview/close | `balance.py` |
| 5 | OD arrêté 6/7/8 → 131/139 | **Implémenté** | `close_exercise` |
| 6 | Statut exercice `CLOSING` | **Enum présent, non utilisé** | `ExerciseStatus.CLOSING` |
| 7 | Verrouillage exercice `CLOSED` | **Implémenté** | `close_exercise` |
| 8 | Création exercice N+1 | **Implémenté** | `ensure_company_ledger` |
| 9 | Affectation AG (111/118/121/465) | **Implémenté séparé** | `allocate_result` |
| 10 | Paiement dividendes optionnel | **Implémenté** | `allocate_result` |
| 11 | Production états (bilan/CR/TFT) | **Indépendant** (génération à la demande) | `statements` / PDF |
| 12 | Report à nouveau (AN) | **Séparé** | `opening.post_opening` |
| 13 | Verrouillage automatique de toutes les périodes | **Manquant** | — |
| 14 | Tests E2E close + allocate + AN | **Manquants** | `test_closing.py` = helpers seuls |

### 3.2 Écarts vs parcours attendu bêta

1. `close_exercise` n’exige pas que les périodes 1–11 soient `IT_CLOSED` — seule la **dernière** doit rester `OPEN` pour passer l’OD.  
2. Pas d’état intermédiaire `CLOSING` (fenêtre de course).  
3. Pas de lien automatique close → états PDF → AN N+1.  
4. `restore_pnl_rows` ajuste l’affichage CR post-clôture — à valider EC (comportement documenté).  
5. Réserve légale 10 % / 20 % : heuristique SA/SARL — **VAL_METIER**.

### 3.3 Scénarios E2E proposés (attendus indépendants)

Réutiliser `SYSCO01_TEST_SCENARIOS.md` dossiers A/B + extension :

| ID | Enchaînement | Attendu indépendant |
|---|---|---|
| E2E-C1 | Scénarios 1–8 → `preview_close` | `can_close=true` ; XI = CA − charges calculé hors app |
| E2E-C2 | `close_exercise` | 1 écriture `result_close` ; classes 6/7/8 soldées ; 131 ou 139 = XI ; status CLOSED |
| E2E-C3 | Tentative `post_entry` sur N | Refus exercice clôturé |
| E2E-C4 | `allocate_result` bénéfice | Σ affectations = bénéfice ; écriture sur N+1 |
| E2E-C5 | `post_opening` N+1 | AN classes 1–5 + 13 ; pas de 6/7/8 ; D=C |
| E2E-C6 | Perte | 139 → 129 ; pas de dividendes |
| E2E-C7 | Brouillon restant | `can_close=false` |
| E2E-C8 | Double close | 409 |
| E2E-C9 | CR après close | XI pré-close = XI via `restore_pnl_rows` |
| E2E-C10 | Isolation 2 sociétés | Close A n’affecte pas B |

**Fichiers tests futurs :** `tests/test_close_e2e.py` (DB), jeux fixtures XOF.

### 3.4 Correctifs techniques possibles sans arbitrage EC

- Tests E2E C1–C10.  
- Utiliser `ExerciseStatus.CLOSING` pendant la transaction (réduit course).  
- Optionnel : chaîner IT-close des périodes 1…n-1 dans `close_exercise` (feature flag) — **à confirmer** si cela change le modèle opérationnel (plutôt VAL_METIER léger).  
- Documenter le flux UI : preview → close → allocate → opening.

### 3.5 Critères d’acceptation CLOSE-01

- [ ] Suite E2E verte sur SQLite/PG de test.  
- [ ] Attendus numériques du dossier A (XI, 131, AN) documentés et assertés.  
- [ ] Aucune régression `test_opening` / `test_closing` helpers.  
- [ ] Rapport de couverture CLOSE joint au pack EC.

### 3.6 Complexité / risques

- Complexité **M** (surtout fixtures).  
- Risque : flaky si dépend de `date.today()` (`closed_on`) — figer la date en test.  
- Risque métier : enchaînement IT-close auto non désiré par les pilotes.

---

## 4. REOPEN-01 — Réouverture d’exercice

### 4.1 État actuel

- `ExerciseStatus.CLOSED` bloque `post_entry` et `post_opening`.  
- **Aucune** API / service `reopen_exercise`.  
- Correction prévue : contrepassation sur période ouverte (souvent N+1 via art. 22-4).  
- Scénario SYSCO 16 : **refus** de réouverture = non-régression négative attendue tant que politique absente.

### 4.2 Alternatives (aucune inventée comme « officielle »)

| Option | Description | Quand | Risques |
|---|---|---|---|
| **R0 — Statu quo bêta** | Pas de réouverture ; corrections sur N+1 (contrepassation / OD) + notes | Bêta fictive | Moins flexible pour pilotes |
| **R1 — Réouverture contrôlée** | Passage CLOSED→OPEN (ou CLOSING) avec double approbation, motif, AuditLog, invalidation sceaux périodes, blocage si AN N+1 déjà posté ou états « publiés » | Après PV EC | Complexe ; peut invalider liasses déjà émises |
| **R2 — Correctifs N+1 uniquement** | Documenter procédure art. 20 exercice antérieur → RAN + notes | Aligné AUDCIF cité | Notes encore partielles (NOTES-01) |
| **R3 — Procédure exceptionnelle plateforme** | Runbook ops + script supervised (hors self-service) + PV | Incidents lab | Contourne produit ; piste d’audit critique |

### 4.3 Décisions nécessitant l’avis EC

1. La réouverture self-service est-elle **souhaitable** pour une PME OHADA, ou faut-il l’interdire ?  
2. Si R1 : quelles conditions (affectation déjà faite ? dividendes payés ? PDF déjà générés ?)  
3. Traitement des sceaux `it_close` / hash période après réouverture.  
4. Suffisance de R2 + notes pour la première bêta.

### 4.4 Recommandation plan (en attente décision)

- **Bêta privée :** adopter **R0 + R2 documenté** (pas de code reopen).  
- Préparer **spécification R1** (ADR) pour validation EC, **sans implémenter**.  
- Critère GO produit élargi : PV EC sur la politique choisie.

### 4.5 Si R1 est un jour autorisé — esquisse technique (non démarrée)

Fichiers : `closing.py` / `api.py` / `models.Exercise` / AuditLog.  
Précontrôles : pas d’écriture `allocation`/`opening` dépendante non contrepassée ; motif obligatoire ; rôle `org_admin` + second approbateur ; statut `CLOSING` pendant travaux ; re-close obligatoire.

Complexité **L** · dépendance forte EC.

---

## 5. Dépendances SYSCOHADA — classification A / B / C

### A. Correctifs techniques **sans** arbitrage comptable

| ID | Travaux | Prérequis |
|---|---|---|
| ACC-02 | Managers immutabilité + admin + whitelist annotations | Autorisation code |
| ACC-03 | Trigger différé / totaux + tests | Autorisation code **+ migration** |
| CLOSE-01 | Tests E2E + éventuellement statut CLOSING | Autorisation code |
| PDF-CLAIM | Retirer / neutraliser libellés « conforme SYSCOHADA » | Autorisation code |
| DOC | Pointer runbooks vers ce plan + pack EC | Docs only |
| OPS-scan | Script read-only détection écritures déséquilibrées avant trigger | Autorisation script lab |

### B. Correctifs **nécessitant** validation expert-comptable

| ID | Travaux | Livrable EC |
|---|---|---|
| SYSCO-01 | Ajustements `sn_map` / `smt_map` / formules TFT-SIG | PV grille pack EC |
| NOTES-01 | Périmètre notes minimales | Liste notes obligatoires |
| SMT-01 | Seuils / devise / bascule régime | Avis SMT |
| CLOSE métier | IT-close auto ? réserve légale ? | Avis |
| REOPEN-01 | Choix R0/R1/R2/R3 | Avis politique |
| TAX-01 | Hors moteur : confirmation exclusion TVA nationale | Avis fiscaliste pays (si besoin) |

### C. À **exclure** du périmètre première bêta privée

| Domaine | Motif |
|---|---|
| Claim / certification SYSCOHADA | NO-GO explicite |
| TVA / IS déclaratifs nationaux | Hors moteur |
| Réouverture self-service (R1) | Tant que pas de PV |
| Banques / assurances / NPO | Hors AUDCIF art. 5 al. 4 (doc ledger) |
| Consolidation avancée | Partiel ; non critique bêta mono-société |
| Notes annexes exhaustives | NOTES-01 |
| Inventaire physique annuel complet | Partiel stocks |
| Contournement SQL superuser | Accepté lab ; hors threat model SaaS app role |

---

## 6. Plan de livraison

### 6.1 Lots proposés

| Lot | Contenu | Complexité | Dépendances | GO lot |
|---|---|---|---|---|
| **L0** | Ce plan + transmission pack EC | S | — | Docs livrés |
| **L1** | ACC-02 applicatif | M | Autorisation code | Critères §1.6 |
| **L2** | ACC-03 SQL + tests | M–L | L1 + autorisation migration | Critères §2.6 |
| **L3** | CLOSE-01 E2E | M | Autorisation code | Critères §3.5 |
| **L4** | PDF-CLAIM + admin hardening | S | Autorisation code | Plus de claim abusif |
| **L5** | Revue EC (PV) | — | Pack SYSCO-01 | Grille signée |
| **L6** | Mapping SN/SMT/Notes | M–L | L5 + autorisation | Écarts P0 traités |
| **L7** | REOPEN (si R1 choisi) | L | L5 | Spec + tests + audit trail |

### 6.2 Stratégie de tests globale

1. Conserver les **265** tests comme filet.  
2. Ajouter suites dédiées : immutabilité, balance SQL, close E2E.  
3. Jeux indépendants SYSCO scénarios 1–8, 15–18.  
4. Pas de mutation DEV/bêta pour prouver : uniquement DB de test / lab isolé.  
5. Avant activation trigger ACC-03 en bêta : scan read-only d’équilibre.

### 6.3 Conditions GO / NO-GO (jalons)

| Jalon | GO | NO-GO |
|---|---|---|
| Bêta privée fictive (actuel) | Réserves SYSCO-01 respectées | Claim conformité ; données réelles clients |
| Après L1–L3 | Intégrité technique renforcée | Échec tests immutabilité / E2E close |
| Après L5 (PV EC) | Mapping validé ou liste d’écarts acceptés | PV « non validé » sans plan |
| Élargissement pilotes | L6 + réserves levées | Liasse non revue ; REOPEN ambigu |

### 6.4 Estimation de complexité (indicatif)

| Lot | Effort relatif | Notes |
|---|---|---|
| L1 ACC-02 | 2–4 j | Attention lettering/bank_rec |
| L2 ACC-03 | 3–6 j | Inclut migration + scan |
| L3 CLOSE E2E | 2–4 j | Fixtures riches |
| L4 wording/admin | 0,5–1 j | |
| L5 EC | 1–2 j EC | Hors eng. logiciel |
| L6 mapping | 3–10 j | Selon PV |
| L7 reopen | 5–15 j | Si retenu |

### 6.5 Risques transverses

| Risque | Mitigation |
|---|---|
| Implémenter avant autorisation | **Interdit** — attendre décision |
| Corriger le mapping sans EC | Reporter en L6 |
| Migration RLS / rôles cassés | Toute migration ACC-03 revue isolation SAAS-03 |
| Régression snapshots ACC-01 | Garder `test_snapshot_concurrency` gate |
| Confusion certification | Communiquer CONDITIONAL GO uniquement |

---

## 7. Décisions attendues du product owner

Merci de trancher avant tout correctif :

1. **Autoriser L1 (ACC-02 applicatif) ?** oui / non / plus tard  
2. **Autoriser L2 (ACC-03 + migration) ?** oui / non / après L1 seulement  
3. **Autoriser L3 (tests E2E close) ?** oui / non  
4. **Autoriser L4 (retrait claims PDF) ?** oui / non  
5. **Politique REOPEN pour la bêta :** R0+R2 (recommandé) / préparer spec R1 / autre  
6. **Calendrier revue EC (L5) :** date cible ?

---

## 8. Références

- `docs/audit/SYSCO01_ACCOUNTING_AUDIT_REPORT.md`  
- `docs/audit/SYSCO01_REQUIREMENTS_MATRIX.md`  
- `docs/audit/SYSCO01_TEST_SCENARIOS.md`  
- `docs/audit/SYSCO01_FINANCIAL_STATEMENTS_REVIEW.md`  
- `docs/audit/SYSCO01_EXPERT_VALIDATION_PACK.md`  
- `docs/ledger.md`  
- Code : `services/posting.py`, `closing.py`, `opening.py`, `periods.py`, `lettering.py`, `bank_rec.py`, `models.py`, `tests/test_due_on.py`, `tests/test_closing.py`

---

*Fin du plan — aucun correctif démarré.*
