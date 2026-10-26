#!/bin/sh
# Helpers OPS-01 — aucun secret en dur.
set -eu

ops_root() {
  CDPATH= cd -- "$(dirname "$0")/../.." && pwd
}

ops_ts() {
  date +%Y%m%d_%H%M%S
}

ops_require_cmd() {
  for c in "$@"; do
    command -v "$c" >/dev/null 2>&1 || {
      echo "ERROR: commande requise absente: $c" >&2
      exit 1
    }
  done
}

ops_log() {
  echo "[ops $(date -Iseconds 2>/dev/null || date)] $*"
}

ops_fail() {
  echo "ERROR: $*" >&2
  exit 1
}

# Refuse d'agir sur les projets Compose protégés.
ops_assert_safe_project() {
  case "$1" in
    muhimuerp|muhimu-beta|muhimu-frappe)
      ops_fail "projet Compose protégé interdit: $1"
      ;;
  esac
}

ops_sha256() {
  f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$f" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$f" | awk '{print $1}'
  else
    ops_fail "sha256sum/shasum requis"
  fi
}

ops_encrypt_file() {
  # Chiffre in → out via OPENSSL ; passphrase = env BACKUP_ENCRYPTION_PASS
  in="$1"
  out="$2"
  [ -n "${BACKUP_ENCRYPTION_PASS:-}" ] || ops_fail "BACKUP_ENCRYPTION_PASS non défini (chiffrement requis)"
  ops_require_cmd openssl
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
    -in "$in" -out "$out" -pass env:BACKUP_ENCRYPTION_PASS
}

ops_decrypt_file() {
  in="$1"
  out="$2"
  [ -n "${BACKUP_ENCRYPTION_PASS:-}" ] || ops_fail "BACKUP_ENCRYPTION_PASS non défini"
  ops_require_cmd openssl
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in "$in" -out "$out" -pass env:BACKUP_ENCRYPTION_PASS
}
