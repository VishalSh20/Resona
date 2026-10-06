"""Strict ledger item schemas (spec §3.1).

Every item cites ``turn_ids`` and a verbatim ``quote``; a failed quote check
rejects the item, so no ledger entry can reference text the transcript does not
contain.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LedgerItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_ids: list[int | str] = Field(default_factory=list)
    quote: str = ""


class ClaimItem(LedgerItem):
    claim_id: str
    text: str
    type: str = "domain_fact"
    severity: str = "minor"


class FactItem(LedgerItem):
    fact_id: str
    text: str
    stated_turn: int | str | None = None
    critical: bool = False


class IntentItem(LedgerItem):
    intent_id: str
    text: str
    critical: bool = False
    source: str = "explicit"


class InstructionItem(LedgerItem):
    instruction_id: str
    text: str
    type: str = "must"
    severity: str = "major"
    evaluator: str = "jev"
    trigger: str | None = None
    unstable: bool = False


class GoalItem(LedgerItem):
    goal_id: str
    condition: str
    critical: bool = False
    verification_source: str = "conversation"


class EmotionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: int | str
    emotion_labels: list[str] = Field(default_factory=list)
    intensity: int = 0
    text_cues: list[str] = Field(default_factory=list)
    prosody_cues: list[str] = Field(default_factory=list)
    agent_voice: str | None = None
    turn_ids: list[int | str] = Field(default_factory=list)
    quote: str = ""


class PreservationPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_span: str
    restated_span: str
    kind: str = "confirmation"
    turn_ids: list[int | str] = Field(default_factory=list)
    quote: str = ""


class RawClaimList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[ClaimItem] = Field(default_factory=list)


class RawFactList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[FactItem] = Field(default_factory=list)


class RawIntentList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[IntentItem] = Field(default_factory=list)


class RawInstructionList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[InstructionItem] = Field(default_factory=list)


class RawGoalList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[GoalItem] = Field(default_factory=list)


class RawEmotionList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[EmotionItem] = Field(default_factory=list)


class RawPreservationList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PreservationPair] = Field(default_factory=list)


def item_payload(item: BaseModel) -> dict[str, Any]:
    return item.model_dump(mode="json")


__all__ = [
    "ClaimItem",
    "EmotionItem",
    "FactItem",
    "GoalItem",
    "InstructionItem",
    "IntentItem",
    "LedgerItem",
    "PreservationPair",
    "RawClaimList",
    "RawEmotionList",
    "RawFactList",
    "RawGoalList",
    "RawInstructionList",
    "RawIntentList",
    "RawPreservationList",
    "item_payload",
]
