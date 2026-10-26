from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0008_organization_setup_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="is_demo",
            field=models.BooleanField(
                default=False,
                help_text="Sandbox de démonstration, hors clients réels.",
            ),
        ),
    ]
