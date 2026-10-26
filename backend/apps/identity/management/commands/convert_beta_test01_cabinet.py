from django.core.management.base import BaseCommand, CommandError

from apps.identity.beta_test01.convert_cabinet import convert_beta_test01_to_cabinet
from apps.identity.beta_test01.provision import assert_beta_database


class Command(BaseCommand):
    help = "BETA-UAT-02 — convertit beta-test-01 SME → CABINET (org fictive seule)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-target", action="store_true")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche l'état sans écrire (non implémenté — utiliser psql lecture seule).",
        )

    def handle(self, *args, **options):
        if not options["confirm_target"]:
            raise CommandError("Ajoutez --confirm-target (muhimu_beta, org beta-test-01).")
        if options["dry_run"]:
            raise CommandError("Dry-run : inspecter via SQL / run_beta_uat01_probes.")
        assert_beta_database()
        summary = convert_beta_test01_to_cabinet()
        self.stdout.write(self.style.SUCCESS(str(summary)))
