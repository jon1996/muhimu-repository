import os

from django.db import migrations


APP_ROLE = "muhimu_app"


def create_app_role(apps, schema_editor):
    password = os.getenv("POSTGRES_APP_PASSWORD") or os.getenv("POSTGRES_PASSWORD") or "muhimu"
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [APP_ROLE])
        if cursor.fetchone():
            cursor.execute(f"ALTER ROLE {APP_ROLE} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS")
            cursor.execute(f"ALTER ROLE {APP_ROLE} PASSWORD %s", [password])
        else:
            cursor.execute(
                f"CREATE ROLE {APP_ROLE} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS",
                [password],
            )
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
        cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
        cursor.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE}"
        )
        cursor.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}"
        )


def drop_app_role(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP ROLE IF EXISTS {APP_ROLE}")


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0002_rls"),
    ]

    operations = [
        migrations.RunPython(create_app_role, drop_app_role),
    ]
