#!/bin/sh
# Orchestration sauvegarde Postgres + médias (+ chiffrement optionnel).
#   ENV=dev BACKUP_ENCRYPT=0 ./scripts/ops/backup_all.sh
set -eu
. "$(dirname "$0")/lib_common.sh"
ROOT="$(ops_root)"
cd "$ROOT"
ENV_NAME="${ENV:-dev}"
ops_log "backup_all start ENV=$ENV_NAME encrypt=${BACKUP_ENCRYPT:-0}"
sh "$ROOT/scripts/ops/backup_postgres.sh"
sh "$ROOT/scripts/ops/backup_media.sh"
ops_log "backup_all done ENV=$ENV_NAME"
