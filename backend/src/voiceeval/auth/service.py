"""Credential authentication service (sign-up / sign-in).

The smallest real identity model on top of the existing ``users``/``user_roles``
support tables: email + password credentials, an ``user`` role, and a user-scope
JWT. This replaces the previous out-of-band-only token issuance for interactive
clients; the CLI still exists for service accounts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.auth.jwt import create_user_token
from voiceeval.auth.passwords import hash_password, verify_password
from voiceeval.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    ValidationError,
)
from voiceeval.db.models.support import User
from voiceeval.db.repositories import UserRepository

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_ROLE = "user"
MIN_PASSWORD_LENGTH = 8


@dataclass
class AuthenticatedUser:
    user: User
    token: str
    roles: list[str] = field(default_factory=list)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        username: str | None = None,
    ) -> AuthenticatedUser:
        email = (email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValidationError("a valid email address is required")
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise ValidationError(
                f"password must be at least {MIN_PASSWORD_LENGTH} characters"
            )
        if await self._users.find_by_email(email) is not None:
            raise ConflictError(
                "an account with this email already exists",
                code="EMAIL_ALREADY_REGISTERED",
            )
        if username and await self._users.find_by_username(username) is not None:
            raise ConflictError(
                "this username is already taken", code="USERNAME_ALREADY_TAKEN"
            )

        try:
            user = await self._users.create_user(
                email=email,
                username=username,
                password_hash=hash_password(password),
            )
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "an account with this email already exists",
                code="EMAIL_ALREADY_REGISTERED",
            ) from exc

        await self._users.add_role(user.id, DEFAULT_ROLE)
        return AuthenticatedUser(
            user=user,
            token=create_user_token(user.id),
            roles=[DEFAULT_ROLE],
        )

    async def login(self, *, email: str, password: str) -> AuthenticatedUser:
        identifier = (email or "").strip().lower()
        user = await self._users.find_by_email(identifier)
        if user is None:
            user = await self._users.find_by_username(identifier)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("invalid email or password")
        if not user.is_active:
            raise AuthorizationError("this account is disabled")
        return AuthenticatedUser(
            user=user,
            token=create_user_token(user.id),
            roles=await self._users.list_roles(user.id),
        )

    async def get_user(self, user_id: str) -> User:
        return await self._users.get_user(user_id)

    async def list_roles(self, user_id: str) -> list[str]:
        return await self._users.list_roles(user_id)


__all__ = ["AuthService", "AuthenticatedUser", "DEFAULT_ROLE", "MIN_PASSWORD_LENGTH"]
