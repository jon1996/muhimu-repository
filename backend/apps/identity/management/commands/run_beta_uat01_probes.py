import json

from django.core.management.base import BaseCommand, CommandError
from django.test.utils import override_settings

from apps.identity.beta_test01.provision import assert_beta_database
from apps.identity.beta_test01.uat_probe import run_uat_probes


class Command(BaseCommand):
    help = "BETA-UAT-01 — sondes lecture seule SME/CABINET + API (sans mutation)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm-target", action="store_true")

    def handle(self, *args, **options):
        if not options["confirm_target"]:
            raise CommandError("Ajoutez --confirm-target.")
        assert_beta_database()
        with override_settings(
            ALLOWED_HOSTS=["testserver", "localhost", "erp.beta.localhost"],
            AUTH_LOGIN_RATE_LIMIT_ENABLED=False,
        ):
            payload = run_uat_probes()
        self.stdout.write(json.dumps(payload, indent=2))
