"""Stage 1 orchestration: build every ledger in parallel (spec §3).

Capability-gated: builders whose evidence a requested metric needs are run; the
rest are skipped. ``evidence_coverage`` is the share of requested-metric
evidence that was successfully built.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from voiceeval.judging.evidence.claims import build_claim_ledger
from voiceeval.judging.evidence.emotion import build_emotion_timeline
from voiceeval.judging.evidence.facts import build_fact_registry
from voiceeval.judging.evidence.injection import InjectionScreen
from voiceeval.judging.evidence.instructions import build_instruction_checklist
from voiceeval.judging.evidence.intents import build_intent_ledger
from voiceeval.judging.evidence.preservation import build_preservation_pairs
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.goals import build_goal_checklist
from voiceeval.judging.probes.jev import JevRunner
from voiceeval.judging.stage0.runner import Stage0Result
from voiceeval.llm.base import BaseGenerationModel
from voiceeval.metrics.signals import AttemptSignals

logger = logging.getLogger("voiceeval.judging.evidence")

LEDGER_KEYS = ("claim", "fact", "intent", "instruction", "goal", "emotion", "preservation")


@dataclass
class Ledgers:
    claim: LedgerResult | None = None
    fact: LedgerResult | None = None
    intent: LedgerResult | None = None
    instruction: LedgerResult | None = None
    goal: LedgerResult | None = None
    emotion: LedgerResult | None = None
    preservation: LedgerResult | None = None
    injection: dict[int | str, float] = field(default_factory=dict)

    def get(self, key: str) -> LedgerResult | None:
        return getattr(self, key, None)

    def items(self, key: str) -> list[Any]:
        ledger = self.get(key)
        return list(ledger.items) if ledger else []

    @property
    def coverage(self) -> float:
        present = sum(1 for key in LEDGER_KEYS if getattr(self, key) is not None)
        return present / len(LEDGER_KEYS)


@dataclass
class EvidenceContext:
    llm: BaseGenerationModel | None
    runner: JevRunner
    stage0: Stage0Result
    signals: AttemptSignals
    evaluator_content: dict[str, Any]
    judge_prompt: str
    scenario: str
    language_policy: dict[str, Any]
    requested_metrics: set[str]


def _numbered_transcript(stage0: Stage0Result) -> str:
    lines: list[str] = []
    for turn in stage0.turns:
        speaker = "CALLER" if turn.speaker == "caller" else "AGENT"
        lines.append(f"[turn {turn.turn_id}] {speaker}: {turn.text}")
    return "\n".join(lines)


class EvidenceBuilder:
    def __init__(self, *, injection: InjectionScreen | None = None) -> None:
        self._screen = injection

    async def build(self, ctx: EvidenceContext) -> Ledgers:
        inputs = LedgerInputs(
            transcript=_numbered_transcript(ctx.stage0),
            known_turn_ids={turn.turn_id for turn in ctx.stage0.turns},
            stage0=ctx.stage0,
            signals=ctx.signals,
            evaluator_content=ctx.evaluator_content,
            judge_prompt=ctx.judge_prompt,
            scenario=ctx.scenario,
            language_policy=ctx.language_policy,
        )
        llm = ctx.llm

        builders = {
            "claim": build_claim_ledger(llm, inputs),
            "fact": build_fact_registry(llm, inputs),
            "intent": build_intent_ledger(llm, inputs),
            "instruction": build_instruction_checklist(llm, inputs),
            "goal": build_goal_checklist(llm, inputs),
            "emotion": build_emotion_timeline(llm, inputs),
            "preservation": build_preservation_pairs(llm, inputs),
        }
        if self._screen is not None:
            builders["injection"] = self._screen_agent_turns(ctx)

        results = await asyncio.gather(*builders.values(), return_exceptions=True)
        ledgers = Ledgers()
        injection: dict[int | str, float] = {}
        for key, result in zip(builders.keys(), results):
            if isinstance(result, Exception):
                logger.info("ledger %s failed: %s", key, result)
                setattr(ledgers, key if key != "injection" else "injection",
                        None if key != "injection" else injection)
                continue
            if key == "injection":
                injection = result  # type: ignore[assignment]
                ledgers.injection = injection
            else:
                setattr(ledgers, key, result)
        return ledgers

    async def _screen_agent_turns(self, ctx: EvidenceContext) -> dict[int | str, float]:
        assert self._screen is not None
        agent_turns = {
            turn.turn_id: turn.text
            for turn in ctx.stage0.turns
            if turn.speaker == "agent" and turn.text
        }
        try:
            return await self._screen.screen_turns(agent_turns)
        except Exception as exc:  # noqa: BLE001 - best-effort screen
            logger.info("injection screen failed: %s", exc)
            return {}


__all__ = ["EvidenceBuilder", "EvidenceContext", "Ledgers"]
