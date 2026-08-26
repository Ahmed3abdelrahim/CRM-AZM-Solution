from fastapi import APIRouter

from app.api.routers import admin_config, auth, customers, health, tickets

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin_config.router)
api_router.include_router(customers.router)
api_router.include_router(tickets.router)

# Later batches add routers here: kb, ai, channels, portal, reports, api_keys — per
# contracts/openapi.yaml's tags.
