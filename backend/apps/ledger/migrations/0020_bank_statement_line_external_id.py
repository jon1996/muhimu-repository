from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0019_commitment_class9"),
    ]

    operations = [
        migrations.AddField(
            model_name="bankstatementline",
            name="external_id",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
