"""Link-boundary conversation loop for the caller job (§4.2, §10).

The TargetLink is the audio boundary we own: caller speech is synthesized by our
TTS and sent through ``link.send_audio``, target audio is read from
``link.incoming_audio``. Both directions are recorded in-process, so the exact
audio the target heard and produced is what lands in object storage.

Turn-taking is floor-controlled, not timeout-controlled:

* a continuous, real-time-paced 20 ms playout stream (speech when the caller is
  talking, silence otherwise) so the target's own endpointing sees a realistic
  user stream;
* fused target-activity signals (ASR server VAD, provider speech events, and a
  local energy VAD) drive a :class:`FloorTracker`;
* the caller answers only once the target is *quiet* (VAD end + ASR lag grace),
  takes initiative after long silence, yields when interrupted mid-speech, and
  can barge in on a monologuing or repeating target.

Late ASR segments of an utterance that was already answered are dropped via a
"busy epoch" (they are history, not new triggers) — that is what stops the
caller from replying twice to the same target turn.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import math
import time
from array import array
from collections.abc import Awaitable, Callable
from typing import Any

from voiceeval.runtime.caller.floor import FloorEvent, FloorTracker
from voiceeval.runtime.caller.pipeline import CallerDecisionPipeline, Decision
from voiceeval.runtime.caller.turn_analyzer import TurnAnalyzer, _similarity
from voiceeval.runtime.connections import AudioChunk, RawAgentEvent
from voiceeval.runtime.events import (
    CanonicalEvent,
    CanonicalEventBuilder,
    EventSource,
    EventType,
)
from voiceeval.runtime.livekit.failure import terminal_payload
from voiceeval.runtime.livekit.lifecycle import LifecycleMachine, ConnectionState
from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.providers.base import SynthesisRequest, TTSProvider

logger = logging.getLogger("voiceeval.livekit.conversation")

EmitFn = Callable[[CanonicalEvent], Awaitable[None]]

_FRAME_MS = 20
_TICK_S = 0.05
#: How long after our own speech a late ASR final is still considered stale.
_STALE_WINDOW_MS = 1200
_PROBE_AT_IDLE_MS = (6_000, 14_000)
_PROBE_GIVE_UP_MS = 24_000


def _rms_s16le(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = array("h")
    samples.frombytes(data[: count * 2])
    if samples.itemsize != 2:  # pragma: no cover - non-standard platform
        return 0.0
    acc = 0
    for value in samples:
        acc += value * value
    return math.sqrt(acc / count)


class _EnergyVad:
    """Adaptive energy VAD over incoming PCM — the always-available floor signal.

    Runs locally on every received chunk, so it is synchronous with the audio
    (no network lag) and works for links whose provider sends no speech events.
    """

    def __init__(
        self,
        *,
        min_threshold: float = 500.0,
        hangover_ms: int = 300,
    ) -> None:
        self._floor = 120.0
        self._min_threshold = min_threshold
        self._hangover_ms = hangover_ms
        self._speaking = False
        self._last_above_ms: int | None = None

    def update(self, data: bytes, at_ms: int) -> bool:
        level = _rms_s16le(data)
        threshold = max(self._min_threshold, self._floor * 4.0)
        if level >= threshold:
            self._speaking = True
            self._last_above_ms = at_ms
        else:
            # Adapt the noise floor only while not in speech, and slowly.
            if not self._speaking:
                self._floor = min(
                    800.0, max(30.0, self._floor * 0.97 + level * 0.03)
                )
            if (
                self._last_above_ms is not None
                and at_ms - self._last_above_ms > self._hangover_ms
            ):
                self._speaking = False
        return self._speaking


class _TargetActivity:
    """OR-fusion of target speech signals (energy VAD, ASR VAD, provider).

    Remote VAD signals (Sarvam's ``vad_signals``) arrive with seconds of lag —
    especially the *end* marker — so a stuck-on remote source expires quickly
    and the local energy VAD becomes the end-of-speech pacer.
    """

    #: How long a remote source may stay "on" without reconfirmation.
    REMOTE_ON_CAP_MS = 2_500

    def __init__(self) -> None:
        self._sources: dict[str, bool] = {}
        self._on_since: dict[str, int] = {}
        self.active = False
        self.last_start_ms: int | None = None
        self.last_end_ms: int | None = None

    def set(self, source: str, active: bool, at_ms: int) -> str | None:
        """Update one source; returns ``"start"``/``"end"`` on a fused edge."""
        previous = self.active
        self._sources[source] = active
        if active:
            self._on_since[source] = at_ms
        else:
            self._on_since.pop(source, None)
        fused = any(self._sources.values())
        self.active = fused
        if fused == previous:
            return None
        if fused:
            self.last_start_ms = at_ms
            return "start"
        self.last_end_ms = at_ms
        return "end"

    def stale_sources(self, at_ms: int) -> list[str]:
        """Remote sources stuck on past the cap (their END signal is late)."""
        return [
            name
            for name, since in self._on_since.items()
            if name != "energy" and self._sources.get(name) and at_ms - since > self.REMOTE_ON_CAP_MS
        ]


class _Playout:
    """Paces a continuous, real-time 20 ms frame stream into the link.

    Speech comes from the buffer (fed by TTS); silence is sent whenever the
    buffer is empty, so the target's endpointing sees a normal user stream and
    the caller recording is continuous (aligned with the agent track). The
    buffer is cleared on barge-in (the caller stops mid-utterance).
    """

    def __init__(
        self,
        *,
        link: Any,
        recording: AttemptRecording,
        sample_rate: int,
        clock: Callable[[], float],
        on_speaking_change: Callable[[bool], None],
    ) -> None:
        self._link = link
        self._recording = recording
        self._sample_rate = sample_rate
        self._clock = clock
        self._on_speaking_change = on_speaking_change
        self._frame_bytes = max(2, int(sample_rate * _FRAME_MS / 1000) * 2)
        self._buffer = bytearray()
        self.speaking = False
        self.failed: Exception | None = None
        self._closed = False

    def enqueue(self, chunk: AudioChunk) -> None:
        self._buffer.extend(chunk.data)

    def interrupt(self) -> None:
        """Stop speaking immediately (the caller yields the floor)."""
        self._buffer.clear()

    async def wait_idle(self, timeout_s: float = 10.0) -> None:
        deadline = self._clock() + timeout_s
        while self._buffer and self._clock() < deadline and self.failed is None:
            await asyncio.sleep(_FRAME_MS / 1000)

    def close(self) -> None:
        self._closed = True

    async def run(self) -> None:
        silence = b"\x00" * self._frame_bytes
        frame_s = _FRAME_MS / 1000
        next_tick = self._clock()
        while not self._closed:
            is_speech = bool(self._buffer)
            if is_speech:
                frame = bytes(self._buffer[: self._frame_bytes])
                del self._buffer[: self._frame_bytes]
            else:
                frame = silence
            chunk = AudioChunk(
                data=frame, sample_rate=self._sample_rate, channels=1
            )
            try:
                await self._link.send_audio(chunk)
            except Exception as exc:  # transport closed mid-call
                self.failed = exc
                return
            self._recording.append_caller(chunk)
            if is_speech != self.speaking:
                self.speaking = is_speech
                self._on_speaking_change(is_speech)
            next_tick += frame_s
            delay = next_tick - self._clock()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                # We fell behind (backpressure or a stall): resync instead of
                # bursting to catch up.
                next_tick = self._clock()


async def _text_stream(asr: Any):
    """Adapt an ASR with only ``transcripts()`` to the event-stream shape."""
    from voiceeval.runtime.providers.sarvam import StreamingAsrEvent

    async for text in asr.transcripts():
        yield StreamingAsrEvent(kind="transcript", text=text)


#: Trailing discourse markers: the target is mid-thought, not done talking.
_PREAMBLE_ENDINGS = (
    "first of all",
    "so listen",
    "brother listen",
    "listen",
    "for example",
    "you see",
    "i mean",
    "basically",
    "actually",
    "okay so",
    "so",
    "like",
    "look",
    "uh",
    "um",
)


def _ends_in_preamble(text: str) -> bool:
    """True when the utterance trails off on a discourse marker — more is coming."""
    tail = " ".join(text.lower().split()[-4:]).rstrip(".!?,").strip()
    if not tail:
        return False
    return any(tail.endswith(marker) for marker in _PREAMBLE_ENDINGS)


class LinkConversationRunner:
    def __init__(
        self,
        *,
        attempt_id: str,
        link,
        pipeline: CallerDecisionPipeline,
        builder: CanonicalEventBuilder,
        recording: AttemptRecording,
        tts: TTSProvider,
        emit: EmitFn,
        clock: Callable[[], float] = time.monotonic,
        max_agent_turns: int = 32,
        turn_silence_s: float = 2.5,
        asr_factory: Callable[[], Any] | None = None,
        end_of_turn_grace_s: float = 0.6,
        asr_lag_grace_s: float = 0.4,
        first_audio_timeout_s: float = 15.0,
        wall_clock_s: float = 180.0,
        stall_backstop_s: float = 45.0,
        tail_s: float = 3.0,
    ) -> None:
        self._attempt_id = attempt_id
        self._link = link
        self._pipeline = pipeline
        self._builder = builder
        self._recording = recording
        self._tts = tts
        self._emit = emit
        self._clock = clock
        self._max_agent_turns = max_agent_turns
        self._turn_silence_ms = int(turn_silence_s * 1000)
        self._asr_factory = asr_factory
        self._asr_active = asr_factory is not None
        self._eot_grace_ms = int(end_of_turn_grace_s * 1000)
        self._asr_lag_ms = int(asr_lag_grace_s * 1000)
        self._first_audio_timeout_ms = int(first_audio_timeout_s * 1000)
        self._wall_clock_ms = int(wall_clock_s * 1000)
        self._stall_backstop_ms = int(stall_backstop_s * 1000)
        self._tail_s = tail_s

        self._floor = FloorTracker(clock=self._ms)
        self._activity = _TargetActivity()
        self._energy_vad = _EnergyVad()
        self._turn_analyzer = TurnAnalyzer()
        self._lifecycle = LifecycleMachine()

        self._playout: _Playout | None = None
        self._asr_queue: asyncio.Queue | None = None
        self._emit_q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._agent_audio_task: asyncio.Task | None = None

        self.terminal_reason: str | None = None
        self._turns = 0
        self._pending: list[str] = []
        self._assertions: list[str] = []
        self._prev_agent_text: str | None = None

        self._decide_task: asyncio.Task | None = None
        self._speak_task: asyncio.Task | None = None
        self._current_step: Decision | None = None
        self._reply_segments: list[str] = []
        self._reply_assertions: list[str] = []
        self._busy_since_ms: int | None = None
        self._abort_speech = False
        self._tts_failed = False
        self._conn_lost: str | None = None

        self._started_ms = 0
        self._first_audio_ms: int | None = None
        self._last_activity_ms = 0
        self._last_signal_ms = 0
        self._last_pending_ms = 0
        self._busy_text_answered: str | None = None
        self._caller_speech_start_ms: int | None = None
        self._caller_speech_end_ms: int | None = None
        self._barge_cooldown_until_ms = 0
        self._false_interruption_flagged = False
        self._opened = False
        self._probe_count = 0
        self._probe_last_ms = 0
        self._target_ever_spoke = False
        self._asr_text_ms = 0
        self._asr_strike_anchor_ms = 0
        self._asr_strikes = 0

    # ------------------------------------------------------------- utilities

    def _ms(self) -> int:
        return int(self._clock() * 1000)

    def _fire(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        source: str = EventSource.RUNTIME.value,
    ) -> None:
        """Fire-and-forget emit: a slow telemetry sink must never stall a turn."""
        event = self._builder.build(
            event_type, source=source, payload=payload, monotonic_ms=self._ms()
        )
        try:
            self._emit_q.put_nowait(event)
        except asyncio.QueueFull:  # pragma: no cover - pathological sink
            logger.warning("emit queue full; dropping %s", event_type)

    async def _emit_drainer(self) -> None:
        while True:
            item = await self._emit_q.get()
            try:
                if item is None:
                    return
                await self._emit(item)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - telemetry must not kill a call
                logger.debug("emit failed", exc_info=True)
            finally:
                self._emit_q.task_done()

    async def _flush_emits(self) -> None:
        await self._emit_q.join()

    def _note_floor_events(self, events: list[FloorEvent]) -> None:
        for event in events:
            self._fire(
                event.kind.value,
                {"state": event.state.value},
                source=EventSource.DERIVED.value,
            )

    def _note_target_activity(self, source: str, active: bool, at_ms: int) -> None:
        edge = self._activity.set(source, active, at_ms)
        if edge is None:
            return
        self._last_activity_ms = at_ms
        self._last_signal_ms = at_ms
        if edge == "start":
            self._target_ever_spoke = True
            self._probe_count = 0
        self._note_floor_events(
            self._floor.note_target_vad(edge == "start", at_ms=at_ms)
        )

    def _expire_activity_sources(self, now: int) -> None:
        """Turn off remote VAD sources whose END marker is overdue."""
        for source in self._activity.stale_sources(now):
            logger.debug("activity source %s expired (END signal late)", source)
            self._note_target_activity(source, False, now)

    def _on_caller_speaking_change(self, speaking: bool) -> None:
        now = self._ms()
        if speaking:
            self._caller_speech_start_ms = now
            self._caller_speech_end_ms = None
            self._fire(EventType.CALLER_SPEECH_START.value, {}, source=EventSource.CALLER.value)
        else:
            self._caller_speech_end_ms = now
            self._fire(EventType.CALLER_SPEECH_END.value, {}, source=EventSource.CALLER.value)
        self._note_floor_events(self._floor.note_caller_playout(speaking, at_ms=now))

    # --------------------------------------------------------------- pumping

    async def _pump_agent_audio(self) -> None:
        try:
            async for chunk in self._link.incoming_audio():
                now = self._ms()
                self._last_activity_ms = now
                if self._first_audio_ms is None:
                    self._first_audio_ms = now
                self._recording.append_agent(chunk)
                speaking = self._energy_vad.update(chunk.data, now)
                self._note_target_activity("energy", speaking, now)
                if self._asr_queue is not None:
                    try:
                        self._asr_queue.put_nowait(chunk)
                    except asyncio.QueueFull:
                        # ASR is falling behind; drop audio rather than let lag
                        # grow invisibly (the watchdog below degrades to
                        # provider captions if this persists).
                        pass
        except asyncio.CancelledError:  # pragma: no cover - normal shutdown
            raise
        except Exception as exc:  # pragma: no cover - transport dependent
            logger.warning("agent audio pump stopped: %s", exc)
            self._conn_lost = self._conn_lost or f"audio pump: {exc}"

    async def _asr_pump(self, asr: Any) -> None:
        assert self._asr_queue is not None
        while True:
            chunk = await self._asr_queue.get()
            await asr.push(chunk)

    async def _asr_read(self, asr: Any, out_queue: asyncio.Queue) -> None:
        stream = asr.stream() if hasattr(asr, "stream") else _text_stream(asr)
        async for event in stream:
            now = self._ms()
            if event.kind == "speech_start":
                self._note_target_activity("asr", True, now)
                continue
            if event.kind == "speech_end":
                self._note_target_activity("asr", False, now)
                continue
            text = (event.text or "").strip()
            if not text:
                continue
            self._asr_text_ms = now
            logger.info("[dialog] TARGET(asr) %r", text[:300])
            out_queue.put_nowait(
                RawAgentEvent(
                    type=EventType.AGENT_TEXT_FINAL.value,
                    source=EventSource.INDEPENDENT_ASR.value,
                    monotonic_ms=now,
                    payload={"text": text},
                )
            )

    async def _asr_supervisor(self, out_queue: asyncio.Queue) -> None:
        """Keep the streaming ASR alive; degrade to provider captions if it dies."""
        for attempt, delay in enumerate((0.0, 1.0, 2.0)):
            if delay:
                await asyncio.sleep(delay)
            try:
                async with self._asr_factory() as asr:  # type: ignore[misc]
                    await asyncio.gather(self._asr_pump(asr), self._asr_read(asr, out_queue))
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # provider dependent
                logger.warning("live ASR failed (attempt %d): %s", attempt + 1, exc)
                continue
            return
        self._asr_active = False
        logger.warning("live ASR unavailable; falling back to provider captions")

    # ------------------------------------------------------------ turn logic

    def _accept_text(self, text: str, now: int) -> bool:
        """Whether an incoming transcript is a new trigger, not stale history.

        The repetition bug this guards against is a *re-delivery* of the
        utterance we just answered, so the drop test is textual similarity to
        the answered text — not timing. Genuinely new content that arrives
        while a reply is being planned is accepted and folds into a fresh
        decision (see ``_collect_decision``).
        """
        if not text:
            return False
        if self._pending and text == self._pending[-1]:
            return False
        if self._busy_since_ms is None:
            return True
        answered = self._busy_text_answered or ""
        if answered and _similarity(text, answered) >= 0.6:
            logger.info("[dialog] DROP stale segment %r", text[:80])
            return False
        if not self._playout_speaking() and self._reply_in_flight():
            # Still planning: accept, and _collect_decision folds it into a
            # fresh decision instead of speaking the stale one.
            return True
        edge = self._activity.last_start_ms or 0
        if self._activity.active or edge > self._busy_since_ms:
            return True
        if self._reply_in_flight():
            # We are mid-speech with no evidence the target is talking: a
            # dissimilar-but-late segment of the answered utterance.
            logger.info("[dialog] DROP late segment %r", text[:80])
            return False
        return True

    def _playout_speaking(self) -> bool:
        return bool(self._playout and self._playout.speaking)

    def _reply_in_flight(self) -> bool:
        if self._decide_task is not None or self._speak_task is not None:
            return True
        if self._playout_speaking():
            return True
        # Stay "busy" for the stale window after speech ends.
        if self._busy_since_ms is not None and self._caller_speech_end_ms is not None:
            return self._ms() - self._caller_speech_end_ms <= _STALE_WINDOW_MS
        return False

    def _turn_complete(self, now: int) -> bool:
        """End-of-turn: the target is quiet, mid-thought pauses respected."""
        if not self._pending:
            return False
        pending_idle_ms = now - self._last_pending_ms
        if self._activity.active:
            # They are audibly still talking; a gap between ASR segments is
            # not a turn end. Only a long text silence forces an answer.
            return pending_idle_ms >= 4_500
        if (
            _ends_in_preamble(" ".join(self._pending))
            and pending_idle_ms < int(self._turn_silence_ms * 1.5)
        ):
            # "Okay, so…", "Brother, listen." — wait for the actual content.
            return False
        quiet_ms = now - (self._activity.last_end_ms or self._started_ms)
        return (
            quiet_ms >= self._eot_grace_ms and pending_idle_ms >= self._asr_lag_ms
        ) or pending_idle_ms >= self._turn_silence_ms

    def _begin_reply(self, *, barge_in: bool = False) -> None:
        now = self._ms()
        segments = self._pending
        self._pending = []
        assertions = self._assertions
        self._assertions = []
        self._reply_segments = segments
        self._reply_assertions = assertions
        self._busy_since_ms = now
        self._busy_text_answered = " ".join(segments).strip()
        silence_ms = (
            now - self._activity.last_end_ms if self._activity.last_end_ms else 0
        )
        text = self._busy_text_answered
        logger.info(
            "[dialog] DECIDE barge=%s pending=%r silence=%dms",
            barge_in,
            text[:120],
            silence_ms,
        )
        self._decide_task = asyncio.create_task(
            self._pipeline.decide(
                text,
                previous_text=self._prev_agent_text,
                assertions=assertions,
                silence_ms=silence_ms,
            )
        )

    async def _collect_decision(self, now: int) -> str | None:
        """Handle a finished decide task. Returns a terminal reason or None."""
        task = self._decide_task
        assert task is not None
        self._decide_task = None
        try:
            step = task.result()
        except Exception:
            logger.exception("decision pipeline failed; dropping reply")
            self._pending = self._reply_segments + self._pending
            self._busy_since_ms = None
            return None

        target_resumed = (
            (self._activity.last_start_ms or 0) > (self._busy_since_ms or 0)
            or bool(self._pending)
        )
        if target_resumed and not self._playout_speaking():
            # The target only paused: fold the text back and keep listening.
            logger.info("[dialog] reply superseded — target resumed speaking")
            self._pending = self._reply_segments + self._pending
            self._last_pending_ms = now
            self._busy_since_ms = None
            return None

        self._prev_agent_text = self._busy_text_answered or self._prev_agent_text
        self._turns += 1
        logger.info(
            "[dialog] CALLER >> action=%s lang=%s terminal=%s text=%r",
            step.action,
            step.language,
            step.terminal,
            (step.text or "")[:300],
        )
        self._fire(
            EventType.DECISION_RECORDED.value,
            {"turn": self._turns, **(step.record or {})},
            source=EventSource.CALLER.value,
        )
        self._abort_speech = False
        self._current_step = step
        self._speak_task = asyncio.create_task(self._speak_step(step))
        return None

    async def _speak_step(self, step: Decision) -> None:
        if not step.text:
            return
        rng = getattr(self._pipeline, "_rng", None)
        # Human think-time before answering, absorbed by whatever the decision
        # already took: the *total* gap from end-of-turn to audio is what a
        # human hears, so we never stack a fixed delay on top of LLM latency.
        delay = (
            rng.uniform("response_latency", 0.2, 0.7)
            if rng is not None
            else 0.35
        )
        elapsed_s = (self._ms() - (self._busy_since_ms or self._ms())) / 1000
        await asyncio.sleep(max(0.0, delay - elapsed_s))
        request = SynthesisRequest(
            text=step.text,
            language=step.language,
            sample_rate=self._recording.sample_rate,
        )
        for attempt in (1, 2):
            try:
                async for chunk in self._tts.synthesize(request):
                    if self._abort_speech:
                        return
                    if self._playout is not None:
                        self._playout.enqueue(chunk)
                break
            except Exception as exc:  # noqa: BLE001 - fallback then classify
                logger.warning("TTS failed (attempt %d): %s", attempt, exc)
                self._fire(
                    EventType.CALLER_TTS_ERROR.value,
                    {"provider": getattr(self._tts, "name", "tts"), "error": str(exc)[:200]},
                    source=EventSource.CALLER.value,
                )
        else:
            self._tts_failed = True
            return
        try:
            await self._link.send_control(
                {"type": "caller.turn.end", "turn_id": f"turn-{self._turns}"}
            )
        except Exception:  # pragma: no cover - best effort
            pass

    async def _collect_speech(self, now: int) -> str | None:
        """Handle a finished speak task; terminal steps end the call."""
        task = self._speak_task
        assert task is not None
        self._speak_task = None
        try:
            task.result()
        except Exception:
            logger.exception("speech task failed")
            self._tts_failed = True
            return None
        step, self._current_step = self._current_step, None
        if step is not None and step.terminal:
            self.terminal_reason = step.terminal_reason or "NATURAL_SUCCESS"
        elif step is not None and self._turns >= self._max_agent_turns:
            self.terminal_reason = "MAX_TURNS"
        return None

    def _maybe_yield(self, now: int) -> None:
        """The target is talking over us: decide whether to stop speaking."""
        if not self._playout_speaking():
            self._false_interruption_flagged = False
            return
        if not self._activity.active:
            self._false_interruption_flagged = False
            return
        planner = self._pipeline.interruption
        caller_start = self._caller_speech_start_ms or now
        utterance_age_ms = now - caller_start
        if utterance_age_ms < planner.hold_floor_initial_ms():
            return
        overlap_ms = now - max(self._activity.last_start_ms or now, caller_start)
        new_words = sum(len(part.split()) for part in self._pending)
        if planner.is_false_interruption(
            target_speech_ms=overlap_ms, target_words=new_words
        ):
            if not self._false_interruption_flagged:
                self._false_interruption_flagged = True
                self._fire(
                    EventType.CALLER_FALSE_INTERRUPTION.value,
                    {"overlap_ms": overlap_ms},
                    source=EventSource.CALLER.value,
                )
            return
        if planner.should_yield(
            target_speech_ms=overlap_ms, target_words=max(1, new_words)
        ):
            logger.info("[dialog] CALLER yields (target barge-in, %d ms)", overlap_ms)
            self._fire(
                EventType.TURN_INTERRUPTED.value,
                {"by": "target", "overlap_ms": overlap_ms},
                source=EventSource.DERIVED.value,
            )
            self._abort_speech = True
            if self._playout is not None:
                self._playout.interrupt()

    def _maybe_barge_in(self, now: int) -> None:
        """The caller cuts into a monologuing or repeating target."""
        if self._reply_in_flight() or not self._activity.active:
            return
        if now < self._barge_cooldown_until_ms:
            return
        turn_start = self._activity.last_start_ms
        if turn_start is None:
            return
        text = " ".join(self._pending)
        reading = self._turn_analyzer.analyze(
            text, previous_text=self._prev_agent_text
        ) if text else None
        question_complete = text.rstrip().endswith("?")
        decision = self._pipeline.decide_barge_in(
            target_turn_ms=now - turn_start,
            target_words=self._floor.turn.words,
            question_complete=question_complete,
            end_of_turn_probability=0.8 if question_complete else 0.0,
            repeated=bool(reading and reading.is_repeat),
        )
        if not decision.attempt:
            return
        logger.info("[dialog] CALLER barge-in: %s", decision.reason)
        self._barge_cooldown_until_ms = now + 4_000
        self._fire(
            EventType.BARGE_IN_ATTEMPTED.value,
            {"trigger": decision.trigger, "mode": decision.mode.value},
            source=EventSource.CALLER.value,
        )
        self._begin_reply(barge_in=True)
        self._fire(EventType.BARGE_IN_SUCCEEDED.value, {}, source=EventSource.CALLER.value)

    def _idle_ms(self, now: int) -> int:
        """Silence duration for initiative: speech edges, text and events count
        as activity; raw audio (often a continuous silence stream) does not."""
        anchors = [self._started_ms, self._last_signal_ms, self._probe_last_ms]
        if self._caller_speech_end_ms:
            anchors.append(self._caller_speech_end_ms)
        return now - max(anchors)

    def _maybe_take_initiative(self, now: int) -> None:
        """Silence is the caller's problem too: open, probe, or give up."""
        if self._reply_in_flight() or self._pending or self._activity.active:
            return
        idle_ms = self._idle_ms(now)

        if (
            not self._opened
            and not self._target_ever_spoke
            and not self._link.capabilities().target_speaks_first
            and idle_ms >= 800
        ):
            self._opened = True
            logger.info("[dialog] CALLER opens (target does not speak first)")
            self._begin_reply()
            return

        if self._probe_count < len(_PROBE_AT_IDLE_MS):
            if idle_ms >= _PROBE_AT_IDLE_MS[self._probe_count]:
                self._probe_count += 1
                self._probe_last_ms = now
                logger.info("[dialog] CALLER probe #%d after %d ms idle", self._probe_count, idle_ms)
                self._busy_since_ms = now
                self._speak_task = asyncio.create_task(self._speak_probe())
            return
        if idle_ms >= _PROBE_GIVE_UP_MS:
            reason = (
                "TARGET_SILENT" if self._turns == 0 else "CONVERSATION_STALL"
            )
            logger.info("[dialog] call ends: %s after %d ms idle", reason, idle_ms)
            self.terminal_reason = reason

    async def _speak_probe(self) -> None:
        step = await self._pipeline.realize_probe(self._probe_count)
        logger.info("[dialog] CALLER >> probe text=%r", (step.text or "")[:300])
        await self._speak_step(step)

    # ------------------------------------------------------------ supervision

    def _check_supervision(self, now: int) -> str | None:
        if self.terminal_reason:
            return self.terminal_reason
        if self._playout is not None and self._playout.failed is not None:
            return "TARGET_HUNG_UP"
        if self._tts_failed:
            return "TTS_FAILURE"
        if self._conn_lost is not None:
            return "TARGET_HUNG_UP"
        if (
            self._first_audio_ms is None
            and now - self._started_ms >= self._first_audio_timeout_ms
        ):
            return "TARGET_SILENT"
        if now - self._started_ms >= self._wall_clock_ms:
            return "WALL_CLOCK_TIMEOUT"
        if now - self._last_activity_ms >= self._stall_backstop_ms:
            return "CONVERSATION_STALL"
        return None

    def _asr_watchdog(self, now: int) -> None:
        """Detect 'target is talking but the ASR has gone blind'."""
        if not self._asr_active or not self._activity.active:
            return
        start = self._activity.last_start_ms or now
        if now - start < 8_000 or now - self._asr_text_ms < 4_000:
            return
        if self._asr_strike_anchor_ms != start:
            self._asr_strike_anchor_ms = start
            self._asr_strikes += 1
            logger.warning(
                "ASR produced no text for %d ms of target speech (strike %d)",
                now - start,
                self._asr_strikes,
            )
            if self._asr_strikes >= 3:
                self._asr_active = False
                logger.warning("ASR unreliable; falling back to provider captions")

    # ------------------------------------------------------------ main loop

    def _handle_turn_text(self, text: str, extra: Any, now: int) -> None:
        accepted = self._accept_text(text, now)
        logger.info(
            "[dialog] TARGET << %r%s",
            text[:300],
            "" if accepted else " (stale-dropped)",
        )
        if not accepted:
            return
        self._pending.append(text)
        self._last_pending_ms = now
        self._last_activity_ms = now
        self._last_signal_ms = now
        self._probe_count = 0
        self._floor.note_target_transcript(text, is_final=True)
        if isinstance(extra, list):
            self._assertions.extend(str(item) for item in extra)

    async def _handle_raw(self, raw: RawAgentEvent, now: int) -> None:
        canonical = self._builder.build(
            raw.type,
            source=raw.source
            if raw.source in {s.value for s in EventSource}
            else EventSource.PROVIDER_NORMALIZED.value,
            payload=raw.payload,
            monotonic_ms=raw.monotonic_ms or now,
            media_timestamp=raw.media_timestamp,
            turn_id=raw.turn_id,
            provider_event_id=raw.provider_event_id,
        )
        self._fire(canonical.type, canonical.payload or {}, source=canonical.source)

        ctype = canonical.type
        if ctype == EventType.CONNECTION_CLOSED.value or ctype == EventType.CONNECTION_CLOSED:
            self._conn_lost = str((canonical.payload or {}).get("reason") or "closed")
            return
        if ctype in (
            EventType.AGENT_SPEECH_START.value,
            EventType.TARGET_SPEECH_START.value,
            EventType.AGENT_SPEECH_START,
            EventType.TARGET_SPEECH_START,
        ):
            self._note_target_activity("provider", True, now)
            return
        if ctype in (
            EventType.AGENT_SPEECH_END.value,
            EventType.TARGET_SPEECH_END.value,
            EventType.AGENT_SPEECH_END,
            EventType.TARGET_SPEECH_END,
        ):
            self._note_target_activity("provider", False, now)
            return
        if ctype in (
            EventType.TARGET_TRANSCRIPT_FINAL.value,
            EventType.TARGET_TRANSCRIPT_FINAL,
        ) and self._asr_active:
            # The provider's own caption: provenance only, never the trigger.
            logger.info(
                "[dialog] TARGET(provider) %r",
                str((canonical.payload or {}).get("text") or "")[:300],
            )
            return
        if self._is_turn_event(ctype, canonical.source):
            text = str((canonical.payload or {}).get("text") or "").strip()
            self._handle_turn_text(text, (canonical.payload or {}).get("assertions"), now)

    def _is_turn_event(self, ctype: Any, source: Any) -> bool:
        """Whether an event is the caller's decision trigger.

        With our own ASR active, only the ASR transcription of the target's
        audio counts; the provider's caption is provenance. Otherwise fall back
        to the provider transcript.
        """
        value = ctype.value if isinstance(ctype, EventType) else ctype
        source_value = source.value if isinstance(source, EventSource) else source
        if value == EventType.AGENT_TEXT_FINAL.value:
            if self._asr_active:
                return source_value == EventSource.INDEPENDENT_ASR.value
            return True
        if value == EventType.TARGET_TRANSCRIPT_FINAL.value:
            return not self._asr_active
        return False

    async def _finish(self, reason: str) -> str:
        """Speak the goodbye fully, keep listening for the tail, then hang up."""
        self._lifecycle_fail_safe(ConnectionState.CLOSING)
        if self._speak_task is not None:
            try:
                await self._speak_task
            except Exception:  # pragma: no cover
                pass
        if self._playout is not None:
            await self._playout.wait_idle()
        if reason not in ("TARGET_HUNG_UP", "TRANSPORT_LOST", "TTS_FAILURE"):
            # The target's reply to our goodbye matters to the judges; keep
            # recording (and sending silence) for a short tail.
            await asyncio.sleep(self._tail_s)
        self._lifecycle_fail_safe(ConnectionState.ENDED)
        return reason

    def _lifecycle_fail_safe(self, state: ConnectionState) -> None:
        try:
            if self._lifecycle.can_transition(state):
                self._lifecycle.transition(state)
        except Exception:  # pragma: no cover - bookkeeping must not break a call
            pass

    async def run(self) -> str | None:
        """Run until the caller or the supervisor ends the call."""
        self._started_ms = self._ms()
        self._last_activity_ms = self._started_ms
        self._asr_text_ms = self._started_ms
        for state in (
            ConnectionState.DISPATCHED,
            ConnectionState.REGISTERED,
            ConnectionState.CONNECTING,
            ConnectionState.ANSWERED,
        ):
            self._lifecycle_fail_safe(state)

        self._playout = _Playout(
            link=self._link,
            recording=self._recording,
            sample_rate=self._recording.sample_rate,
            clock=self._clock,
            on_speaking_change=self._on_caller_speaking_change,
        )
        playout_task = asyncio.create_task(self._playout.run())
        self._agent_audio_task = asyncio.create_task(self._pump_agent_audio())
        drain_task = asyncio.create_task(self._emit_drainer())
        queue: asyncio.Queue = asyncio.Queue()

        # Pre-open the persistent TTS socket so the first turn pays no connect.
        tts_open = getattr(self._tts, "open", None)
        tts_task = (
            asyncio.create_task(tts_open()) if callable(tts_open) else None
        )

        async def _reader() -> None:
            try:
                async for raw in self._link.events():
                    now = self._ms()
                    self._last_activity_ms = now
                    self._last_signal_ms = now
                    if not raw.monotonic_ms:
                        raw = dataclasses.replace(raw, monotonic_ms=now)
                    queue.put_nowait(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # transport dependent
                queue.put_nowait(
                    RawAgentEvent(
                        type=EventType.CONNECTION_CLOSED.value,
                        source=EventSource.RUNTIME.value,
                        monotonic_ms=self._ms(),
                        payload={"reason": f"error: {exc}"},
                    )
                )
            else:
                queue.put_nowait(
                    RawAgentEvent(
                        type=EventType.CONNECTION_CLOSED.value,
                        source=EventSource.RUNTIME.value,
                        monotonic_ms=self._ms(),
                        payload={"reason": "event_stream_ended"},
                    )
                )

        reader = asyncio.create_task(_reader())
        asr_task: asyncio.Task | None = None
        if self._asr_active:
            self._asr_queue = asyncio.Queue(maxsize=2000)
            asr_task = asyncio.create_task(self._asr_supervisor(queue))
        self._lifecycle_fail_safe(ConnectionState.CONVERSING)

        tasks = [playout_task, self._agent_audio_task, drain_task, reader, asr_task, tts_task]
        try:
            while True:
                now = self._ms()
                reason = self._check_supervision(now)
                if reason is not None:
                    return await self._finish(reason)

                if self._decide_task is not None and self._decide_task.done():
                    await self._collect_decision(now)
                if self._speak_task is not None and self._speak_task.done():
                    await self._collect_speech(now)

                try:
                    raw = await asyncio.wait_for(queue.get(), timeout=_TICK_S)
                except asyncio.TimeoutError:
                    raw = None
                if raw is not None:
                    await self._handle_raw(raw, now)

                now = self._ms()
                self._asr_watchdog(now)
                self._maybe_yield(now)

                if self._reply_in_flight():
                    continue
                if self._turn_complete(now):
                    self._begin_reply()
                    continue
                self._maybe_barge_in(now)
                if self._decide_task is None and self._speak_task is None:
                    self._maybe_take_initiative(now)
        finally:
            if self._playout is not None:
                self._playout.close()
            for task in tasks:
                if task is not None:
                    task.cancel()
            for task in tasks:
                if task is None:
                    continue
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # pragma: no cover
                    pass
            tts_close = getattr(self._tts, "aclose", None)
            if callable(tts_close):
                try:
                    await tts_close()
                except Exception:  # pragma: no cover - best-effort teardown
                    pass

    async def emit_terminal(self, reason: str) -> None:
        """Emit the terminal event with a classified status/eligibility payload."""
        await self._flush_emits()
        await self._emit(
            self._builder.build(
                EventType.ATTEMPT_TERMINAL,
                source=EventSource.RUNTIME.value,
                payload=terminal_payload(reason),
            )
        )


__all__ = ["LinkConversationRunner"]
