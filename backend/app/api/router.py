from fastapi import APIRouter

from app.api.routers import (
    admin_config,
    ai,
    api_keys,
    auth,
    channels,
    customers,
    health,
    kb,
    portal,
    reports,
    tickets,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(admin_config.router)
api_router.include_router(customers.router)
api_router.include_router(tickets.router)
api_router.include_router(ai.router)
api_router.include_router(kb.router)
api_router.include_router(channels.router)
api_router.include_router(portal.router)
api_router.include_router(reports.router)
api_router.include_router(api_keys.router)
