"""Idempotency-key handling.

State-changing endpoints require an ``Idempotency-Key`` header. The key is
recorded with its scope and (when a body exists) a hash of the request so a
repeated request is rejected instead of creating duplicate work — a duplicate
revision, a duplicate validation job, a duplicate logical repetition.

The reservation runs inside the request's transaction, so if the operation fails
before commit the key is rolled back with it and a later retry is not blocked.
The database ``UNIQUE(key)`` constraint is the final guard against two
concurrent requests that both pass the existence check: the loser surfaces as a
clean ``409`` rather than an integrity error.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ConflictError
from voiceeval.core.ids import new_plain_ulid
from voiceeval.db.models.support import IdempotencyKey


def hash_request(payload: Any) -> str:
    """Stable SHA-256 of a request body, used to detect key reuse."""
    data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class IdempotencyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(
        self, key: str, scope: str, *, request_hash: str | None = None
    ) -> IdempotencyKey:
        """Record ``key`` for ``scope``, rejecting a duplicate.

        Raises :class:`ConflictError` if the key has already been used. When a
        ``request_hash`` is supplied it is stored, and reusing the key for a
        different body is reported distinctly. The DB unique constraint backstops
        the check so concurrent duplicates cannot both succeed.
        """
        existing = await self._find(key)
        if existing is not None:
            self._reject(existing, request_hash)

        record = IdempotencyKey(
            id=new_plain_ulid(), key=key, scope=scope, request_hash=request_hash
        )
        self._session.add(record)
        try:
            await self._session.flush()
        except IntegrityError as exc:  # concurrent request won the race
            raise ConflictError(
                f"idempotency key '{key}' has already been used"
            ) from exc
        return record

    @staticmethod
    def _reject(existing: IdempotencyKey, request_hash: str | None) -> None:
        if (
            request_hash is not None
            and existing.request_hash is not None
            and existing.request_hash != request_hash
        ):
            raise ConflictError(
                f"idempotency key '{existing.key}' was used for a different request"
            )
        raise ConflictError(
            f"idempotency key '{existing.key}' has already been used for scope "
            f"'{existing.scope}'"
        )

    async def _find(self, key: str) -> IdempotencyKey | None:
        result = await self._session.execute(
            select(IdempotencyKey).where(IdempotencyKey.key == key)
        )
        return result.scalar_one_or_none()
