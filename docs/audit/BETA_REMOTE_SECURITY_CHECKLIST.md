# Checklist sécurité — Bêta MUHIMU distante

**Référence :** BETA-REMOTE-ARCH-01  
**Usage :** contrôles **avant** ouverture testeurs (implémentation future)  
**RLS :** politiques PostgreSQL **inchangées** — cette checklist ne modifie pas les migrations RLS.

---

## Légende

| Statut | Signification |
|--------|----------------|
| ☐ | À exécuter sur remote |
| ◐ | Partiellement couvert (local / doc) |
| — | Hors périmètre implémentation actuelle |

---

## 1. Gouvernance et accès

| ID | Contrôle | Bloquant | Statut conception |
|----|----------|----------|-------------------|
| G1 | Charte testeurs signée (données fictives, non certification) | Oui | ◐ doc `docs/beta-testers/*` |
| G2 | Liste nominative testeurs + révocation documentée | Oui | ☐ |
| G3 | **MFA** sur compte **hébergeur** (VPS/cloud console) | Oui | ☐ |
| G4 | **MFA** sur compte **console SaaS** staff (`muhimu_platform`) | Oui | ☐ |
| G5 | SSH : clés uniquement, pas de mot de passe root | Oui | ☐ |
| G6 | Séparation rôles : ops / dev / testeurs | Oui | ◐ |

---

## 2. Réseau et périmètre

| ID | Contrôle | Bloquant | Statut |
|----|----------|----------|--------|
| N1 | PostgreSQL **non** exposé Internet | Oui | ◐ modèle compose local |
| N2 | Redis **non** exposé Internet | Oui | ◐ |
| N3 | Pare-feu : deny by default, 443 (+ VPN UDP si utilisé) | Oui | ☐ |
| N4 | `AUTH_TRUST_PROXY=1` uniquement derrière proxy de confiance | Oui | ◐ `.env.beta.example` |
| N5 | Pas de binding `0.0.0.0` sur services internes | Oui | ☐ audit `docker inspect` |
| N6 | VPN admin (WireGuard/Tailscale) pour SSH/ops | Recommandé | ☐ |

---

## 3. Authentification et sessions

| ID | Contrôle | Bloquant | Référence |
|----|----------|----------|-----------|
| A1 | Rate-limit login Redis (SEC-P0-01) | Oui | ◐ validé local |
| A2 | SEC-SESSION-01 : 12 h absolu, 30 min idle | Oui | ◐ déployé local |
| A3 | Cookies Secure + CSRF Secure | Oui | ◐ |
| A4 | Logout invalidation serveur | Oui | ◐ probes |
| A5 | SessionGuard SG-1 à SG-6 (navigateur) | Oui | ☐ `BETA_LOCAL_CLOSEOUT_REPORT.md` |
| A6 | Pas de credentials bêta locale sur remote | Oui | ☐ politique |

---

## 4. Tenancy et RLS (sans modification policies)

| ID | Contrôle | Bloquant | Méthode |
|----|----------|----------|---------|
| T1 | Runtime ERP = `muhimu_app` NOBYPASSRLS | Oui | SQL `\du` |
| T2 | Isolation cabinet (CompanyAccess) | Oui | `run_beta_uat01_probes` remote |
| T3 | Runner métier avec `tenant_context` (pas BYPASS) | Oui | ◐ closeout local |
| T4 | Aucun contournement RLS en prod remote | Oui | Revue config |
| T5 | Test fuite cross-org (2 orgs demo) | Oui | ☐ scénario dédié read-only |

---

## 5. Intégrité comptable

| ID | Contrôle | Bloquant | Statut |
|----|----------|----------|--------|
| C1 | 4 triggers ACC-03 actifs | Oui | ◐ validé local |
| C2 | Σ débit = Σ crédit posted (par société) | Oui | ☐ post-provision remote |
| C3 | BETA-SCOPE restrict + consolidation 403 | Oui | ◐ probes |
| C4 | PDF disclaimer « DOCUMENT DE TEST » | Oui | ◐ probes |

---

## 6. Données et fichiers

| ID | Contrôle | Bloquant | Statut |
|----|----------|----------|--------|
| D1 | Jeu demo **remote** sans copy DB locale | Oui | ☐ stratégie § doc deployment |
| D2 | Aucune donnée réelle client | Oui | ☐ revue org names / NIF |
| D3 | Media chiffré au repos (volume + backup) | Recommandé | ☐ |
| D4 | URLs documents : auth + tenancy headers | Oui | ◐ API design |
| D5 | Logs sans mots de passe / secrets | Oui | ◐ audit code |

---

## 7. TLS et application

| ID | Contrôle | Bloquent | Statut |
|----|----------|----------|--------|
| H1 | Certificats **publics valides** (pas self-signed testeurs) | Oui | ☐ |
| H2 | HSTS (phase 2 optionnelle) | Non | ☐ |
| H3 | `DJANGO_DEBUG=0` | Oui | ◐ |
| H4 | `BOOTSTRAP_LOCAL_ACCOUNTS=0` | Oui | ◐ |
| H5 | Headers sécurité nginx (X-Frame-Options, etc.) | Recommandé | ☐ revue nginx |

---

## 8. Opérations

| ID | Contrôle | Bloquant | Statut |
|----|----------|----------|--------|
| O1 | Backup auto + alerte échec | Oui | ☐ |
| O2 | Restore drill documenté | Oui | ☐ |
| O3 | Runbook incident (fuite creds, compromission) | Oui | ◐ |
| O4 | Rotation secrets planifiée | Recommandé | ☐ |
| O5 | Images pin par digest / tag immuable | Oui | ☐ |

---

## Synthèse pré-ouverture testeurs

**Bloquants restants (remote) :** tous les ☐ ci-dessus marqués **Oui** dans les sections 1–8.

**Couverture actuelle :** validations **bêta locale** (closeout, SEC-SESSION-01, UAT probes) — **ne remplace pas** les contrôles sur l’hôte distant.
