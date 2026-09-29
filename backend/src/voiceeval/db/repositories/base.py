"""Shared repository helpers.

Repositories are thin persistence facades over an async session. They perform
domain-meaningful operations (create revision, freeze version, transition
status) rather than exposing generic CRUD, and they keep SQLAlchemy models out
of the API layer.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ResourceNotFoundError

_ModelT = TypeVar("_ModelT")


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get(self, model: type[_ModelT], id_: str, *, name: str) -> _ModelT:
        obj = await self._session.get(model, id_)
        if obj is None:
            raise ResourceNotFoundError(f"{name} '{id_}' not found")
        return obj
