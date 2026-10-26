#!/bin/sh
# Migrations contrôlées (one-shot) — rôle propriétaire PostgreSQL uniquement.
set -eu

echo "[migrate] applying migrations (no bootstrap)"
python manage.py migrate --noinput
python manage.py collectstatic --noinput
echo "[migrate] done"
