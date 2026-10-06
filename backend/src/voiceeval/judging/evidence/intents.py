"""Caller intent ledger (spec §3.2): explicit, implicit and scenario-outcome intents."""

from __future__ import annotations

from voiceeval.judging.evidence.extract import extract_items
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import IntentItem, RawIntentList
from voiceeval.llm.base import BaseGenerationModel

_SYSTEM = (
    "You extract caller intents from a call: explicit requests, implicit needs, "
    "and intents implied by the scenario's expected outcome. Mark intents whose "
    "failure would defeat the call as critical."
)
_USER = """Scenario / expected outcome:
{scenario}

Transcript:
{transcript}

Return caller intents with a verbatim quote and turn_ids."""


def _fallback(inputs: LedgerInputs) -> list[IntentItem]:
    items = []
    for turn in inputs.stage0.turns:
        if turn.speaker != "caller":
            continue
        items.append(
            IntentItem(
                intent_id=f"intent-{turn.turn_id}",
                text=turn.text,
                critical=False,
                source="explicit",
                turn_ids=[turn.turn_id],
                quote=turn.text,
            )
        )
    return items


async def build_intent_ledger(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    items = await extract_items(
        llm, RawIntentList, "items", system=_SYSTEM,
        user=_USER.format(scenario=inputs.scenario, transcript=inputs.transcript),
        transcript=inputs.transcript, known_turn_ids=inputs.known_turn_ids,
    )
    if not items:
        items = _fallback(inputs)  # type: ignore[assignment]
    return LedgerResult(ledger_type="intent", status="ok", items=list(items))


__all__ = ["build_intent_ledger"]
