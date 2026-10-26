from django.core.management.base import BaseCommand, CommandError

from apps.identity.beta_test01.provision import assert_beta_database, provision_beta_test01, purge_beta_test01


class Command(BaseCommand):
    help = "BETA-TEST-01 — provisioning idempotent sandbox fictive (muhimu_beta uniquement)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-target",
            action="store_true",
            help="Confirme la cible bêta (obligatoire).",
        )
        parser.add_argument(
            "--force-entries",
            action="store_true",
            help="Recrée les écritures seed si absentes (idempotent par exercice).",
        )
        parser.add_argument(
            "--rotate-passwords",
            action="store_true",
            help="Repose les mots de passe depuis BETA_TEST01_DEFAULT_PASSWORD.",
        )
        parser.add_argument(
            "--purge",
            action="store_true",
            help="Supprime uniquement l'organisation beta-test-01 (destructif, scope limité).",
        )

    def handle(self, *args, **options):
        if not options["confirm_target"]:
            raise CommandError(
                "Refus : ajoutez --confirm-target (cible muhimu_beta). "
                "Exécuter avec rôle propriétaire PG (BYPASSRLS) : "
                "POSTGRES_APP_USER=$POSTGRES_USER POSTGRES_APP_PASSWORD=$POSTGRES_PASSWORD."
            )
        db = assert_beta_database()
        if options["purge"]:
            n = purge_beta_test01()
            self.stdout.write(self.style.WARNING(f"Purge beta-test-01 : {n} objets supprimés (cascade org)."))
            return
        summary = provision_beta_test01(
            force_entries=options["force_entries"],
            rotate_passwords=options["rotate_passwords"],
        )
        self.stdout.write(self.style.SUCCESS(f"Provisioning OK sur {db}"))
        self.stdout.write(str(summary))
