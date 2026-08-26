import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

from app.api.router import api_router
from app.core.errors import register_error_handlers

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Bilingual Support CRM API")

    @app.middleware("http")
    async def correlation_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    register_error_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
