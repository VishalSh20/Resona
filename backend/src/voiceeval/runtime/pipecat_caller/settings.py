"""Pipecat caller configuration.

The pipecat caller reads its own knobs from ``PIPECAT_CALLER_*`` environment
variables (optionally a local ``.env``). Provider credentials are taken from the
shared application settings, so nothing is duplicated.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class PipecatCallerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="PIPECAT_CALLER_",
    )

    # Spawning layer.
    max_concurrent: int = 5
    poll_interval_s: float = 2.0
    #: Target-link transports this runtime will dial (comma-separated).
    target_transports: str = "websocket,fake"
    #: Websocket wire protocol used when a target does not declare one itself.
    #: ``protobuf`` is Pipecat's native framing (what a real Pipecat agent
    #: serves); ``voiceeval`` is the raw-PCM/JSON protocol of the fake target.
    protocol: Literal["protobuf", "voiceeval"] = "protobuf"
    #: How long to wait for the target websocket before calling it a failure.
    connect_timeout_s: float = 15.0
    #: How long to wait for the recording upload before giving up on it.
    upload_timeout_s: float = 60.0

    # Pipeline.
    stt_model: str = "saaras:v4"
    tts_model: str = "bulbul:v3"
    tts_voice: str = "shubh"
    language: str = "hi-IN"
    in_sample_rate: int = 16_000
    out_sample_rate: int = 16_000
    #: Whether the caller opens the conversation with a short greeting.
    greet_first: bool = True
    #: Wall-clock cap for one call (mirrors ``wall_clock_timeout_ms``).
    wall_clock_timeout_s: float = 180.0

    # Conversation context: messages kept verbatim, and the count that triggers
    # folding everything older into the rolling summary. The trigger must exceed
    # the window or a fresh summary would immediately re-trigger.
    window_messages: int = 12
    summarize_after: int = 20

    @property
    def allowed_transports(self) -> tuple[str, ...]:
        return tuple(
            part.strip() for part in self.target_transports.split(",") if part.strip()
        )


@lru_cache
def get_pipecat_caller_settings() -> PipecatCallerSettings:
    return PipecatCallerSettings()


__all__ = ["PipecatCallerSettings", "get_pipecat_caller_settings"]
