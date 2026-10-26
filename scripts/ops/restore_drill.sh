#!/bin/sh
# Drill de restauration ISOLÉE — projet muhimu-ops-restore uniquement.
# Ne touche jamais muhimuerp / muhimu-beta / volumes de production.
#
# Prérequis (env, jamais en argv) :
#   OPS_RESTORE_APP_PASSWORD, OPS_RESTORE_PLATFORM_PASSWORD
#   OPS_RESTORE_PG_PASSWORD (optionnel si volume déjà initialisé)
#   DUMP=... ROLES=... (optionnel : dernier dump DEV)
#
# Usage: ./scripts/ops/restore_drill.sh
set -eu
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'
. "$(dirname "$0")/lib_common.sh"
ROOT="$(ops_root)"
cd "$ROOT"

PROJECT="muhimu-ops-restore"
ops_assert_safe_project "$PROJECT"
ops_require_cmd docker

[ -n "${OPS_RESTORE_APP_PASSWORD:-}" ] || ops_fail "OPS_RESTORE_APP_PASSWORD requis"
[ -n "${OPS_RESTORE_PLATFORM_PASSWORD:-}" ] || ops_fail "OPS_RESTORE_PLATFORM_PASSWORD requis"
export OPS_RESTORE_PG_PASSWORD="${OPS_RESTORE_PG_PASSWORD:-ops_restore_temp_lab_only}"

DUMP="${DUMP:-}"
ROLES="${ROLES:-}"
if [ -z "$DUMP" ]; then
  DUMP=$(ls -1t "$ROOT"/backups/postgres/muhimu_dev_*.dump 2>/dev/null | head -n1 || true)
fi
if [ -z "$ROLES" ] && [ -n "$DUMP" ]; then
  ROLES="${DUMP%.dump}_roles.sql"
fi
[ -n "$DUMP" ] && [ -f "$DUMP" ] || ops_fail "DUMP introuvable"
[ -n "$ROLES" ] && [ -f "$ROLES" ] || ops_fail "ROLES introuvable: $ROLES"

if [ -f "${DUMP%.dump}.sha256" ]; then
  expect=$(awk -v f="$(basename "$DUMP")" '$2==f {print $1; exit}' "${DUMP%.dump}.sha256")
  actual=$(ops_sha256 "$DUMP")
  [ "$expect" = "$actual" ] || ops_fail "checksum dump mismatch"
  ops_log "checksum OK"
fi

COMPOSE="docker compose -p $PROJECT -f docker-compose.ops-restore.yml"
export OPS_RESTORE_PG_PORT="${OPS_RESTORE_PG_PORT:-5439}"

LOG_DIR="$ROOT/backups/logs"
mkdir -p "$LOG_DIR"
TS="$(ops_ts)"
LOG="$LOG_DIR/restore_drill_${TS}.log"
VALIDATE_OUT="$LOG_DIR/restore_validate_${TS}.out"

run_drill() {
  ops_log "=== RESTORE DRILL start dump=$(basename "$DUMP") ==="
  START=$(date +%s)

  $COMPOSE up -d db
  i=0
  until $COMPOSE exec -T db pg_isready -U muhimu -d postgres >/dev/null 2>&1; do
    i=$((i + 1))
    [ "$i" -lt 40 ] || ops_fail "timeout health restore db"
    sleep 1
  done
  ops_log "db healthy"

  ops_log "recreate database muhimu_restore (volume temp conservé)"
  $COMPOSE exec -T db psql -U muhimu -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'muhimu_restore' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS muhimu_restore;
CREATE DATABASE muhimu_restore OWNER muhimu;
SQL

  ops_log "apply roles DDL"
  $COMPOSE exec -T db psql -U muhimu -d muhimu_restore -v ON_ERROR_STOP=1 < "$ROLES"

  ops_log "set role passwords from env"
  if command -v py >/dev/null 2>&1; then
    PY="py -3"
  elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
  elif command -v python >/dev/null 2>&1; then
    PY="python"
  else
    ops_fail "python requis pour set_restore_role_passwords.py"
  fi
  # Chemin relatif : py.exe Windows ne comprend pas /d/... de Git Bash.
  # shellcheck disable=SC2086
  $PY scripts/ops/set_restore_role_passwords.py \
    | $COMPOSE exec -T db psql -U muhimu -d muhimu_restore -v ON_ERROR_STOP=1

  ops_log "pg_restore"
  $COMPOSE cp "$DUMP" "db:/var/lib/postgresql/restore.dump"
  set +e
  $COMPOSE exec -T db sh -c 'pg_restore -U muhimu -d muhimu_restore --no-owner /var/lib/postgresql/restore.dump'
  RC=$?
  set -e
  $COMPOSE exec -T db sh -c 'rm -f /var/lib/postgresql/restore.dump'
  [ "$RC" -eq 0 ] || [ "$RC" -eq 1 ] || ops_fail "pg_restore failed rc=$RC"

  TABLES=$($COMPOSE exec -T db psql -U muhimu -d muhimu_restore -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" | tr -d ' \r')
  [ "$TABLES" -ge 30 ] || ops_fail "restore incomplet: tables=$TABLES"
  ops_log "tables=$TABLES"

  $COMPOSE exec -T db psql -U muhimu -d muhimu_restore -v ON_ERROR_STOP=1 <<'SQL'
GRANT USAGE ON SCHEMA public TO muhimu_app, muhimu_platform;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO muhimu_app, muhimu_platform;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO muhimu_app, muhimu_platform;
SQL

  ops_log "validation SQL"
  $COMPOSE exec -T db psql -U muhimu -d muhimu_restore -v ON_ERROR_STOP=1 \
    < "$ROOT/scripts/ops/validate_restored.sql" | tee "$VALIDATE_OUT"

  END=$(date +%s)
  DUR=$((END - START))
  ops_log "=== RESTORE DRILL OK duration=${DUR}s ==="
  ops_log "TEMP RESOURCES (await authorization before delete):"
  ops_log "  compose_project=$PROJECT"
  ops_log "  volume=muhimu_ops_restore_pgdata"
  ops_log "  network=muhimu_ops_restore_net"
  ops_log "  host_port=${OPS_RESTORE_PG_PORT}"
  echo "RESTORE_DRILL_OK=1"
  echo "RESTORE_DURATION_SECONDS=$DUR"
  echo "RESTORE_VALIDATE_OUT=$VALIDATE_OUT"
}

set -o pipefail
run_drill 2>&1 | tee -a "$LOG"
