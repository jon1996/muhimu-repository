import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0016_entryline_due_on"),
        ("tenancy", "0006_rls_officers"),
    ]

    operations = [
        migrations.CreateModel(
            name="EsgReport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("year", models.PositiveSmallIntegerField()),
                ("headcount", models.PositiveIntegerField(default=0)),
                ("hires", models.PositiveIntegerField(default=0)),
                ("dismissals", models.PositiveIntegerField(default=0)),
                ("disabled_count", models.PositiveIntegerField(default=0)),
                ("social_dialogue", models.TextField(blank=True)),
                ("health", models.TextField(blank=True)),
                ("training", models.TextField(blank=True)),
                ("equality", models.TextField(blank=True)),
                ("env_policy", models.TextField(blank=True)),
                ("waste", models.TextField(blank=True)),
                ("water", models.TextField(blank=True)),
                ("energy", models.TextField(blank=True)),
                ("ghg", models.TextField(blank=True)),
                ("biodiversity", models.TextField(blank=True)),
                ("territory", models.TextField(blank=True)),
                ("neighbors", models.TextField(blank=True)),
                ("patronage", models.TextField(blank=True)),
                ("purchases", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="esg_reports",
                        to="tenancy.company",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="tenancy.organization"),
                ),
            ],
            options={"ordering": ["-year"]},
        ),
        migrations.AddConstraint(
            model_name="esgreport",
            constraint=models.UniqueConstraint(fields=("company", "year"), name="uniq_esg_company_year"),
        ),
    ]
