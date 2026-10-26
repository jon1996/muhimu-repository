from django.db import migrations

TABLES = [
    "ledger_bankstatement",
    "ledger_bankstatementline",
]


def _enable(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_isolation ON {table};
CREATE POLICY {table}_isolation ON {table}
  USING (app_bypass_rls() OR organization_id = app_current_org())
  WITH CHECK (app_bypass_rls() OR organization_id = app_current_org());
"""


def _disable(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


SQL = "\n".join(_enable(t) for t in TABLES)
REVERSE = "\n".join(_disable(t) for t in reversed(TABLES))


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0012_bank_reconciliation"),
    ]

    operations = [
        migrations.RunSQL(SQL, REVERSE),
    ]
