from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"
    label = "identity"
    verbose_name = "Identité"

    def ready(self) -> None:
        from django.contrib.auth.signals import user_logged_in

        from apps.identity.session_policy import stamp_session_on_login

        def _on_login(sender, request, user, **kwargs):
            stamp_session_on_login(request)

        user_logged_in.connect(_on_login, dispatch_uid="muhimu_session_stamp")
