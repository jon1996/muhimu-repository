"""Envoi d'e-mails via Namecheap Private Email (SMTP)."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from apps.platform.models import DemoGrant
from apps.tenancy.models import Organization

DEMO_PME_SLUG = "demo-pme"
DEMO_CABINET_SLUG = "demo-cabinet"


def mail_status() -> dict:
    backend = settings.EMAIL_BACKEND
    smtp_ready = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD) and "smtp" in backend
    if "smtp" in backend:
        mode = "smtp"
    elif "console" in backend:
        mode = "console"
    elif "locmem" in backend:
        mode = "test"
    else:
        mode = backend.rsplit(".", 2)[-2] if "." in backend else backend
    return {
        "provider": "Namecheap Private Email",
        "host": settings.EMAIL_HOST,
        "port": settings.EMAIL_PORT,
        "use_ssl": bool(settings.EMAIL_USE_SSL),
        "use_tls": bool(settings.EMAIL_USE_TLS),
        "username": settings.EMAIL_HOST_USER,
        "from_email": settings.DEFAULT_FROM_EMAIL,
        "password_set": bool(settings.EMAIL_HOST_PASSWORD),
        "backend": backend,
        "mode": mode,
        "configured": smtp_ready,
        "erp_url": settings.ERP_PUBLIC_URL,
    }


def send_templated_mail(*, subject: str, to: str, template: str, context: dict) -> None:
    try:
        validate_email(to)
    except ValidationError as exc:
        raise ValueError("Adresse e-mail invalide.") from exc
    payload = {**context, "year": timezone.now().year}
    text = render_to_string(f"platform/email/{template}.txt", payload)
    html = render_to_string(f"platform/email/{template}.html", payload)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)


def send_test_mail(to: str) -> None:
    status = mail_status()
    send_templated_mail(
        subject="Muhimu — test d'envoi",
        to=to,
        template="mail_test",
        context={
            "to": to,
            "from_email": status["from_email"],
            "host": status["host"],
            "port": status["port"],
            "mode": status["mode"],
        },
    )


def send_demo_credentials(user, password: str, *, access_pme: bool, access_cabinet: bool) -> None:
    login_url = settings.ERP_PUBLIC_URL.rstrip("/") + "/login"
    sme = Organization.objects.filter(slug=DEMO_PME_SLUG, is_demo=True).first()
    cabinet = Organization.objects.filter(slug=DEMO_CABINET_SLUG, is_demo=True).first()
    scopes: list[str] = []
    if access_pme and sme is not None:
        scopes.append(f"PME — {sme.name}")
    elif access_pme:
        scopes.append("PME démo")
    if access_cabinet and cabinet is not None:
        scopes.append(f"Cabinet — {cabinet.name}")
    elif access_cabinet:
        scopes.append("Cabinet démo")
    send_templated_mail(
        subject="Votre accès Muhimu ERP",
        to=user.email,
        template="demo_access",
        context={
            "full_name": user.get_full_name(),
            "email": user.email,
            "password": password,
            "login_url": login_url,
            "scopes": scopes,
            "scope_txt": ", ".join(scopes) or "aucun dossier",
        },
    )


def deliver_demo_mail(grant: DemoGrant, password: str | None) -> tuple[bool, str]:
    if not password:
        return False, "Aucun mot de passe à envoyer."
    try:
        send_demo_credentials(
            grant.user,
            password,
            access_pme=grant.access_pme,
            access_cabinet=grant.access_cabinet,
        )
    except Exception as exc:
        return False, str(exc) or "Envoi SMTP impossible."
    grant.last_emailed_at = timezone.now()
    grant.save(update_fields=["last_emailed_at", "updated_at"])
    return True, ""
