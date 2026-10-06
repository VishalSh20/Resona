"""Deterministic quote check (spec §5.1).

Every ledger item and finding must cite a quote that appears in the transcript
after whitespace/punctuation normalization. The check is script-aware so
Devanagari and Latin text are compared consistently.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
# Keep letters/digits across scripts; drop punctuation and separators.
_NON_WORD = re.compile(r"[^\w\u0900-\u0DFF]+", re.UNICODE)


def normalize(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _NON_WORD.sub(" ", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


def quote_in_transcript(quote: str, transcript: str) -> bool:
    normalized_quote = normalize(quote)
    if not normalized_quote:
        return False
    return normalized_quote in normalize(transcript)


def check_turn_ids_exist(turn_ids: list[int | str], known: set[int | str]) -> bool:
    return all(turn_id in known for turn_id in turn_ids)


def validate_item(
    *,
    quote: str,
    turn_ids: list[int | str],
    transcript: str,
    known_turn_ids: set[int | str],
) -> tuple[bool, str | None]:
    """Return ``(ok, reason)`` for one ledger item / finding."""
    if not quote.strip():
        return False, "missing_quote"
    if not check_turn_ids_exist(turn_ids, known_turn_ids):
        return False, "unknown_turn_id"
    if not quote_in_transcript(quote, transcript):
        return False, "quote_not_in_transcript"
    return True, None


__all__ = [
    "check_turn_ids_exist",
    "normalize",
    "quote_in_transcript",
    "validate_item",
]
