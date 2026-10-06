"""Ledger result container shared by all Stage-1 builders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from voiceeval.judging.stage0.runner import Stage0Result
    from voiceeval.metrics.signals import AttemptSignals


@dataclass
class LedgerInputs:
    """Everything a Stage-1 builder needs, assembled once per judge run."""

    transcript: str
    known_turn_ids: set[int | str]
    stage0: "Stage0Result"
    signals: "AttemptSignals"
    evaluator_content: dict[str, Any]
    judge_prompt: str
    scenario: str
    language_policy: dict[str, Any]


@dataclass
class LedgerResult:
    ledger_type: str
    status: str = "ok"  # ok | unstable | invalid
    items: list[BaseModel] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    raw: list[dict[str, Any]] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {
            "ledger_type": self.ledger_type,
            "status": self.status,
            "items": [item.model_dump(mode="json") for item in self.items],
        }


__all__ = ["LedgerResult"]
