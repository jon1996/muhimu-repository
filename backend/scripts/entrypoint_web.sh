#!/bin/sh
# Démarrage runtime ERP / platform — PAS de migrate, PAS de bootstrap_demo.
set -eu

echo "[entrypoint] APP_ROLE=${APP_ROLE:-erp} starting gunicorn"
exec gunicorn config.wsgi:application --config gunicorn.conf.py
