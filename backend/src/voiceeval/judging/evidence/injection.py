"""Injection screen (spec §5.2).

Each agent turn entering any packet is screened with a Jev Noul. Turns above the
threshold are marked ``injection_suspected``, wrapped as quoted data, and every
probe touching them is routed to the LLM adjudicator.
"""

from __future__ import annotations

import asyncio

from voiceeval.core.config import get_settings
from voiceeval.judging.probes.jev import JevRunner
from voiceeval.judging.probes.registry import get_probe


class InjectionScreen:
    def __init__(self, runner: JevRunner, *, threshold: float | None = None) -> None:
        self._runner = runner
        self._threshold = threshold if threshold is not None else get_settings().injection_tau
        self._probe = get_probe("inj.v1")

    async def screen_turn(self, turn_id: int | str, text: str) -> float:
        answer = await self._runner.run_single(
            {"agent_text": text}, self._probe.probe_id, self._probe.question()
        )
        return float(answer.value or 0.0)

    async def screen_turns(self, turns: dict[int | str, str]) -> dict[int | str, float]:
        """Screen many turns concurrently, returning ``turn_id -> P(injection)``."""
        if not turns:
            return {}
        results = await asyncio.gather(
            *(self.screen_turn(turn_id, text) for turn_id, text in turns.items())
        )
        return dict(zip(turns.keys(), results))

    def is_suspected(self, probability: float) -> bool:
        return probability > self._threshold


__all__ = ["InjectionScreen"]
