# Revue performance et stabilité

## 1. Constats (revue code, pas de charge exécutée)

| Sujet | État | Commentaire |
|---|---|---|
| Snapshots de balance | Conception saine | Évite `SUM` historique à chaque écran |
| Concurrence snapshots | **Risque** | Pas de `select_for_update` / `F()` |
| Celery / files | Absent | PDF / états / imports synchrones |
| `CONN_MAX_AGE` | 0 | Correct pour RLS ; coût connexions |
| Pagination écritures | À vérifier côté API/UI | Dashboard slice client-side (6 lignes) |
| Index | Uniques métier présents | Pas d’audit EXPLAIN réalisé |
| N+1 | Possible sur listes | Prefetch partiel dans API |

## 2. Scénarios de test recommandés (non exécutés)

Environnement **isolé uniquement** :

| Scénario | Objectif | Critère |
|---|---|---|
| 1 000 écritures postées | Latence post + balance | p95 post < 300 ms ; balance < 1 s |
| 10 000 écritures | Génération PDF livres | < 30 s ou async |
| 100 000 écritures | Snapshots + grand-livre compte | Pas de timeout ; mémoire stable |
| 10 users simultanés même société | Courses snapshots | Soldes = vérité lignes |
| 20 organisations | RLS + perf | Pas de fuite ; latence stable |

## 3. Risques de blocage

- `select_for_update` sur séquence journal : bon, mais snapshots non verrouillés.
- Clôture exercice longue transaction possible sur gros volumes.
- PDF ReportLab en requête HTTP : timeout reverse-proxy.

## 4. Recommandations

1. Corriger ACC-01 (P0) avant tout bench concurrent.
2. Brancher Celery pour PDF/exports.
3. Ajouter pagination serveur stricte sur `/ledger/entries`.
4. Job nocturne de réconciliation snapshots.
5. Exécuter les scénarios ci-dessus après P0, documenter résultats dans ce fichier.
