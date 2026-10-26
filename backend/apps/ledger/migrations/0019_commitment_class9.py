import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0018_rls_esg_report"),
    ]

    operations = [
        migrations.AddField(
            model_name="commitment",
            name="entry",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="commitments",
                to="ledger.entry",
            ),
        ),
    ]
