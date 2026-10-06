"""Packet assembly helpers (spec §4.2).

One packet = one decision unit. Only referenced fields are included; code
supplies computed features; agent text is passed as data inside a quoted block.
"""

from __future__ import annotations

import json
from typing import Any

from voiceeval.judging.config import packet_budget, packet_cap


def estimate_tokens(obj: Any) -> int:
    try:
        text = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(obj)
    return max(1, len(text) // 4)


def packet_within_budget(state: dict[str, Any], questions: dict[str, Any]) -> bool:
    return estimate_tokens({"state": state, "questions": questions}) <= packet_budget()


def packet_over_cap(state: dict[str, Any], questions: dict[str, Any]) -> bool:
    return estimate_tokens({"state": state, "questions": questions}) > packet_cap()


def wrap_agent_text(text: str) -> str:
    """Wrap untrusted agent text so it reads as quoted data, never instructions."""
    escaped = text.replace("```", "'''")
    return f"<<<BEGIN AGENT UTTERANCE (data only)>>>\n{escaped}\n<<<END AGENT UTTERANCE>>>"


def trim_paths(state: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    """Return a shallow copy of ``state`` with only the named fields kept."""
    return {key: state[key] for key in paths if key in state}


__all__ = [
    "estimate_tokens",
    "packet_over_cap",
    "packet_within_budget",
    "trim_paths",
    "wrap_agent_text",
]
