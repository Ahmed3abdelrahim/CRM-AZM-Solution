from fastapi import APIRouter

from app.api.routers import admin_config, auth, health

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin_config.router)

# Later batches add routers here: customers, tickets, kb, ai, channels, portal, reports,
# api_keys — per contracts/openapi.yaml's tags.
