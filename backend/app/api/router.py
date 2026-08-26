from fastapi import APIRouter

from app.api.routers import health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)

# Later batches add routers here: auth, admin_config, customers, tickets, kb, ai, channels,
# portal, reports, api_keys — per contracts/openapi.yaml's tags.
