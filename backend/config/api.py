from ninja import NinjaAPI
from ninja.security import SessionAuth

from apps.audit.api import router as audit_router
from apps.identity.api import router as identity_router
from apps.ledger.api import router as ledger_router
from apps.tenancy.api import router as tenancy_router

api = NinjaAPI(
    title="Muhimu ERP API",
    version="0.1.0",
    description="API SaaS Comptabilité / FinTech SYSCOHADA",
    csrf=True,
    auth=SessionAuth(),
)

api.add_router("", identity_router)
api.add_router("", tenancy_router)
api.add_router("", audit_router)
api.add_router("", ledger_router)
