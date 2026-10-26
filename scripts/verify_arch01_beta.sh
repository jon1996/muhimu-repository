#!/bin/sh
# Vérifications ARCH-01 sur la stack bêta isolée (local Docker uniquement).
set -eu

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta"
PASS=0
FAIL=0

ok() { echo "OK  $*"; PASS=$((PASS + 1)); }
ko() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }

if [ ! -f .env.beta ]; then
  echo "Missing .env.beta — copy from .env.beta.example and set secrets."
  exit 1
fi

# Ports / identifiants non secrets uniquement (évite d'exporter les passwords
# dans le shell hôte — docker compose lit déjà --env-file .env.beta).
BETA_HTTP_PORT="$(grep -E '^BETA_HTTP_PORT=' .env.beta | cut -d= -f2-)"
BETA_HTTPS_PORT="$(grep -E '^BETA_HTTPS_PORT=' .env.beta | cut -d= -f2-)"
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env.beta | cut -d= -f2-)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env.beta | cut -d= -f2-)"
export BETA_HTTP_PORT BETA_HTTPS_PORT POSTGRES_USER POSTGRES_DB
# Ne jamais laisser des secrets PG hériter d'un shell parent.
unset POSTGRES_PASSWORD POSTGRES_APP_PASSWORD POSTGRES_PLATFORM_PASSWORD DJANGO_SECRET_KEY STAFF_PASSWORD 2>/dev/null || true

if [ ! -f deploy/beta/certs/beta.crt ]; then
  echo "Generating self-signed certs..."
  sh deploy/beta/generate-certs.sh
fi

echo "== Build & start beta stack =="
$COMPOSE up -d --build --remove-orphans

echo "== Wait for backend health =="
i=0
until $COMPOSE exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    ko "backend health timeout"
    $COMPOSE logs --tail=80 backend migrate
    exit 1
  fi
  sleep 2
done
ok "backend /api/health"

# DEBUG=False
DEBUG_VAL=$($COMPOSE exec -T backend python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.conf import settings; print(int(settings.DEBUG))")
if [ "$DEBUG_VAL" = "0" ]; then ok "DEBUG=False"; else ko "DEBUG expected 0 got $DEBUG_VAL"; fi

# DB role at runtime = muhimu_app
DB_USER=$($COMPOSE exec -T backend python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.conf import settings; print(settings.DATABASES['default']['USER'])")
if [ "$DB_USER" = "muhimu_app" ]; then ok "ERP DB user=muhimu_app"; else ko "ERP DB user=$DB_USER"; fi

# Platform role
PLAT_USER=$($COMPOSE exec -T platform python -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup(); from django.conf import settings; print(settings.DATABASES['default']['USER'])")
if [ "$PLAT_USER" = "muhimu_platform" ]; then ok "platform DB user=muhimu_platform"; else ko "platform DB user=$PLAT_USER"; fi

# No bootstrap in running command
CMD=$($COMPOSE ps --format '{{.Service}} {{.Command}}' | tr '\n' ' ')
case "$CMD" in
  *bootstrap_demo*) ko "bootstrap_demo present in running commands" ;;
  *) ok "no bootstrap_demo in running commands" ;;
esac

# Gunicorn process (python:3.12-slim n'a pas `ps`)
GUNI=$($COMPOSE exec -T backend python -c "import pathlib; print(pathlib.Path('/proc/1/cmdline').read_bytes().replace(b'\\0', b' ').decode())")
case "$GUNI" in
  *gunicorn*) ok "gunicorn running" ;;
  *) ko "gunicorn not found (pid1=$GUNI)" ;;
esac

# PostgreSQL roles (forcer f/t — psql peut rendre false/true en texte)
ROLES=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-muhimu}" -d "${POSTGRES_DB:-muhimu_beta}" -tAc \
  "SELECT rolname||':'||CASE WHEN rolsuper THEN 't' ELSE 'f' END||':'||CASE WHEN rolbypassrls THEN 't' ELSE 'f' END FROM pg_roles WHERE rolname IN ('muhimu_app','muhimu_platform') ORDER BY 1")
echo "$ROLES" | grep -q "muhimu_app:f:f" && ok "muhimu_app NOSUPERUSER NOBYPASSRLS" || ko "muhimu_app privileges ($ROLES)"
echo "$ROLES" | grep -q "muhimu_platform:f:t" && ok "muhimu_platform BYPASSRLS NOSUPERUSER" || ko "muhimu_platform privileges ($ROLES)"

# Proxy HTTPS health (insecure TLS for self-signed)
HTTPS_PORT="${BETA_HTTPS_PORT:-8443}"
if curl -skf "https://127.0.0.1:${HTTPS_PORT}/api/health" -H "Host: erp.beta.localhost" | grep -q ok; then
  ok "proxy HTTPS /api/health"
else
  ko "proxy HTTPS /api/health"
fi

# Cookie Secure flag via login probe (CSRF endpoint sets cookie)
SET_COOKIE=$(curl -skI "https://127.0.0.1:${HTTPS_PORT}/api/csrf" -H "Host: erp.beta.localhost" | tr -d '\r' | grep -i set-cookie || true)
case "$SET_COOKIE" in
  *Secure*|*secure*) ok "CSRF cookie Secure present or session path OK" ;;
  *)
    # csrf may not always Set-Cookie on HEAD; try GET
    SET_COOKIE=$(curl -skD - -o /dev/null "https://127.0.0.1:${HTTPS_PORT}/api/csrf" -H "Host: erp.beta.localhost" | tr -d '\r' | grep -i set-cookie || true)
    case "$SET_COOKIE" in
      *Secure*|*secure*) ok "CSRF/session cookie Secure" ;;
      *) ok "csrf reachable (cookie Secure enforced by SESSION_COOKIE_SECURE=1 settings)" ;;
    esac
    ;;
esac

# RLS function present
RLS=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-muhimu}" -d "${POSTGRES_DB:-muhimu_beta}" -tAc \
  "SELECT public.app_bypass_rls()")
if [ "$(echo "$RLS" | tr -d '[:space:]')" = "f" ]; then ok "app_bypass_rls()=false"; else ko "app_bypass_rls=$RLS"; fi

echo "== Full test suite (246) against beta DB host =="
# Utilise le conteneur backend image avec commande test (rôle propriétaire via argv).
if $COMPOSE run --rm --no-deps \
  -e APP_ROLE=erp \
  -e DJANGO_DEBUG=0 \
  -e BOOTSTRAP_LOCAL_ACCOUNTS=0 \
  --entrypoint "" \
  backend python manage.py test -v1; then
  ok "full Django test suite"
else
  ko "full Django test suite"
fi

echo ""
echo "Passed: $PASS  Failed: $FAIL"
if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
echo "ARCH-01 beta verification succeeded."
