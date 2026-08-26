from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.permissions import PermissionDeniedError


class IllegalTransitionError(Exception):
    def __init__(self, message_ar: str, message_en: str) -> None:
        self.message_ar = message_ar
        self.message_en = message_en
        super().__init__(message_en)


class NotFoundError(Exception):
    def __init__(self, message_ar: str, message_en: str) -> None:
        self.message_ar = message_ar
        self.message_en = message_en
        super().__init__(message_en)


def _error_response(status_code: int, message_ar: str, message_en: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"message_ar": message_ar, "message_en": message_en},
    )


async def permission_denied_handler(request: Request, exc: PermissionDeniedError) -> JSONResponse:
    return _error_response(
        403,
        f"الإذن مرفوض: {exc.code}",
        f"Permission denied: {exc.code}",
    )


async def illegal_transition_handler(request: Request, exc: IllegalTransitionError) -> JSONResponse:
    return _error_response(422, exc.message_ar, exc.message_en)


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error_response(404, exc.message_ar, exc.message_en)


def register_error_handlers(app) -> None:
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    app.add_exception_handler(IllegalTransitionError, illegal_transition_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
