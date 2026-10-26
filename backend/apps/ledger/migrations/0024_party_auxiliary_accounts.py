from django.db import migrations


def forwards(apps, schema_editor):
    ThirdParty = apps.get_model("ledger", "ThirdParty")
    from apps.tenancy.rls import bypass_rls

    with bypass_rls():
        if not ThirdParty.objects.exists():
            return
        from apps.ledger.models import ThirdParty as LiveThirdParty
        from apps.ledger.services.lettering import ensure_party_auxiliary, is_subdivision

        parties = LiveThirdParty.objects.select_related("account", "company", "company__organization")
        for party in parties:
            if not party.account_id or is_subdivision(party.account.code):
                continue
            aux = ensure_party_auxiliary(
                party.company,
                kind=party.kind,
                name=party.name,
                reference=party.reference,
                base=party.account,
            )
            if aux.id != party.account_id:
                party.account = aux
                party.save(update_fields=["account"])


def backwards(apps, schema_editor):
    return


class Migration(migrations.Migration):
    dependencies = [
        ("ledger", "0023_commitment_origin_entry"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
