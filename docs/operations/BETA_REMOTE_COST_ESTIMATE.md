# Estimation de coûts — Bêta MUHIMU distante

**Référence :** BETA-REMOTE-ARCH-01  
**Date :** 2026-10-15  
**Devise :** EUR (ordre de grandeur)

---

## Légende

| Tag | Signification |
|-----|----------------|
| **[EST]** | Estimation ingénierie — **non vérifiée** sur site hébergeur au moment de la rédaction |
| **[VER]** | Prix public affiché sur site fournisseur (à re-vérifier avant achat) |

*Aucun devis n’a été commandé ; aucun achat effectué (mandat ARCH-01).*

---

## Hypothèses charge

| Paramètre | Valeur |
|-----------|--------|
| Utilisateurs testeurs | 5–15 |
| Concurrence | Faible (compta, pas batch massif) |
| Stockage DB + media | < 20 Go an 1 |
| Trafic sortant | < 100 Go/mois |

---

## Option A — VPS dédié + Docker Compose

**Description :** 1 VPS (Hetzner / OVH / DigitalOcean), stack identique à bêta locale, ops manuelles.

### Dimensionnement suggéré

| Ressource | Spec **[EST]** |
|-----------|----------------|
| vCPU | 4 |
| RAM | 8–16 Go |
| SSD | 80–160 Go |
| Bande passante | 20 T inclus typique EU |

### Coûts mensuels

| Poste | EUR/mois | Tag |
|-------|----------|-----|
| VPS (ex. équivalent CPX31 / D4) | 25–45 | **[EST]** — bande marché EU 2025–2026 |
| IPv4 dédiée (si facturée) | 0–4 | **[EST]** |
| Snapshots VPS | 5–10 | **[EST]** |
| Stockage backup off-site (S3 50 Go) | 1–3 | **[EST]** |
| Domaine + DNS (si nouveau) | ~1 (amorti /12) | **[EST]** |
| Let’s Encrypt | 0 | **[VER]** |
| Tailscale (≤ 3 users free) / WireGuard | 0 | **[VER]** free tier |
| **Sous-total infra** | **~35–60** | **[EST]** |

### Coûts ops (hors infra)

| Poste | EUR/mois | Tag |
|-------|----------|-----|
| Maintenance ops (patch, backup, deploy) | 2–8 h × taux interne | **[EST]** |
| Monitoring SaaS léger (option) | 0–15 | **[EST]** |

### Avantages / inconvénients

| + | − |
|---|---|
| Coût prévisible, aligné compose existant | Single point of failure |
| Contrôle total | Ops à votre charge |
| Facile rollback image | Scaling vertical manuel |

---

## Option B — Cloud managé (services décomposés)

**Description :** Compute container (ou VM) + **PostgreSQL managé** + **Redis managé** + LB TLS.

### Dimensionnement suggéré **[EST]**

| Service | Spec |
|---------|------|
| PostgreSQL managé | 2 vCPU, 4–8 Go RAM, 20 Go |
| Redis managé | 1 Go |
| Compute (2 containers API + 2 web) | 2 × 1 vCPU, 2 Go |
| Load balancer + TLS | 1 |

### Coûts mensuels (fourchette large selon cloud)

| Poste | EUR/mois | Tag |
|-------|----------|-----|
| PostgreSQL managé | 40–120 | **[EST]** (AWS RDS / DO DB / Scaleway RDB) |
| Redis managé | 15–40 | **[EST]** |
| Compute containers | 30–80 | **[EST]** |
| LB / ingress TLS | 10–25 | **[EST]** |
| Egress réseau | 5–20 | **[EST]** |
| Backups managés DB | 5–15 | **[EST]** |
| **Sous-total infra** | **~105–300** | **[EST]** |

### Avantages / inconvénients

| + | − |
|---|---|
| Backups / patch DB délégués | Coût ×2–5 vs VPS |
| Meilleure résilience DB | Complexité réseau privé (VPC) |
| Scaling path clair | Compose à adapter (endpoints managés) |

---

## Comparaison synthétique

| Critère | Option A VPS | Option B Managé |
|---------|--------------|-----------------|
| Coût mensuel infra **[EST]** | 35–60 € | 105–300 € |
| Time-to-first deploy | **Rapide** (compose existant) | Moyen (VPC, secrets, endpoints) |
| Compétence ops | Linux + Docker | Cloud + réseau |
| Adapté 5–15 experts-comptables | **Oui** | Oui (surdimensionné début) |
| Séparation prod future | Bonne (autre VPS) | **Très bonne** (autre compte cloud) |

---

## Coûts sécurité / réseau (communs)

| Poste | EUR/mois | Tag |
|-------|----------|-----|
| MFA (TOTP apps) | 0 | **[VER]** |
| Coffre secrets (team) | 0–8 | **[EST]** |
| WAF basique (option cloudflare free) | 0 | **[VER]** free |
| Audit externe (option) | ponctuel | hors abonnement |

---

## Recommandation coût / architecture

Pour un **petit panel d’experts-comptables distants** en phase beta :

1. **Démarrer option A** (VPS 8–16 Go, Compose, backups off-site) — **~40–55 €/mois [EST]** infra.  
2. Prévoir migration **option B** uniquement si : > 25 utilisateurs, SLA 99,9 %, ou exigence **DB managée** contractuelle.

---

## Décisions budget nécessitant votre accord

| ID | Question |
|----|----------|
| B1 | Plafond mensuel infra (ex. 60 € vs 150 €) |
| B2 | Acceptation single VPS vs surcoût HA |
| B3 | Budget temps ops interne (h/mois) |
| B4 | Hébergeur EU obligatoire (RGPD / localisation) |

---

## Prochaine vérification **[VER]** (sur GO implémentation)

1. Consulter pages tarifaires hébergeur retenu (date + capture ops).  
2. Chiffrer egress réel après 1 mois pilote.  
3. Mettre à jour ce document avec colonne **prix vérifiés**.
