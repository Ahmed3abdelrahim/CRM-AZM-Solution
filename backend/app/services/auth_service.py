from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import InvalidCredentialsError
from app.core.permissions import CurrentActor
from app.core.security import InvalidTokenError, decode_token, issue_access_token, issue_refresh_token, verify_password
from app.models.user import User
from app.schemas.auth import TokenPair


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _token_pair(self, user_id) -> TokenPair:
        return TokenPair(
            access_token=issue_access_token(user_id),
            refresh_token=issue_refresh_token(user_id),
            expires_in=settings.JWT_ACCESS_TTL_MINUTES * 60,
        )

    async def login(self, email: str, password: str) -> TokenPair:
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        # A wrong email, a wrong password, and a deactivated account all raise the same error —
        # login must not disclose which part of the attempt was wrong.
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        user.last_login_at = datetime.now(timezone.utc)
        return self._token_pair(user.id)

    async def refresh(self, refresh_token: str) -> TokenPair:
        try:
            user_id = decode_token(refresh_token, expected_type="refresh")
        except InvalidTokenError as exc:
            raise InvalidCredentialsError() from exc
        user = await self.session.get(User, user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError()
        return self._token_pair(user.id)

    async def logout(self, actor: CurrentActor) -> None:
        # Stateless JWT, no server-side session/blocklist table in data-model.md this sprint —
        # logout is a client-side token discard; nothing to write here.
        return None
