"""Fact registry (spec §3.2): caller facts, constraints, commitments, referents."""

from __future__ import annotations

from voiceeval.judging.evidence.extract import extract_items
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import FactItem, RawFactList
from voiceeval.llm.base import BaseGenerationModel

_SYSTEM = (
    "You build a fact registry for a call. Capture every fact, preference, "
    "constraint, commitment and referent stated by either speaker. Mark "
    "constraints and safety-critical facts as critical."
)
_USER = """Transcript:
{transcript}

Return the fact registry. Each fact needs stated_turn, critical, a verbatim quote
and turn_ids."""


def _fallback(inputs: LedgerInputs) -> list[FactItem]:
    facts: list[FactItem] = []
    for turn in inputs.stage0.turns:
        fact_id = f"fact-{turn.turn_id}"
        facts.append(
            FactItem(
                fact_id=fact_id,
                text=turn.text,
                stated_turn=turn.turn_id,
                critical=False,
                turn_ids=[turn.turn_id],
                quote=turn.text,
            )
        )
    return facts


async def build_fact_registry(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    items = await extract_items(
        llm, RawFactList, "items", system=_SYSTEM, user=_USER.format(transcript=inputs.transcript),
        transcript=inputs.transcript, known_turn_ids=inputs.known_turn_ids,
    )
    if not items:
        items = _fallback(inputs)  # type: ignore[assignment]
    return LedgerResult(ledger_type="fact", status="ok", items=list(items))


__all__ = ["build_fact_registry"]
