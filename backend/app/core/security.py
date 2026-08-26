from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from passlib.context import CryptContext

from app.config import settings

ALGORITHM = "HS256"

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


class InvalidTokenError(Exception):
    pass


def _issue_token(user_id: uuid.UUID, token_type: Literal["access", "refresh"], ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def issue_access_token(user_id: uuid.UUID) -> str:
    return _issue_token(user_id, "access", timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES))


def issue_refresh_token(user_id: uuid.UUID) -> str:
    return _issue_token(user_id, "refresh", timedelta(days=settings.JWT_REFRESH_TTL_DAYS))


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> uuid.UUID:
    """Raises InvalidTokenError on any decode failure, expiry, or a token of the wrong type
    (e.g. a refresh token presented where an access token is required) — callers never see a
    raw PyJWT exception."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"expected a {expected_type} token")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("malformed subject claim") from exc
