from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0006_rls_officers"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="setup_data",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Choix d'initialisation : vide, demo, ou non renseigné.",
                max_length=16,
            ),
        ),
    ]
