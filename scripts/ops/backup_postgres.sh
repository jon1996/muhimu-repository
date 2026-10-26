#!/bin/sh
# Sauvegarde PostgreSQL MUHIMU (format custom) + rôles (sans mots de passe).
# Usage:
#   ENV=dev|beta ./scripts/ops/backup_postgres.sh
# Secrets via env / fichier --env-file Docker uniquement (jamais en arguments).
set -eu
. "$(dirname "$0")/lib_common.sh"
ROOT="$(ops_root)"
cd "$ROOT"

ENV_NAME="${ENV:-dev}"
TS="$(ops_ts)"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups/postgres}"
mkdir -p "$OUT_DIR"
LOG_DIR="$ROOT/backups/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/backup_${ENV_NAME}_${TS}.log"

case "$ENV_NAME" in
  dev)
    PROJECT="muhimuerp"
    SERVICE="db"
    DB_NAME="${POSTGRES_DB:-muhimu}"
    DB_USER="${POSTGRES_USER:-muhimu}"
    COMPOSE="docker compose -p $PROJECT"
    ;;
  beta)
    PROJECT="muhimu-beta"
    SERVICE="db"
    DB_NAME="${POSTGRES_DB:-muhimu_beta}"
    DB_USER="${POSTGRES_USER:-muhimu}"
    COMPOSE="docker compose -p $PROJECT -f docker-compose.beta.yml --env-file .env.beta"
    ;;
  *)
    ops_fail "ENV doit être dev ou beta (reçu: $ENV_NAME)"
    ;;
esac

DUMP="$OUT_DIR/muhimu_${ENV_NAME}_${TS}.dump"
ROLES="$OUT_DIR/muhimu_${ENV_NAME}_${TS}_roles.sql"
META="$OUT_DIR/muhimu_${ENV_NAME}_${TS}.meta.json"
SUMS="$OUT_DIR/muhimu_${ENV_NAME}_${TS}.sha256"

{
  ops_log "start backup ENV=$ENV_NAME DB=$DB_NAME project=$PROJECT"
  START=$(date +%s)

  $COMPOSE exec -T "$SERVICE" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null \
    || ops_fail "PostgreSQL $ENV_NAME indisponible"

  # Dump custom (schéma + données + ACL ; pas les mots de passe de rôles cluster).
  # --no-owner : portable ; ACL conservées (grants muhimu_app / platform).
  $COMPOSE exec -T "$SERVICE" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner \
    > "$DUMP.tmp" || ops_fail "pg_dump échoué"
  mv "$DUMP.tmp" "$DUMP"

  # Rôles applicatifs : DDL sans PASSWORD (les secrets restent hors archive).
  cat > "$ROLES" <<'EOF'
-- OPS-01 roles (no passwords). Apply before pg_restore. Passwords set separately from env.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'muhimu_app') THEN
    CREATE ROLE muhimu_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
  ELSE
    ALTER ROLE muhimu_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'muhimu_platform') THEN
    CREATE ROLE muhimu_platform LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;
  ELSE
    ALTER ROLE muhimu_platform WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS;
  END IF;
END
$$;
EOF

  # Snapshot compteurs (lecture seule) pour validation post-restore.
  COUNTS=$($COMPOSE exec -T "$SERVICE" psql -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT json_build_object(
       'orgs', (SELECT count(*) FROM tenancy_organization),
       'companies', (SELECT count(*) FROM tenancy_company),
       'journals', (SELECT count(*) FROM ledger_journal),
       'entries', (SELECT count(*) FROM ledger_entry),
       'lines', (SELECT count(*) FROM ledger_entryline),
       'snapshots', (SELECT count(*) FROM ledger_balancesnapshot),
       'users', (SELECT count(*) FROM identity_user),
       'debit', (SELECT coalesce(sum(debit),0) FROM ledger_entryline),
       'credit', (SELECT coalesce(sum(credit),0) FROM ledger_entryline)
     );" | tr -d '\r' | tr -d ' ')

  SIZE=$(wc -c < "$DUMP" | tr -d ' ')
  HASH=$(ops_sha256 "$DUMP")
  HASH_ROLES=$(ops_sha256 "$ROLES")
  END=$(date +%s)
  DUR=$((END - START))

  printf '%s  %s\n%s  %s\n' "$HASH" "$(basename "$DUMP")" "$HASH_ROLES" "$(basename "$ROLES")" > "$SUMS"

  cat > "$META" <<EOF
{
  "env": "$ENV_NAME",
  "project": "$PROJECT",
  "database": "$DB_NAME",
  "timestamp": "$TS",
  "dump_file": "$(basename "$DUMP")",
  "roles_file": "$(basename "$ROLES")",
  "bytes": $SIZE,
  "sha256_dump": "$HASH",
  "sha256_roles": "$HASH_ROLES",
  "duration_seconds": $DUR,
  "counts": $COUNTS,
  "pg_dump_format": "custom",
  "passwords_included": false
}
EOF

  if [ "${BACKUP_ENCRYPT:-0}" = "1" ]; then
    ops_encrypt_file "$DUMP" "$DUMP.enc"
    ENC_HASH=$(ops_sha256 "$DUMP.enc")
    printf '%s  %s\n' "$ENC_HASH" "$(basename "$DUMP.enc")" >> "$SUMS"
    # Retirer le dump en clair si demandé
    if [ "${BACKUP_REMOVE_PLAINTEXT:-1}" = "1" ]; then
      rm -f "$DUMP"
      ops_log "plaintext dump removed; encrypted at $DUMP.enc"
    fi
  fi

  # Rétention : garder les N derniers dumps (+ meta/roles/sha) pour cet env
  RETAIN="${BACKUP_RETAIN:-7}"
  ls -1t "$OUT_DIR"/muhimu_${ENV_NAME}_*.meta.json 2>/dev/null | tail -n +$((RETAIN + 1)) | while read -r meta; do
    base="${meta%.meta.json}"
    ops_log "retention: pruning $base*"
    rm -f "$base".dump "$base".dump.enc "$base"_roles.sql "$base".sha256 "$base".meta.json
  done

  ops_log "OK dump=$DUMP bytes=$SIZE sha256=$HASH duration=${DUR}s"
  echo "BACKUP_OK=$DUMP"
} 2>&1 | tee -a "$LOG"
