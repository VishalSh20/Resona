"""Shared API dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.auth.dependencies import require_user
from voiceeval.core.config import get_settings
from voiceeval.core.errors import ValidationError
from voiceeval.db.session import get_session


async def get_session_dep() -> AsyncIterator[AsyncSession]:
    """Yield an async session for the lifetime of a request."""
    async for session in get_session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session_dep)]


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Require an Idempotency-Key header on state-changing requests."""
    if not idempotency_key:
        raise ValidationError("missing Idempotency-Key header")
    return idempotency_key


IdempotencyKeyDep = Annotated[str, Depends(require_idempotency_key)]

# Applied at router level so every control-plane route requires a user JWT.
# The only unauthenticated surface is the signed media-blob endpoint, which is
# authorised by its short-lived HMAC signature instead of a bearer token.
require_user_dep = Depends(require_user)


async def redis_available() -> bool:
    """Best-effort Redis liveness check used by the readiness endpoint."""
    client = redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await client.ping()
        return True
    except Exception:
        return False
    finally:
        await client.aclose()
