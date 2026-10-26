#!/bin/sh
# Archive MEDIA_ROOT depuis un conteneur backend (DEV ou bêta).
set -eu
. "$(dirname "$0")/lib_common.sh"
ROOT="$(ops_root)"
cd "$ROOT"

ENV_NAME="${ENV:-dev}"
TS="$(ops_ts)"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups/media}"
mkdir -p "$OUT_DIR" "$ROOT/backups/logs"
LOG="$ROOT/backups/logs/backup_media_${ENV_NAME}_${TS}.log"

case "$ENV_NAME" in
  dev)
    COMPOSE="docker compose -p muhimuerp"
    SERVICE="backend"
    ;;
  beta)
    COMPOSE="docker compose -p muhimu-beta -f docker-compose.beta.yml --env-file .env.beta"
    SERVICE="backend"
    ;;
  *)
    ops_fail "ENV=dev|beta"
    ;;
esac

ARCHIVE="$OUT_DIR/muhimu_${ENV_NAME}_media_${TS}.tar.gz"
SUMS="$OUT_DIR/muhimu_${ENV_NAME}_media_${TS}.sha256"

{
  ops_log "start media backup ENV=$ENV_NAME"
  START=$(date +%s)
  $COMPOSE exec -T "$SERVICE" sh -c 'cd /app && tar czf - media' > "$ARCHIVE.tmp" \
    || ops_fail "tar media échoué"
  mv "$ARCHIVE.tmp" "$ARCHIVE"
  HASH=$(ops_sha256 "$ARCHIVE")
  SIZE=$(wc -c < "$ARCHIVE" | tr -d ' ')
  printf '%s  %s\n' "$HASH" "$(basename "$ARCHIVE")" > "$SUMS"

  if [ "${BACKUP_ENCRYPT:-0}" = "1" ]; then
    ops_encrypt_file "$ARCHIVE" "$ARCHIVE.enc"
    printf '%s  %s\n' "$(ops_sha256 "$ARCHIVE.enc")" "$(basename "$ARCHIVE.enc")" >> "$SUMS"
    if [ "${BACKUP_REMOVE_PLAINTEXT:-1}" = "1" ]; then
      rm -f "$ARCHIVE"
    fi
  fi

  END=$(date +%s)
  ops_log "OK media=$ARCHIVE bytes=$SIZE sha256=$HASH duration=$((END - START))s"
  echo "MEDIA_BACKUP_OK=$ARCHIVE"
} 2>&1 | tee -a "$LOG"
