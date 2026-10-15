"""Naive Pipecat caller runtime (websocket targets).

A separate, additive caller runtime: a plain LLM-driven Pipecat pipeline that
dials a target over a websocket, records both audio directions and uploads them
after the call. It reuses the shared control plane (manifest load, telemetry,
media persistence) but does not touch the LiveKit or scripted-caller runtimes.
"""

from __future__ import annotations

from voiceeval.runtime.pipecat_caller.agent import PipecatCallerAgent
from voiceeval.runtime.pipecat_caller.context import CallerContext, load_caller_context
from voiceeval.runtime.pipecat_caller.settings import (
    PipecatCallerSettings,
    get_pipecat_caller_settings,
)
from voiceeval.runtime.pipecat_caller.supervisor import CallerSupervisor

__all__ = [
    "CallerContext",
    "CallerSupervisor",
    "PipecatCallerAgent",
    "PipecatCallerSettings",
    "get_pipecat_caller_settings",
    "load_caller_context",
]
