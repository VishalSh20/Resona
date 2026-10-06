"""Preservation pairs (spec §3.2): confirmations, summaries, translations, tool args."""

from __future__ import annotations

import re

from voiceeval.judging.evidence.extract import extract_items
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import PreservationPair, RawPreservationList
from voiceeval.llm.base import BaseGenerationModel

_SYSTEM = (
    "You find preservation pairs in a call: places where the agent restates, "
    "confirms, summarises, translates, or passes caller information to a tool. "
    "Kind is one of confirmation, summary, translation, tool_arg."
)
_USER = """Transcript:
{transcript}

Return source_span (the caller's or agent's original) and restated_span (where it
was repeated), with a verbatim quote and turn_ids."""

_TOKEN = re.compile(r"[A-Za-z0-9\u0900-\u0DFF]+")


def _entities(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(text) if any(ch.isdigit() for ch in token)}


def _fallback(inputs: LedgerInputs) -> list[PreservationPair]:
    pairs: list[PreservationPair] = []
    caller_turns = [turn for turn in inputs.stage0.turns if turn.speaker == "caller"]
    agent_turns = [turn for turn in inputs.stage0.turns if turn.speaker == "agent"]
    for agent_turn in agent_turns:
        agent_entities = _entities(agent_turn.text)
        if not agent_entities:
            continue
        for caller_turn in caller_turns:
            if caller_turn.turn_id == agent_turn.turn_id:
                continue
            if agent_entities & _entities(caller_turn.text):
                pairs.append(
                    PreservationPair(
                        source_span=caller_turn.text,
                        restated_span=agent_turn.text,
                        kind="confirmation",
                        turn_ids=[caller_turn.turn_id, agent_turn.turn_id],
                        quote=agent_turn.text,
                    )
                )
                break
    return pairs


async def build_preservation_pairs(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    items = await extract_items(
        llm, RawPreservationList, "items", system=_SYSTEM,
        user=_USER.format(transcript=inputs.transcript),
        transcript=inputs.transcript, known_turn_ids=inputs.known_turn_ids,
    )
    if not items:
        items = _fallback(inputs)  # type: ignore[assignment]
    status = "ok" if items else "invalid"
    return LedgerResult(ledger_type="preservation", status=status, items=list(items))


__all__ = ["build_preservation_pairs"]
