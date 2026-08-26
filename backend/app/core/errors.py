from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.permissions import PermissionDeniedError


class IllegalTransitionError(Exception):
    """contracts/openapi.yaml's `IllegalTransitionError` — 422, naming the ticket's current
    status and every status it could legally move to instead (FR-017)."""

    def __init__(
        self,
        message_ar: str,
        message_en: str,
        current_status_id: UUID,
        permitted_status_ids: list[UUID],
    ) -> None:
        self.message_ar = message_ar
        self.message_en = message_en
        self.current_status_id = current_status_id
        self.permitted_status_ids = permitted_status_ids
        super().__init__(message_en)


class NotFoundError(Exception):
    def __init__(self, message_ar: str, message_en: str) -> None:
        self.message_ar = message_ar
        self.message_en = message_en
        super().__init__(message_en)


class InvalidCredentialsError(Exception):
    """Raised by AuthService.login/refresh — deliberately carries no detail (wrong email, wrong
    password, and an unknown email all map to this single error) so /auth/login never discloses
    which part of a login attempt was wrong."""


class ValidationError(Exception):
    """A bilingual 422, for a business-rule check a schema type alone can't express (e.g.
    CustomerService.create's exactly-one-primary-contact-method rule, FR-011)."""

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
    return JSONResponse(
        status_code=422,
        content={
            "message_ar": exc.message_ar,
            "message_en": exc.message_en,
            "current_status_id": str(exc.current_status_id),
            "permitted_status_ids": [str(status_id) for status_id in exc.permitted_status_ids],
        },
    )


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error_response(404, exc.message_ar, exc.message_en)


async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError) -> JSONResponse:
    return _error_response(401, "بيانات الاعتماد غير صحيحة", "Invalid credentials")


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return _error_response(422, exc.message_ar, exc.message_en)


def register_error_handlers(app) -> None:
    app.add_exception_handler(PermissionDeniedError, permission_denied_handler)
    app.add_exception_handler(IllegalTransitionError, illegal_transition_handler)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(InvalidCredentialsError, invalid_credentials_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
