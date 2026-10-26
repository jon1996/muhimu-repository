"""Set muhimu_app / muhimu_platform passwords on OPS restore cluster via stdin SQL.

Reads OPS_RESTORE_APP_PASSWORD and OPS_RESTORE_PLATFORM_PASSWORD from env.
Emits SQL with dollar-quoting (no echo of secrets beyond the SQL pipe).
"""
from __future__ import annotations

import os
import sys


def dollar_quote(value: str, tag: str = "pw") -> str:
    while tag in value:
        tag += "x"
    return f"${tag}${value}${tag}$"


def main() -> int:
    app = os.environ.get("OPS_RESTORE_APP_PASSWORD") or ""
    plat = os.environ.get("OPS_RESTORE_PLATFORM_PASSWORD") or ""
    if not app or not plat:
        print("missing OPS_RESTORE_APP_PASSWORD / OPS_RESTORE_PLATFORM_PASSWORD", file=sys.stderr)
        return 1
    sql = (
        f"ALTER ROLE muhimu_app PASSWORD {dollar_quote(app)};\n"
        f"ALTER ROLE muhimu_platform PASSWORD {dollar_quote(plat)};\n"
        "GRANT CONNECT ON DATABASE muhimu_restore TO muhimu_app, muhimu_platform;\n"
    )
    sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
