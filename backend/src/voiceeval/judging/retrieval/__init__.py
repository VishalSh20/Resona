"""KB retrieval seam (spec §6.2)."""

from voiceeval.judging.retrieval.base import NoopRetrieval, RetrievedChunk, Retrieval
from voiceeval.judging.retrieval.factory import get_retrieval, set_retrieval

__all__ = ["NoopRetrieval", "RetrievedChunk", "Retrieval", "get_retrieval", "set_retrieval"]
