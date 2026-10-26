# Rapport d’intégrité comptable

## 1. Synthèse

Le moteur utilise des types adaptés (`DecimalField`, `quantize` selon devise) et impose la partie double côté application. Les risques principaux sont la **concurrence sur les snapshots**, l’**absence de garde SQL d’équilibre**, et le **contournement d’immuabilité** via `QuerySet.update` pour certains champs.

**Exécution tests (2026-10-10, Docker) :** 195 tests, 0 échec, 0 ignoré. Voir `TEST_RUN_REPORT.md`.

## 2. Types numériques et arrondis

| Règle | Implémentation | Statut |
|---|---|---|
| Pas de `float` métier | `Decimal` / `parse_amount` | OK (revue code) |
| XOF/XAF/KMF/GNF = 0 décimale | `ZERO_DECIMAL_CURRENCIES` | OK + tests format |
| CDF = 2 décimales | `ohada.py` + tests PDF | OK |
| Arrondi | `ROUND_HALF_UP` | OK |

## 3. Équilibre et validation

| Contrôle | Où | Limite |
|---|---|---|
| ≥ 2 lignes, débit = crédit | `posting.assert_double_entry` | Application seule |
| Classe 9 non mélangée 1–8 | idem | OK |
| Numérotation séquentielle | `JournalSequence` + `select_for_update` | OK |
| Immuabilité `save()` | `Entry` / `EntryLine` | Contournable par `.update()` |

## 4. Cohérence journaux / grand-livre / balance

Flux prévu :

1. `post_entry` → `apply_posted_lines` met à jour `BalanceSnapshot`.
2. Balance / états lisent les snapshots.
3. Grand-livre lit les lignes + solde d’ouverture snapshot.

**Risque silencieux :** si deux validations concurrentes touchent le même compte/période, les increments `mov_debit` / `mov_credit` peuvent se perdre (read-modify-write sans verrou) → balance ≠ somme des lignes.

## 5. Transactions et idempotence

| Mécanisme | Statut |
|---|---|
| `@transaction.atomic` sur post/close/opening | Présent |
| `idempotency_key` unique par société | Présent ; ne compare pas le payload |
| Prévention enregistrements partiels | Globalement OK via atomic |

## 6. Erreurs silencieuses possibles

1. Drift snapshot sous concurrence (P0 ACC-01).
2. Idempotency qui renvoie une pièce différente du payload demandé.
3. Mise à jour `due_on` / `lettering` / `bank_pointage` sur lignes postées (volontaire mais élargit la surface).
4. Pas de job de réconciliation périodique `SUM(lignes)` vs snapshots.

## 7. Tests automatisés recommandés (à ajouter — non encore présents)

Voir `P0_REMEDIATION_PLAN.md` :

- Concurrence multi-thread / multi-process sur `post_entry` même compte.
- Assertion post-post : snapshot == agrégat des lignes.
- Tentative d’écriture déséquilibrée via ORM direct (après CHECK SQL).
- Idempotency : second appel avec payload différent → 409.
