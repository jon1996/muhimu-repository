#!/bin/sh
# Tests unitaires rapides OPS-01 (garde-fous, pas de Docker destructif).
set -eu
. "$(dirname "$0")/lib_common.sh"
ROOT="$(ops_root)"
PASS=0
FAIL=0
ok() { echo "OK  $*"; PASS=$((PASS + 1)); }
ko() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }

# 1) projets protégés refusés
if (ops_assert_safe_project muhimuerp) >/dev/null 2>&1; then ko "muhimuerp should fail"; else ok "refuse muhimuerp"; fi
if (ops_assert_safe_project muhimu-beta) >/dev/null 2>&1; then ko "muhimu-beta should fail"; else ok "refuse muhimu-beta"; fi
if (ops_assert_safe_project muhimu-ops-restore) >/dev/null 2>&1; then ok "allow ops-restore"; else ko "ops-restore should allow"; fi

# 2) dollar-quote passwords SQL
if command -v py >/dev/null 2>&1; then PY="py -3"; elif command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
export OPS_RESTORE_APP_PASSWORD='s3cret$App'
export OPS_RESTORE_PLATFORM_PASSWORD='s3cret$Plat'
# shellcheck disable=SC2086
SQL=$($PY "$ROOT/scripts/ops/set_restore_role_passwords.py")
echo "$SQL" | grep -q "ALTER ROLE muhimu_app PASSWORD" && ok "sql app role" || ko "sql app role"
echo "$SQL" | grep -q '\$pw\$' && ok "dollar quote" || ko "dollar quote"
printf '%s' "$SQL" | grep -Fq 's3cret$App' && ok "password embedded safely" || ko "password missing from quote"

# 3) compose ops-restore présent
[ -f "$ROOT/docker-compose.ops-restore.yml" ] && ok "compose ops-restore" || ko "compose missing"
grep -q 'muhimu_ops_restore_pgdata' "$ROOT/docker-compose.ops-restore.yml" && ok "named temp volume" || ko "volume name"

echo "Passed: $PASS Failed: $FAIL"
[ "$FAIL" -eq 0 ]
