"""One pipecat caller call: lifecycle, telemetry, recording and upload.

The ordering mirrors the LiveKit caller job: the recording is uploaded *before*
the terminal event is reported, because the control plane deletes resources on
the terminal path and would otherwise cancel the upload.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import DependencyUnavailableError
from voiceeval.db.session import get_session_factory
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.livekit.failure import terminal_payload
from voiceeval.runtime.livekit.media import persist_media_records
from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.pipecat_caller.context import CallerContext, load_caller_context
from voiceeval.runtime.pipecat_caller.pipeline import (
    CallerPipeline,
    build_caller_pipeline,
)
from voiceeval.runtime.pipecat_caller.settings import (
    PipecatCallerSettings,
    get_pipecat_caller_settings,
)
from voiceeval.runtime.runner import RUNNER_VERSION
from voiceeval.runtime.telemetry import RunnerWebSocketClient

logger = logging.getLogger("voiceeval.pipecat_caller")


class _TerminalReason:
    """Holds the first terminal reason seen for a call."""

    def __init__(self) -> None:
        self._value: str | None = None

    def set(self, reason: str) -> None:
        if self._value is None:
            self._value = reason

    @property
    def value(self) -> str | None:
        return self._value


async def _emit_lifecycle(
    telemetry: RunnerWebSocketClient, builder: CanonicalEventBuilder, status: str
) -> None:
    await telemetry.send_event(
        builder.build(
            EventType.ATTEMPT_LIFECYCLE,
            source=EventSource.RUNTIME.value,
            payload={"status": status},
        )
    )


async def _emit_terminal(
    telemetry: RunnerWebSocketClient, builder: CanonicalEventBuilder, reason: str
) -> None:
    await telemetry.send_event(
        builder.build(
            EventType.ATTEMPT_TERMINAL,
            source=EventSource.RUNTIME.value,
            payload=terminal_payload(reason),
        )
    )


class PipecatCallerAgent:
    """Runs one call attempt end to end."""

    def __init__(
        self,
        attempt_id: str,
        *,
        telemetry_url: str,
        runner_id: str | None = None,
        settings: PipecatCallerSettings | None = None,
        core: Settings | None = None,
    ) -> None:
        self._attempt_id = attempt_id
        self._telemetry_url = telemetry_url
        self._runner_id = runner_id or f"runner-{attempt_id}"
        self._settings = settings or get_pipecat_caller_settings()
        self._core = core or get_settings()

    async def run(self) -> str:
        telemetry = RunnerWebSocketClient(
            url=self._telemetry_url,
            attempt_id=self._attempt_id,
            runner_id=self._runner_id,
            runner_version=RUNNER_VERSION,
        )
        await telemetry.connect()
        builder = CanonicalEventBuilder(self._attempt_id)

        recording: AttemptRecording | None = None
        built: CallerPipeline | None = None
        reason: str | None = None
        try:
            async with get_session_factory()() as session:
                context = await load_caller_context(
                    session, self._attempt_id, self._settings
                )
            recording = AttemptRecording(sample_rate=context.in_sample_rate)
            await _emit_lifecycle(telemetry, builder, "connecting")
            built = build_caller_pipeline(
                caller_context=context,
                settings=self._settings,
                recording=recording,
                core=self._core,
            )
            reason = await self._drive(built, context, telemetry, builder)
        except DependencyUnavailableError as exc:
            logger.error("attempt %s: %s", self._attempt_id, exc)
            reason = "INTERNAL_ERROR"
        except Exception:
            logger.exception("attempt %s crashed", self._attempt_id)
            reason = "JOB_CRASH"
        reason = reason or "TARGET_HUNG_UP"

        if recording is not None:
            await self._persist(recording)
        if built is not None:
            self._dump_transcript(built)
        try:
            await _emit_terminal(telemetry, builder, reason)
        except Exception:  # pragma: no cover - best-effort flush
            logger.debug("terminal emit failed for %s", self._attempt_id)
        try:
            await telemetry.close()
        except Exception:  # pragma: no cover - best-effort flush
            logger.debug("telemetry close failed for %s", self._attempt_id)
        return reason

    async def _drive(
        self,
        built: CallerPipeline,
        context: CallerContext,
        telemetry: RunnerWebSocketClient,
        builder: CanonicalEventBuilder,
    ) -> str:
        from pipecat.frames.frames import LLMRunFrame
        from pipecat.workers.runner import WorkerRunner

        reason = _TerminalReason()
        connected = asyncio.Event()
        runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)

        @built.transport.event_handler("on_connected")
        async def _on_connected(transport, websocket) -> None:
            connected.set()

        @built.transport.event_handler("on_disconnected")
        async def _on_disconnected(transport, websocket) -> None:
            reason.set("TARGET_HUNG_UP")
            await runner.cancel("TARGET_HUNG_UP")

        await runner.add_workers(built.task)
        runner_task = asyncio.create_task(
            runner.run(), name=f"pipecat-runner:{self._attempt_id}"
        )
        try:
            await asyncio.wait_for(
                connected.wait(), timeout=self._settings.connect_timeout_s
            )
        except asyncio.TimeoutError:
            reason.set("CONNECTION_FAILURE")
            await runner.cancel("CONNECTION_FAILURE")
            await asyncio.gather(runner_task, return_exceptions=True)
            return "CONNECTION_FAILURE"

        await _emit_lifecycle(telemetry, builder, "running")

        if context.greet_first:
            # A bare run: the system instruction already opens the call, so no
            # fake user turn is written into the history or the transcript.
            await built.task.queue_frames([LLMRunFrame()])

        watchdog = asyncio.create_task(
            self._wall_clock(runner, reason), name=f"pipecat-watchdog:{self._attempt_id}"
        )
        try:
            await runner_task
        finally:
            watchdog.cancel()
            await asyncio.gather(watchdog, return_exceptions=True)
        return reason.value or "TARGET_HUNG_UP"

    async def _wall_clock(self, runner, reason: _TerminalReason) -> None:
        try:
            await asyncio.sleep(self._settings.wall_clock_timeout_s)
        except asyncio.CancelledError:
            return
        reason.set("WALL_CLOCK_TIMEOUT")
        await runner.cancel("WALL_CLOCK_TIMEOUT")

    async def _persist(self, recording: AttemptRecording) -> None:
        try:
            records = recording.finalize()
        except Exception:  # pragma: no cover - finalize is a programming guard
            logger.exception("recording finalize failed for %s", self._attempt_id)
            return
        try:
            async with get_session_factory()() as session:
                stored = await asyncio.wait_for(
                    persist_media_records(session, self._attempt_id, records),
                    timeout=self._settings.upload_timeout_s,
                )
            logger.info("attempt %s uploaded %d media artifacts", self._attempt_id, stored)
        except Exception:  # pragma: no cover - depends on object storage
            logger.exception("media persistence failed for %s", self._attempt_id)

    def _dump_transcript(self, built: CallerPipeline) -> None:
        """Write the call transcript next to the object store (debug/judging only)."""
        try:
            data_dir = Path(self._core.local_object_storage_path).parent
            path = built.transcript.dump(
                data_dir / "transcripts" / f"{self._attempt_id}.json"
            )
            logger.info(
                "attempt %s wrote %d transcript turns to %s",
                self._attempt_id,
                len(built.transcript.entries),
                path,
            )
        except Exception:  # pragma: no cover - diagnostics must not break a call
            logger.exception("transcript dump failed for %s", self._attempt_id)


__all__ = ["PipecatCallerAgent"]
