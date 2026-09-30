"""The caller runtime interface.

The runner drives the caller through this interface only. ``CallerController``
is the default in-process implementation; a Pipecat-backed runtime can be
substituted without the runner changing.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from voiceeval.runtime.connections import RawAgentEvent
from voiceeval.runtime.events import CanonicalEvent


@runtime_checkable
class CallerRuntime(Protocol):
    async def start(self) -> Any: ...

    async def observe_agent_event(
        self, raw: RawAgentEvent | None, canonical: list[CanonicalEvent]
    ) -> Any: ...

    def select_action(self) -> str: ...

    async def realize(self, action: str) -> tuple[str, str]: ...

    async def stream_audio(self, text: str, *, turn_id: str, language: str) -> Any: ...

    async def stop(self) -> None: ...
