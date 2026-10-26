from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0007_company_setup_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="setup_data",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Choix d'initialisation de l'organisation : vide, demo, ou non renseigné.",
                max_length=16,
            ),
        ),
    ]
