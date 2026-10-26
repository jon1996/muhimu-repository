import json

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

from apps.identity.beta_test01.provision import assert_beta_database
from apps.identity.beta_test01.scenarios import run_all_scenarios


class Command(BaseCommand):
    help = "BETA-TEST-01 — exécute scénarios métier + contrôles sécurité sur la bêta."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm-target",
            action="store_true",
            help="Confirme la cible bêta (obligatoire).",
        )

    def handle(self, *args, **options):
        if not options["confirm_target"]:
            raise CommandError("Refus : ajoutez --confirm-target.")
        assert_beta_database()
        with override_settings(
            ALLOWED_HOSTS=["testserver", "localhost", "backend", "erp.beta.localhost"],
            AUTH_LOGIN_RATE_LIMIT_ENABLED=False,
        ):
            results = run_all_scenarios()
        ok = sum(1 for r in results if r["ok"])
        self.stdout.write(json.dumps({"passed": ok, "total": len(results), "results": results}, indent=2))
        if ok != len(results):
            raise CommandError(f"Échecs : {len(results) - ok}/{len(results)}")
