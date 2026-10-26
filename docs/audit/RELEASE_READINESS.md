# Release readiness — décision Go / No-Go

**Date :** 2026-10-10  
**Produit :** MUHIMU Accounting (Django / Next.js / PostgreSQL)  
**Décision :** **CONDITIONAL GO**

---

## Tableau de synthèse

| Domaine | État | Risque | Preuves | Action nécessaire |
|---|---|---|---|---|
| Architecture | Partiel | Moyen-Élevé | Code + compose + docs | Hardening runtime prod/pilote |
| SYSCOHADA | Partiel | Élevé | sn_map + tests ; pas d’avis EC | Validation expert + PV |
| Calculs comptables | Partiel | Critique | Decimal OK ; course snapshots | ACC-01 |
| Multi-entreprises | Partiel | Élevé | RLS org ; pas tests croisés | SAAS-03 |
| Sécurité | Partiel | Élevé | Sessions/CSRF/RLS | Rate-limit + config DEBUG=0 |
| UX | Partiel | Moyen | UI FR riche | Onboarding + guide |
| Imports/Exports | Partiel | Moyen | Plan/AN/PDF | Portabilité + import écritures (P1) |
| Performance | Non prouvé | Moyen | Conception snapshots | Bench après P0 |
| Sauvegardes | Absent | Critique | — | OPS-01 drill restore |
| Lancement bêta | Non prêt | Élevé | DemoGrant ; CGU absentes | Checklist P0 |
| Tests automatisés | Vert | — | **195/195 OK** (Docker) | Maintenir + ajouter P0 tests |

## Interprétation de la décision

### CONDITIONAL GO signifie

Une **bêta fermée** avec professionnels est envisageable **après** résolution documentée des P0 :

1. ACC-01  
2. SAAS-03  
3. OPS-01  
4. ARCH-01  
5. SEC-P0-01  
6. SYSCO-01  

Conditions d’usage de la bêta :

- données **fictives uniquement** ;
- environnement isolé ;
- liste nominative de testeurs ;
- pas de claim « conforme SYSCOHADA » public.

### Ce n’est pas un GO

- pour des livres clients réels ;
- pour une ouverture large ;
- pour une commercialisation payante.

### Ce serait un NO-GO si

- un P0 reste ouvert ;
- les tests automatisés redeviennent rouges ;
- le drill restore échoue ;
- une fuite inter-tenant est démontrée.

## Preuves disponibles vs manquantes

| Disponible | Manquant |
|---|---|
| Suite tests 195 OK | Tests concurrence snapshots |
| Mapping SN unitaire | Validation EC écrite |
| RLS dans migrations | Tests isolation croisée |
| Design multi-tenant | Runbook backup/restore |
| UI parcours comptable | Guide + CGU + support |

## Signature décision (à remplir)

| Rôle | Nom | Date | Avis |
|---|---|---|---|
| Technique | | | |
| Produit | | | |
| Expert-comptable | | | |
| Sécurité / ops | | | |
