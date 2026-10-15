"""Pipecat caller spawning layer: the concurrency cap."""

from __future__ import annotations

import asyncio

from voiceeval.runtime.pipecat_caller import supervisor as supervisor_module
from voiceeval.runtime.pipecat_caller.settings import PipecatCallerSettings
from voiceeval.runtime.pipecat_caller.supervisor import CallerSupervisor


async def test_supervisor_caps_concurrency(monkeypatch):
    state = {"active": 0, "peak": 0}

    class _FakeAgent:
        def __init__(self, attempt_id: str, **kwargs) -> None:
            self._attempt_id = attempt_id

        async def run(self) -> str:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            try:
                await asyncio.sleep(0.05)
            finally:
                state["active"] -= 1
            return "NATURAL_SUCCESS"

    monkeypatch.setattr(supervisor_module, "PipecatCallerAgent", _FakeAgent)
    supervisor = CallerSupervisor(
        settings=PipecatCallerSettings(_env_file=None, max_concurrent=3)
    )

    reasons = await supervisor.run_attempts([f"att_{i}" for i in range(10)])

    assert len(reasons) == 10
    assert reasons == ["NATURAL_SUCCESS"] * 10
    assert state["peak"] <= 3
