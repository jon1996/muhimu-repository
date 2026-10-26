# Rapport SaaS multi-entreprises et sécurité

## 1. Modèle multi-tenant

| Niveau | Objet | Isolation |
|---|---|---|
| Client facturé | `Organization` | RLS `organization_id` |
| Dossier comptable | `Company` | Filtres applicatifs + `CompanyAccess` |
| Exercice | `Exercise` | Par société |

**Architecture :** un site / une base PostgreSQL partagée (pas multi-sites Frappe).  
**Rôle runtime :** `muhimu_app` (sans BYPASSRLS) ; migrations / tests / bootstrap en rôle propriétaire.

## 2. Diagnostic SaaS

| Critère | État | Risque |
|---|---|---|
| Plusieurs organisations | Oui | — |
| Isolation données org (RLS) | Oui | Moyen (non prouvé par tests croisés) |
| Isolation sociétés (cabinet) | Applicatif seulement | Élevé si bug filtre |
| Rôles owner/admin/accountant/auditor/viewer | Oui | — |
| Accès cabinet multi-sociétés | `CompanyAccess` | — |
| Permissions API | `require_writer` / `require_company` | — |
| Permissions rapports | Même gated company | — |
| Fichiers | `documents/{company_id}/` + RLS SourceDocument | Moyen |
| Paramètres comptables par société | Oui | — |
| Exercices par société | Oui | — |
| Backup / restore / export sortie | Absents | Critique |
| Abonnements | Non | P2 |

**Verdict :** **pas prêt** pour multi-clients production sans tests d’isolation et runbook ops.

## 3. Vulnérabilités / écarts sécurité (priorisés)

| ID | Gravité | Description | Correction |
|---|---|---|---|
| SEC-P0-01 | HIGH | Pas de rate-limit login | django-axes / middleware / WAF |
| SEC-P0-02 | HIGH | Pas de tests RLS cross-org | Suite tests dédiée |
| SEC-P0-03 | HIGH | Compose bootstrap + DEBUG potentiels | Config prod stricte |
| SEC-01 | HIGH | Pas de MFA | TOTP / WebAuthn (phase 1 optionnelle) |
| SEC-03 | MEDIUM | Headers HSTS / secure absents settings | Activer si HTTPS |
| SEC-04 | MEDIUM | Staff platform bypass RLS | Journaliser toutes lectures sensibles |
| SEC-07 | MEDIUM | Couverture audit trail non inventoriée | Checklist actions |
| SEC-MEDIA | MEDIUM | Servir media via app authZ | Pas d’URL publique brute |

## 4. Authentification / sessions

- Auth email + mot de passe, sessions cookie HttpOnly, CSRF Ninja/Django.
- Cookies séparés ERP / platform.
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` si `DEBUG=0`.
- Validateurs de mot de passe Django standards.

## 5. Ce qui n’a pas été fait

- Pas de test offensif.
- Pas de scan CVE automatisé des dépendances.
- Pas d’audit pentest externe.

## 6. Actions avant bêta externe

1. Tests isolation RLS (P0).
2. Rate-limit + verrouillage compte.
3. Environnement pilote : `DEBUG=0`, secrets forts, HTTPS, `BOOTSTRAP_LOCAL_ACCOUNTS=0`.
4. Procédure révocation accès / DemoGrant.
5. CGU + politique confidentialité (hors code — obligatoire business).
