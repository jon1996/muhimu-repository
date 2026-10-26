from django.db import migrations, models


def backfill_taxonomy(apps, schema_editor):
    Account = apps.get_model("ledger", "Account")
    from apps.ledger.taxonomy import classify

    batch = []
    fields = [
        "code",
        "account_class",
        "level",
        "family",
        "sense",
        "is_collective",
        "is_postable",
    ]
    for account in Account.objects.all().iterator():
        info = classify(account.code)
        account.code = info["code"]
        if info["account_class"]:
            account.account_class = info["account_class"]
        account.level = info["level"]
        account.family = info["family"]
        account.sense = info["sense"]
        account.is_collective = info["is_collective"]
        if info["level"] == "class":
            account.is_postable = False
        batch.append(account)
        if len(batch) >= 250:
            Account.objects.bulk_update(batch, fields)
            batch = []
    if batch:
        Account.objects.bulk_update(batch, fields)


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0002_rls"),
    ]

    operations = [
        migrations.AlterField(
            model_name="account",
            name="code",
            field=models.CharField(max_length=24),
        ),
        migrations.AddField(
            model_name="account",
            name="level",
            field=models.CharField(
                choices=[
                    ("class", "Classe"),
                    ("subclass", "Sous-classe"),
                    ("principal", "Compte principal"),
                    ("secondary", "Compte secondaire"),
                    ("auxiliary", "Compte auxiliaire"),
                ],
                default="principal",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="family",
            field=models.CharField(
                choices=[
                    ("resource", "Ressources durables"),
                    ("fixed_asset", "Actif immobilisé"),
                    ("stock", "Stocks"),
                    ("third_party", "Tiers"),
                    ("treasury", "Trésorerie"),
                    ("expense", "Charges AO"),
                    ("income", "Produits AO"),
                    ("other", "Autres charges / produits"),
                ],
                default="other",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="sense",
            field=models.CharField(
                choices=[
                    ("debit", "Débiteur"),
                    ("credit", "Créditeur"),
                    ("either", "Mixte"),
                ],
                default="either",
                max_length=8,
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="is_collective",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="account",
            name="is_syscohada",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="account",
            name="notes",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.RunPython(backfill_taxonomy, migrations.RunPython.noop),
    ]
