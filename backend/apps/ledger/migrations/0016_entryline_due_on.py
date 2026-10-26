from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0015_rls_commitment"),
    ]

    operations = [
        migrations.AddField(
            model_name="entryline",
            name="due_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
