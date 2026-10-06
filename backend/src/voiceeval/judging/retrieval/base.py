"""Retrieval protocol (spec §0.1 ``kb_collection_id``).

A real vector-store retriever can be plugged in later; until then the no-op
implementation returns nothing, so ``kb_groundedness`` is ``not_applicable``
when no collection is configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Retrieval(Protocol):
    async def retrieve(
        self, query: str, *, collection_id: str, k: int = 8
    ) -> list[RetrievedChunk]: ...

    def enabled(self, collection_id: str | None) -> bool: ...


class NoopRetrieval:
    async def retrieve(
        self, query: str, *, collection_id: str, k: int = 8
    ) -> list[RetrievedChunk]:
        return []

    def enabled(self, collection_id: str | None) -> bool:
        return False


__all__ = ["NoopRetrieval", "RetrievedChunk", "Retrieval"]
