# Muhimu ERP

SaaS ERP Comptabilité / FinTech (SYSCOHADA). Django + Next.js, PostgreSQL, Redis.

Deux surfaces distinctes (images Docker comprises) :

| Surface | Image API | Image web | Ports |
| --- | --- | --- | --- |
| ERP (produit) | `muhimu-erp-api` | `muhimu-erp-web` | API 8001, UI 3001 |
| Console SaaS | `muhimu-platform-api` | `muhimu-platform-web` | API 8002, UI 3002 |

Même base PostgreSQL, cookies de session séparés. L'admin Django n'est plus sur l'ERP : il est servi par la plateforme (`http://localhost:8002/django/`).

## Démarrage (Docker)

```bash
docker compose up --build
```

- ERP : http://localhost:3001
- Console SaaS : http://localhost:3002
- API ERP : http://localhost:8001/api/docs
- API console : http://localhost:8002/api/docs

Compte ERP démo **(local uniquement)** :

- Email : `demo@muhimu.local`
- Mot de passe : `Demo1234!`

Compte console **(local uniquement)** :

- Email : `ops@muhimu.local`
- Mot de passe : `Ops1234!`

En **production**, les adresses `@muhimu.local` sont désactivées. La console utilise `STAFF_EMAIL` (ex. `jp@muhimu.tech`). Les formulaires de connexion ne préremplissent plus les comptes locaux. L’expéditeur SMTP reste `jp@muhimu.tech`.

Les e-mails (invitations démo, test SMTP) passent par **Namecheap Private Email**.

Dans `.env` :

```
EMAIL_HOST=mail.privateemail.com
EMAIL_PORT=465
EMAIL_USE_SSL=1
EMAIL_HOST_USER=jp@muhimu.tech
EMAIL_HOST_PASSWORD=mot-de-passe-application
DEFAULT_FROM_EMAIL=Muhimu <jp@muhimu.tech>
BOOTSTRAP_LOCAL_ACCOUNTS=0
STAFF_EMAIL=jp@muhimu.tech
STAFF_PASSWORD=...
```

Utilisez le mot de passe d'application (Private Email → Security Center), pas le mot de passe webmail. L'expéditeur doit être la boîte authentifiée, ou un alias du même domaine. Sans USER/PASSWORD, les messages s'écrivent dans les logs `platform`. Test d'envoi : Console → E-mails.

## Démarrage local

PostgreSQL 16 et Redis 7 doivent tourner (ou `docker compose up db redis`). Le port hôte Postgres est **5433**.

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py bootstrap_demo
set APP_ROLE=erp
python manage.py runserver 8001
```

Dans un autre terminal :

```bash
cd backend
set APP_ROLE=platform
python manage.py runserver 8002
```

```bash
cd frontend
npm install
npm run dev
```

```bash
cd console
npm install
npm run dev -- --port 3002
```

## Architecture

Voir [docs/architecture.md](docs/architecture.md). Conception du ledger SYSCOHADA : [docs/ledger.md](docs/ledger.md).
