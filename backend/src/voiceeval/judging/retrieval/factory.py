"""Process-wide retrieval singleton (no-op until a vector store is wired)."""

from __future__ import annotations

from voiceeval.judging.retrieval.base import NoopRetrieval, Retrieval

_retrieval: Retrieval | None = None


def get_retrieval() -> Retrieval:
    global _retrieval
    if _retrieval is None:
        _retrieval = NoopRetrieval()
    return _retrieval


def set_retrieval(retrieval: Retrieval | None) -> None:
    global _retrieval
    _retrieval = retrieval


__all__ = ["get_retrieval", "set_retrieval"]
