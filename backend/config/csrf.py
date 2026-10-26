from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure


def csrf_failure(request, reason=""):
    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return JsonResponse(
            {"detail": "Jeton de sécurité invalide. Rechargez la page, puis réessayez."},
            status=403,
        )
    return django_csrf_failure(request, reason=reason)
