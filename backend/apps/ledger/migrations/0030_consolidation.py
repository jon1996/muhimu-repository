import uuid
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0029_rls_fxrate"),
        ("tenancy", "0006_rls_officers"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsolidationGroup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                (
                    "kind",
                    models.CharField(
                        choices=[("consolidated", "Consolidé"), ("combined", "Combiné")],
                        default="consolidated",
                        max_length=16,
                    ),
                ),
                ("year", models.PositiveSmallIntegerField()),
                ("currency_code", models.CharField(default="XOF", max_length=3)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consolidation_groups",
                        to="tenancy.organization",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="consolidation_parents",
                        to="tenancy.company",
                    ),
                ),
            ],
            options={"ordering": ["-year", "name"]},
        ),
        migrations.CreateModel(
            name="ConsolidationMember",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "method",
                    models.CharField(
                        choices=[
                            ("full", "Intégration globale"),
                            ("proportional", "Intégration proportionnelle"),
                            ("equity", "Mise en équivalence"),
                            ("combined", "Combinaison"),
                        ],
                        default="full",
                        max_length=16,
                    ),
                ),
                ("ownership_pct", models.DecimalField(decimal_places=4, default=Decimal("100"), max_digits=7)),
                ("is_parent", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="consolidation_memberships",
                        to="tenancy.company",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="ledger.consolidationgroup",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="tenancy.organization"),
                ),
            ],
            options={"ordering": ["-is_parent", "company__name"]},
        ),
        migrations.CreateModel(
            name="ConsolidationElimination",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=8)),
                ("label", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=19)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("sales", "Chiffre d’affaires / achats"),
                            ("rec_pay", "Créances / dettes"),
                            ("investment", "Titres / capitaux"),
                            ("dividend", "Dividendes"),
                            ("other", "Autre"),
                        ],
                        default="other",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="eliminations",
                        to="ledger.consolidationgroup",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="tenancy.organization"),
                ),
            ],
            options={"ordering": ["code", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="consolidationgroup",
            constraint=models.UniqueConstraint(
                fields=("organization", "name", "year"), name="uniq_consolidation_org_name_year"
            ),
        ),
        migrations.AddConstraint(
            model_name="consolidationmember",
            constraint=models.UniqueConstraint(fields=("group", "company"), name="uniq_consolidation_member"),
        ),
    ]
