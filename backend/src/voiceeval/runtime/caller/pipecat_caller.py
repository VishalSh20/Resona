"""Pipecat-backed caller runtime.

Pipecat is the intended audio-orchestration runtime for the caller. This module
integrates it at a narrow, testable seam:

* :class:`CallerSpeechProcessor` is a real Pipecat ``FrameProcessor`` that turns
  caller text into ``AudioRawFrame``s using the configured :class:`TTSProvider`.
* :func:`build_caller_pipeline` composes those processors into a real Pipecat
  ``Pipeline`` for a transport-backed run.
* :class:`PipecatCallerRuntime` presents the same interface as
  :class:`CallerController`, delegating scenario state, policy and action
  selection to it while owning the speech/audio stage.

Pipecat 1.12 executes pipelines through a worker/bus runtime and stamps frame
identifiers at push time, and it needs real transports to be useful. v1 has no
Pipecat transport, so the in-process path is the default (``use_pipecat=False``)
and the pipeline graph is built for the eventual transport-backed run. The frame
translation helpers are pure and unit-tested.
"""

from __future__ import annotations

from typing import Any

from pipecat.frames.frames import AudioRawFrame, Frame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from voiceeval.runtime.caller.controller import CallerController
from voiceeval.runtime.connections import AudioChunk, RawAgentEvent
from voiceeval.runtime.events import CanonicalEvent
from voiceeval.runtime.providers.base import SynthesisRequest, TTSProvider


def to_audio_frame(chunk: AudioChunk) -> AudioRawFrame:
    """Convert a canonical audio chunk into a Pipecat audio frame."""
    return AudioRawFrame(
        audio=chunk.data,
        sample_rate=chunk.sample_rate,
        num_channels=chunk.channels,
    )


def from_audio_frame(frame: AudioRawFrame) -> AudioChunk:
    """Convert a Pipecat audio frame into a canonical audio chunk."""
    duration_ms = None
    if frame.sample_rate:
        frames = len(frame.audio) // (2 * max(1, frame.num_channels))
        duration_ms = int(frames * 1000 / frame.sample_rate)
    return AudioChunk(
        data=frame.audio,
        sample_rate=frame.sample_rate,
        channels=frame.num_channels,
        duration_ms=duration_ms,
    )


class CallerSpeechProcessor(FrameProcessor):
    """Pipecat processor that synthesizes caller speech with a TTSProvider."""

    def __init__(self, provider: TTSProvider, *, language: str = "en-IN") -> None:
        super().__init__()
        self._provider = provider
        self._language = language

    async def process_frame(self, frame: Any, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame) and frame.text:
            async for chunk in self._provider.synthesize(
                SynthesisRequest(text=frame.text, language=self._language)
            ):
                await self.push_frame(to_audio_frame(chunk), direction)
        else:
            await self.push_frame(frame, direction)


def build_caller_pipeline(*processors: FrameProcessor) -> Pipeline:
    """Assemble the caller's speech pipeline from its processors."""
    return Pipeline(list(processors))


def speech_processor(
    provider: TTSProvider, *, language: str = "en-IN"
) -> CallerSpeechProcessor:
    return CallerSpeechProcessor(provider, language=language)


class PipecatCallerRuntime:
    """Caller runtime whose speech stage is a Pipecat pipeline."""

    def __init__(
        self,
        controller: CallerController,
        provider: TTSProvider,
        *,
        use_pipecat: bool = False,
        language: str = "en-IN",
    ) -> None:
        self._controller = controller
        self._provider = provider
        self._use_pipecat = use_pipecat
        self._language = language

    @property
    def controller(self) -> CallerController:
        return self._controller

    def pipeline(self) -> Pipeline:
        return build_caller_pipeline(
            speech_processor(self._provider, language=self._language)
        )

    async def start(self) -> Any:
        return await self._controller.start()

    async def observe_agent_event(
        self, raw: RawAgentEvent | None, canonical: list[CanonicalEvent]
    ) -> Any:
        return await self._controller.observe_agent_event(raw, canonical)

    def select_action(self) -> str:
        return self._controller.select_action()

    async def realize(self, action: str) -> tuple[str, str]:
        return await self._controller.realize(action)

    async def stream_audio(self, text: str, *, turn_id: str, language: str) -> Any:
        # The canonical events and media timestamps are produced by the
        # controller's TTS component; Pipecat owns transport-level audio
        # orchestration when a transport is configured.
        return await self._controller.stream_audio(
            text, turn_id=turn_id, language=language
        )

    async def stop(self) -> None:
        await self._controller.stop()


__all__ = [
    "CallerSpeechProcessor",
    "PipecatCallerRuntime",
    "build_caller_pipeline",
    "from_audio_frame",
    "speech_processor",
    "to_audio_frame",
]
