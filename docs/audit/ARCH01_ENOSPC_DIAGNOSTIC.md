# ARCH-01 — Diagnostic ENOSPC / Docker (Phases 1–2)

**Date :** 2026-10-10  
**Action :** diagnostic uniquement — **aucune suppression effectuée**

---

## Phase 1 — Résultats

### 1. Espace Windows

| Disque | Taille | Libre | % libre |
|---|---|---|---|
| **C:** | 549 Go | **~64–72 Go** | ~12 % |
| **D:** (projet) | 403 Go | **~264 Go** | ~65 % |

C: n’est plus à 0 octet libre au moment du diagnostic ; l’ENOSPC observé pendant ARCH-01 était très probablement **dans le stockage virtuel Docker / BuildKit**, pas une saturation totale de C: actuelle.

### 2. Disque virtuel Docker / WSL2

| Élément | État |
|---|---|
| Distro WSL | `docker-desktop` **Running** (seule distro listée) |
| `docker_data.vhdx` | `C:\Users\…\AppData\Local\Docker\wsl\disk\docker_data.vhdx` ≈ **22,9 Go** |
| `ext4.vhdx` (main) | ≈ **0,09 Go** |
| Dossier `AppData\Local\Docker` | ≈ **23,0 Go** |
| Montage données dans WSL | `/var/lib/docker` **absent** ; disque data **non monté** dans la distro courante |
| Root WSL `docker-desktop` | `/dev/sdd` ≈ **127 Mo** (54 % utilisé |

### 3–6. Images / caches / conteneurs / volumes Docker

| Contrôle | Résultat |
|---|---|
| `docker info` / `docker version` | **TIMEOUT** — daemon **non répondant** |
| Inventaire images / build cache / conteneurs / volumes | **Impossible** tant que le daemon est HS |
| Snapshot antérieur (avant panne) | Build cache ≈ 6,7 Go ; images reclaimable ≈ 1,7 Go (session ARCH-01) |

### 7. Logs

| Source | Taille |
|---|---|
| `AppData\Local\Docker\log` | ≈ **29 Mo** (48 fichiers) — faible |

### 8. WSL

- `docker-desktop` Running v2  
- Pas de distro `docker-desktop-data` séparée listée (modèle Docker Desktop récent = VHDX `disk\docker_data.vhdx`)

### 9. Intégrité apparente stockage Docker

- Processus Docker Desktop / `com.docker.backend` présents  
- Daemon API **ne répond pas** (500 / timeout)  
- Stockage data VHDX présent sur disque Windows mais **non exposé** correctement dans WSL (`/var/lib/docker` manquant)  
- Symptômes cohérents avec panne après saturation BuildKit (session précédente : `read-only file system` sur `metadata_v2.db`)

### 10. PostgreSQL / chemins projet

| Chemin | Taille |
|---|---|
| `frontend\.next` | ≈ 0,54 Go |
| `console\.next` | ≈ 0,20 Go |
| `frontend\node_modules` | ≈ 0,48 Go |
| `backend\.venv` | ≈ 0,07 Go |
| Sauvegardes `.dump` / `.sql` projet | **Aucune trouvée** (recherche non destructive) |

### Estimation espace récupérable (après restauration daemon)

| Cible (après autorisation) | Estimation | Risque données |
|---|---|---|
| `docker builder prune` (cache build) | **1–7 Go** | Aucun (rebuild) |
| Images dangling / non utilisées | **~1–2 Go** | Faible si non taguées utiles |
| Conteneurs stopped | Faible | Faible |
| `frontend/.next` + `console/.next` | **~0,7 Go** | Aucun (rebuild) |
| Temp Windows | **~0,8 Go** | Faible |
| **Volumes PostgreSQL** | — | **Ne pas toucher** |

---

## Phase 2 — Protection des données (inventaire)

### Volumes Docker à protéger (noms attendus)

| Volume (compose) | Projet | Contenu | Action |
|---|---|---|---|
| `postgres_data` | `muhimuerp` (dev) | **PostgreSQL dev** | **PROTEGER** |
| `frontend_node_modules` | muhimuerp | cache npm frontend | rebuildable |
| `console_node_modules` | muhimuerp | cache npm console | rebuildable |
| `postgres_beta_data` | `muhimu-beta` | PostgreSQL bêta (si créé) | **PROTEGER** |
| `beta_media` / `beta_static` | muhimu-beta | media/static bêta | protéger si présents |

### Données indispensables

1. Volume **`postgres_data`** (données comptables / démo / travail)  
2. Code projet sur **D:** (`d:\muhimu\muhimu ERP`) — hors Docker  
3. Fichier `docker_data.vhdx` (contient les volumes) — **ne jamais supprimer manuellement**

### Sauvegardes

- Aucune sauvegarde SQL autonome détectée dans le dépôt.  
- OPS-01 (backup) non encore fait → **prudence maximale** sur les volumes PG.

### Interdits respectés

- Pas de reset Docker Desktop  
- Pas de suppression manuelle du VHDX  
- Pas de purge volumes  
- Pas de nettoyage exécuté

---

## Cause probable ENOSPC

Saturation / corruption temporaire du **stockage Docker BuildKit** à l’intérieur de `docker_data.vhdx` pendant les builds multi-stage ARCH-01 (frontend + console + API), conduisant à :

1. `read-only file system` sur BuildKit  
2. API Docker 500 / daemon gelé  
3. `ENOSPC` côté outils hôtes lors d’écritures concurrentes  

Le disque **C:** a encore ~64+ Go libres ; le goulot est le **moteur Docker / VHD**, pas D: (projet).

---

## Suite proposée (Phase 3 — autorisation requise)

Nettoyage **progressif**, dans cet ordre, **après votre OK explicite** pour chaque palier :

1. **Paliers Windows sans Docker** : caches Next `.next` (rebuildable) — ~0,7 Go  
2. **Redémarrage contrôlé Docker Desktop** (sans reset / sans delete VHDX)  
3. Si daemon OK : inventaire `docker system df` + `docker volume ls` (vérifier `postgres_data`)  
4. Puis seulement : `docker builder prune` (cache) — **pas** `docker system prune -a --volumes`

**En attente de votre autorisation avant toute suppression ou redémarrage Docker.**

---

## Mise à jour — récupération partielle autorisée (2026-10-10)

### Actions effectuées
1. Suppression `frontend/.next` (550 Mo) + `console/.next` (202 Mo) — confirmée.
2. Redémarrage normal Docker Desktop — **daemon OK** (Server 29.6.1) en ~5 s.
3. Inventaire sans prune / sans suppression volumes.

### État post-récupération
| Élément | État |
|---|---|
| Daemon | **OK** |
| Stockage Docker | `/mnt/docker-desktop-disk` monté (~16.7 Go / 1007 Go, 2 %) |
| Volume `muhimuerp_postgres_data` | **Présent**, lisible, `PG_VERSION=16`, ~113 Mo |
| Volume `postgres_beta_data` | **Absent** (stack bêta jamais montée) |
| Conteneurs `muhimuerp-*` | Exited (255) après restart — attendu |
| Prune | **Non exécuté** |

### Espace disque
- C: ~92.7 Go libres  
- D: ~264.5 Go libres  
