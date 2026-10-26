from ninja import NinjaAPI
from ninja.security import SessionAuth

from apps.platform.api import router as platform_router

platform_api = NinjaAPI(
    title="Muhimu Console API",
    version="0.1.0",
    description="Administration SaaS — séparée de l'ERP",
    csrf=True,
    auth=SessionAuth(),
    urls_namespace="platform_api",
)

platform_api.add_router("", platform_router)
