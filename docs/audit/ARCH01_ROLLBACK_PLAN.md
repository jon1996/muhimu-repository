# ARCH-01 — Plan de rollback

Périmètre : stack Docker **bêta locale** (`muhimu-beta`).  
N’affecte pas la production (aucun déploiement distant dans ARCH-01).

---

## 1. Rollback runtime (immédiat)

Arrêter la stack bêta sans supprimer les données :

```bash
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta down
```

Revenir au développement :

```bash
docker compose -f docker-compose.yml up -d
```

Le volume dev `postgres_data` n’est **pas** partagé avec `postgres_beta_data`.

---

## 2. Rollback données bêta

Supprimer uniquement le volume bêta (irrémédiable pour cette DB lab) :

```bash
docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta down -v
```

`-v` retire `postgres_beta_data`, `beta_media`, `beta_static`.

---

## 3. Rollback code / config

Si les changements ARCH-01 doivent être retirés du dépôt :

| Action | Cible |
|---|---|
| Restaurer | `docker-compose.yml`, Dockerfiles, `settings.py`, `next.config.ts` |
| Supprimer | `docker-compose.beta.yml`, `deploy/beta/`, `backend/gunicorn.conf.py`, `backend/scripts/entrypoint_*.sh`, `scripts/verify_arch01_beta.sh`, docs `ARCH01_*` |
| Conserver | migrations RLS A1′ / ACC-01 (hors ARCH-01) |

Git : revert du commit ARCH-01 si isolé ; sinon revert fichier par fichier.

---

## 4. Points de vigilance

1. **Ne pas** pointer le compose bêta vers `POSTGRES_*` du volume dev.  
2. **Ne pas** réutiliser `.env.beta` comme secrets de production.  
3. Après rollback code, rebuild les images dev (`target: development`) si le cache Docker pointe vers `production`.  
4. Les certificats self-signed peuvent rester sur disque (gitignorés) ; les supprimer avec `deploy/beta/certs/*.crt|*.key` si besoin.

---

## 5. Critères de succès du rollback

- [ ] Stack bêta arrêtée  
- [ ] Stack dev redémarre et `/api/health` OK  
- [ ] Données démo / travail intactes sur volume dev  
- [ ] Aucun conteneur `muhimu-beta-*` restant (sauf volumes si conservés volontairement)
