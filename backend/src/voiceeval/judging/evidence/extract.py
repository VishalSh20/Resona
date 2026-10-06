"""Shared strict-JSON extraction helper for the ledger builders.

Runs the LLM in structured mode, validates the items, then quote-checks every
item; items that fail are dropped (and the builder retries once).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel

from voiceeval.judging.evidence.quote_check import validate_item
from voiceeval.llm.base import BaseGenerationModel, LLMError

logger = logging.getLogger("voiceeval.judging.evidence")


async def extract_items(
    llm: BaseGenerationModel | None,
    list_model: type[BaseModel],
    item_attr: str,
    *,
    system: str,
    user: str,
    transcript: str,
    known_turn_ids: set[int | str],
    retries: int = 2,
) -> list[BaseModel]:
    if llm is None:
        return []
    for attempt in range(retries):
        try:
            result = await llm.structured(list_model, system=system, user=user)
        except (LLMError, Exception) as exc:  # noqa: BLE001 - degrade, never fail the run
            logger.info("ledger extraction failed (%s); attempt %d", exc, attempt + 1)
            continue
        items = list(getattr(result, item_attr) or [])
        kept: list[BaseModel] = []
        for item in items:
            ok, _ = validate_item(
                quote=getattr(item, "quote", ""),
                turn_ids=list(getattr(item, "turn_ids", []) or []),
                transcript=transcript,
                known_turn_ids=known_turn_ids,
            )
            if ok:
                kept.append(item)
        if kept or not items:
            return kept
    return []


__all__ = ["extract_items"]
