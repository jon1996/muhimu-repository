#!/bin/sh
# Génère des certificats TLS self-signed pour la stack bêta locale.
# NE PAS utiliser en production publique.
set -eu
DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)/certs"
mkdir -p "$DIR"
if [ -f "$DIR/beta.crt" ] && [ -f "$DIR/beta.key" ]; then
  echo "Certificats déjà présents dans $DIR"
  exit 0
fi
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$DIR/beta.key" \
  -out "$DIR/beta.crt" \
  -subj "/CN=erp.beta.localhost/O=Muhimu Beta/C=CI" \
  -addext "subjectAltName=DNS:erp.beta.localhost,DNS:console.beta.localhost,DNS:localhost,IP:127.0.0.1"
chmod 600 "$DIR/beta.key"
echo "Certificats self-signed créés dans $DIR"
