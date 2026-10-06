"""Claim ledger (spec §3.2).

Atomic agent claims, taken as the union of two extraction passes and de-duplicated
by token similarity. Chitchat is dropped before scoring (spec §3.4).
"""

from __future__ import annotations

from voiceeval.judging.evidence.extract import extract_items
from voiceeval.judging.evidence.quote_check import normalize
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import ClaimItem, RawClaimList
from voiceeval.llm.base import BaseGenerationModel

_SYSTEM = (
    "You extract atomic factual claims made by the AGENT in a call transcript. "
    "Return only claims the agent asserted. Include the type and a verbatim quote "
    "with the turn ids it came from."
)
_USER = """Transcript:
{transcript}

Extract every agent claim. Types: domain_fact, numeric_date_entity, action_claim,
policy_statement, commitment, chitchat. Chitchat = greetings/small talk."""


def _similarity(a: str, b: str) -> float:
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _dedup(items: list[ClaimItem], threshold: float = 0.8) -> list[ClaimItem]:
    kept: list[ClaimItem] = []
    for item in items:
        if item.type == "chitchat":
            continue
        if any(_similarity(item.text, existing.text) >= threshold for existing in kept):
            continue
        kept.append(item)
    return kept


async def build_claim_ledger(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    user = _USER.format(transcript=inputs.transcript)
    first = await extract_items(
        llm, RawClaimList, "items", system=_SYSTEM, user=user,
        transcript=inputs.transcript, known_turn_ids=inputs.known_turn_ids,
    )
    second = await extract_items(
        llm, RawClaimList, "items", system=_SYSTEM, user=user,
        transcript=inputs.transcript, known_turn_ids=inputs.known_turn_ids,
    )
    claims = _dedup([*first, *second])  # type: ignore[arg-type]
    status = "ok" if claims or llm is None else "invalid"
    return LedgerResult(ledger_type="claim", status=status, items=list(claims))


__all__ = ["build_claim_ledger"]
