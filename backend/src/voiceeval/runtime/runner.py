"""The disposable CallRunner.

Drives one physical CallAttempt end to end: it connects the target adapter,
runs the caller loop, normalizes provider observations into canonical events,
evaluates stop conditions after every event, and streams telemetry to the
backend. All clocks are explicit — runner monotonic for ordering, wall clock for
metadata, media timestamp for audio.

The runner is transport-agnostic and caller-agnostic: it only knows the
``AgentConnection`` contract and the ``CallerController`` interface.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from voiceeval.core.clocks import monotonic_ms as default_monotonic_ms
from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import ConnectionFailedError
from voiceeval.core.logging import bind_execution_context
from voiceeval.domain.enums import AttemptStatus
from voiceeval.observability.tracing import span
from voiceeval.runtime.adapters.base import TargetAdapter
from voiceeval.runtime.caller.controller import CallerController
from voiceeval.runtime.connections import (
    AgentConnection,
    AudioChunk,
    CloseReason,
    ConnectionConfig,
)
from voiceeval.runtime.events import (
    CanonicalEvent,
    CanonicalEventBuilder,
    EventSource,
    EventType,
)
from voiceeval.runtime.media.recorder import MediaArtifactRecord, MediaRecorder
from voiceeval.runtime.media.tts import TTS
from voiceeval.runtime.providers.base import TTSProvider
from voiceeval.runtime.providers.deterministic import DeterministicTTS
from voiceeval.runtime.scenario import Scenario
from voiceeval.runtime.stop_conditions import (
    StopConditionEngine,
    StopDecision,
    StopReason,
)
from voiceeval.runtime.telemetry import (
    CONTROL_CANCEL,
    CONTROL_TERMINATE,
    TelemetrySink,
)

logger = logging.getLogger("voiceeval.runner")

RUNNER_VERSION = "runner.v1"
DEFAULT_RUNNER_ID = "runner-1"
HEARTBEAT_INTERVAL_S = 5.0
CALLER_SAMPLE_RATE = 16000

LifecycleHook = Callable[[AttemptStatus], Awaitable[None]]
MediaSink = Callable[[MediaArtifactRecord], Awaitable[None]]


@dataclass
class RunOutcome:
    attempt_id: str
    terminal_status: str
    failure_class: str | None
    eligible: bool
    stop_reason: str | None
    evidence_event_id: str | None
    events_emitted: int = 0
    agent_turns: int = 0
    caller_turns: int = 0
    audio_bytes_sent: int = 0
    media: list[MediaArtifactRecord] = field(default_factory=list)

    def terminal_payload(self) -> dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "terminal_status": self.terminal_status,
            "failure_class": self.failure_class,
            "eligible": self.eligible,
            "reason": self.stop_reason,
            "evidence_event_id": self.evidence_event_id,
        }


class CallRunner:
    def __init__(
        self,
        *,
        attempt_id: str,
        adapter: TargetAdapter,
        endpoint_config: dict[str, Any],
        scenario: Scenario,
        telemetry: TelemetrySink,
        runner_id: str = DEFAULT_RUNNER_ID,
        runner_version: str = RUNNER_VERSION,
        provider: TTSProvider | None = None,
        settings: Settings | None = None,
        stop_engine: StopConditionEngine | None = None,
        caller: CallerController | None = None,
        lifecycle: LifecycleHook | None = None,
        media_sink: MediaSink | None = None,
        clock: Callable[[], int] = default_monotonic_ms,
    ) -> None:
        self._attempt_id = attempt_id
        self._adapter = adapter
        self._endpoint_config = endpoint_config
        self._scenario = scenario
        self._telemetry = telemetry
        self._runner_id = runner_id
        self._runner_version = runner_version
        self._provider = provider or DeterministicTTS()
        self._settings = settings or get_settings()
        self._clock = clock
        self._lifecycle = lifecycle
        self._media_sink = media_sink

        self._builder = CanonicalEventBuilder(attempt_id, monotonic_clock=clock)
        self._caller_recorder = MediaRecorder(
            track="caller", clock_domain="runner_monotonic"
        )
        self._tts = TTS(
            self._provider,
            self._builder,
            sample_rate=CALLER_SAMPLE_RATE,
            recorder=self._caller_recorder,
        )
        self._caller = caller or CallerController(
            scenario, tts=self._tts, builder=self._builder
        )
        self._stop = stop_engine or StopConditionEngine(
            stall_ms=self._settings.conversation_stall_ms,
            wall_clock_timeout_ms=self._settings.wall_clock_timeout_ms,
            max_wall_clock_timeout_ms=self._settings.max_wall_clock_timeout_ms,
            clock=clock,
        )
        self._connection: AgentConnection | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._events_emitted = 0
        self._agent_turns = 0

    @property
    def caller(self) -> CallerController:
        return self._caller

    @property
    def stop_engine(self) -> StopConditionEngine:
        return self._stop

    @property
    def attempt_id(self) -> str:
        return self._attempt_id

    # -- lifecycle ------------------------------------------------------------

    async def run(self) -> RunOutcome:
        with bind_execution_context(attempt_id=self._attempt_id):
            with span("runtime.attempt", attempt_id=self._attempt_id):
                return await self._run_attempt()

    async def _run_attempt(self) -> RunOutcome:
        await self._telemetry.connect()
        await self._notify_lifecycle(AttemptStatus.STARTING)

        await self._emit(
            EventType.CONNECTION_REQUESTED,
            source=EventSource.RUNTIME,
            payload={
                "url": self._endpoint_config.get("url"),
                "adapter": self._adapter.name,
            },
        )

        decision: StopDecision | None = None
        try:
            decision = await self._connect_and_run()
        except ConnectionFailedError as exc:
            logger.warning("attempt %s connection failure: %s", self._attempt_id, exc)
            decision = self._stop.fail(
                reason=StopReason.CONNECTION_FAILURE, detail={"error": str(exc)}
            )
        except Exception as exc:  # unexpected runner failure -> infrastructure
            logger.exception("attempt %s runner crash", self._attempt_id)
            decision = self._stop.fail(
                reason=StopReason.CONNECTION_FAILURE,
                detail={"error": str(exc), "runner_crash": True},
            )

        await self._notify_lifecycle(AttemptStatus.TERMINATING)
        await self._teardown(decision)
        return await self._finalize(decision)

    async def _connect_and_run(self) -> StopDecision:
        connection = self._adapter.build_connection(self._endpoint_config)
        self._connection = connection
        config: ConnectionConfig = self._adapter.connection_config(self._endpoint_config)
        await self._notify_lifecycle(AttemptStatus.CONNECTING)
        with span(
            "runtime.target.connect",
            attempt_id=self._attempt_id,
            adapter=self._adapter.name,
        ):
            await connection.connect(config)
        await self._emit(
            EventType.CONNECTION_WS_OPEN,
            source=EventSource.RUNTIME,
            payload={"url": config.url},
        )
        await self._emit(
            EventType.CONNECTION_READY, source=EventSource.RUNTIME, payload={}
        )
        await self._notify_lifecycle(AttemptStatus.RUNNING)
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        start_step = await self._caller.start()
        for event in start_step.events:
            await self._emit_event(event)

        return await self._conversation_loop(connection)

    async def _conversation_loop(self, connection: AgentConnection) -> StopDecision:
        pending: list[CanonicalEvent] = []
        receiver = connection.receive().__aiter__()

        while True:
            control = await self._telemetry.next_control(0)
            if control is not None and control.get("type") in (
                CONTROL_CANCEL,
                CONTROL_TERMINATE,
            ):
                return self._stop.fail(
                    reason=StopReason.CANCELLED,
                    detail={"control": control.get("type")},
                )

            timeout_s = max(0.001, self._stop.remaining_stall_ms() / 1000)
            try:
                raw = await asyncio.wait_for(receiver.__anext__(), timeout=timeout_s)
            except asyncio.TimeoutError:
                decision = self._stop.check_timeouts()
                if decision is not None:
                    return decision
                continue
            except StopAsyncIteration:
                return self._stop.fail(
                    reason=StopReason.CONNECTION_FAILURE,
                    detail={"error": "target stream ended"},
                )

            canonical = self._adapter.to_canonical(raw, self._builder)
            stop: StopDecision | None = None
            for event in canonical:
                await self._emit_event(event)
                stop = self._stop.observe(event) or stop
                if event.type == EventType.TURN_END.value:
                    self._agent_turns += 1
                pending.append(event)
                if event.type == EventType.TURN_END.value:
                    step_decision = await self._respond(pending)
                    pending = []
                    stop = step_decision or stop
                    if stop is not None:
                        return stop

            if stop is not None:
                return stop

            decision = self._stop.check_timeouts()
            if decision is not None:
                return decision

    async def _respond(self, pending: list[CanonicalEvent]) -> StopDecision | None:
        with span("runtime.caller.execute", attempt_id=self._attempt_id):
            step = await self._caller.observe_agent_event(None, list(pending))
        stop: StopDecision | None = None
        for event in step.events:
            await self._emit_event(event)
            stop = self._stop.observe(event) or stop
        # Speak even on a terminal step: a caller that acknowledges resolution
        # and then ends the call still has to transmit the acknowledgement.
        if step.turn_id is not None:
            await self._send_step_audio(step.audio, step.turn_id)
        return stop

    async def _send_step_audio(self, chunks: list[AudioChunk], turn_id: str | None) -> None:
        connection = self._connection
        if connection is None:
            return
        for chunk in chunks:
            await connection.send_audio(chunk)
        if turn_id and hasattr(connection, "send_control"):
            await connection.send_control(
                {"type": "caller.turn.end", "turn_id": turn_id}
            )

    # -- teardown -------------------------------------------------------------

    async def _teardown(self, decision: StopDecision | None) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        await self._caller.stop()
        if self._connection is not None:
            try:
                await self._connection.close(self._close_reason(decision))
            except Exception:  # pragma: no cover - teardown races
                pass

    async def _finalize(self, decision: StopDecision | None) -> RunOutcome:
        if decision is None:
            decision = self._stop.fail(reason=StopReason.CONNECTION_FAILURE)

        record = self._caller_recorder.finalize()
        media: list[MediaArtifactRecord] = []
        if record.size_bytes > 0:
            media.append(record)
            if self._media_sink is not None:
                try:
                    await self._media_sink(record)
                except Exception:  # pragma: no cover - persistence is best-effort
                    logger.warning("media persistence failed for %s", self._attempt_id)

        terminal_event = await self._emit(
            EventType.ATTEMPT_TERMINAL,
            source=EventSource.RUNTIME,
            payload=decision.as_payload(),
        )
        await self._telemetry.close()

        return RunOutcome(
            attempt_id=self._attempt_id,
            terminal_status=decision.terminal_status.value,
            failure_class=(
                decision.failure_class.value if decision.failure_class else None
            ),
            eligible=decision.eligible,
            stop_reason=decision.reason.value,
            evidence_event_id=decision.evidence_event_id or terminal_event.event_id,
            events_emitted=self._events_emitted,
            agent_turns=self._agent_turns,
            caller_turns=self._caller.turn_index,
            audio_bytes_sent=self._caller_recorder.size_bytes,
            media=media,
        )

    @staticmethod
    def _close_reason(decision: StopDecision | None) -> CloseReason:
        if decision is None:
            return CloseReason.RUNNER_SHUTDOWN
        mapping = {
            StopReason.NATURAL_SUCCESS: CloseReason.NATURAL_SUCCESS,
            StopReason.CONVERSATION_STALL: CloseReason.CONVERSATION_STALL,
            StopReason.WALL_CLOCK_TIMEOUT: CloseReason.WALL_CLOCK_TIMEOUT,
            StopReason.CONNECTION_FAILURE: CloseReason.CONNECTION_FAILURE,
            StopReason.CANCELLED: CloseReason.PLAN_CANCELLED,
        }
        return mapping.get(decision.reason, CloseReason.CALLER_ENDED)

    # -- plumbing -------------------------------------------------------------

    async def _notify_lifecycle(self, status: AttemptStatus) -> None:
        if self._lifecycle is not None:
            await self._lifecycle(status)

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                await self._telemetry.heartbeat()
        except asyncio.CancelledError:
            return

    async def _emit(
        self, event_type: str, *, source: str, payload: dict[str, Any]
    ) -> CanonicalEvent:
        return await self._emit_event(
            self._builder.build(event_type, source=source, payload=payload)
        )

    async def _emit_event(self, event: CanonicalEvent) -> CanonicalEvent:
        self._events_emitted += 1
        await self._telemetry.send_event(event)
        return event
