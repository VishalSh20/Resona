"""Behavioural tests for the link-boundary conversation loop.

The runner is exercised end to end against a fake link (silence in, events in,
audio out) with the real decision pipeline, to lock in the turn-taking
contract: answer on end-of-turn, never twice for the same utterance, hang-up
handling, and a continuous paced playout stream.
"""

from __future__ import annotations

import asyncio

from voiceeval.runtime.caller.persona import PersonaResolver
from voiceeval.runtime.caller.pipeline import CallerDecisionPipeline
from voiceeval.runtime.connections import AudioChunk, RawAgentEvent
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.livekit.conversation import LinkConversationRunner
from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.livekit.target_links.base import TargetLinkCapabilities

_FRAME = b"\x00" * 640  # 20 ms of 16 kHz pcm_s16le silence


class _FakeTTS:
    name = "fake_tts"

    def __init__(self) -> None:
        self.requests = []

    async def synthesize(self, request):
        self.requests.append(request)
        for _ in range(3):
            yield AudioChunk(data=b"\x01\x02" * 320, sample_rate=request.sample_rate)


class _FakeLink:
    def __init__(self, *, target_speaks_first: bool = True) -> None:
        self.sent: list[AudioChunk] = []
        self._events: asyncio.Queue = asyncio.Queue()
        self._closed = False
        self._speaking = False
        self._target_speaks_first = target_speaks_first

    def capabilities(self) -> TargetLinkCapabilities:
        return TargetLinkCapabilities(
            codec="pcm_s16le",
            sample_rate=16_000,
            target_speaks_first=self._target_speaks_first,
        )

    async def incoming_audio(self):
        while not self._closed:
            await asyncio.sleep(0.02)
            frame = b"\x40\x40" * 320 if self._speaking else _FRAME
            yield AudioChunk(data=frame, sample_rate=16_000)

    async def send_audio(self, frame: AudioChunk) -> None:
        self.sent.append(frame)

    def events(self):
        async def _gen():
            while not self._closed:
                try:
                    yield await asyncio.wait_for(self._events.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue

        return _gen()

    async def send_control(self, message) -> None:
        pass

    async def close(self, reason) -> None:
        self._closed = True

    def push_event(self, type_: str, payload: dict) -> None:
        self._events.put_nowait(
            RawAgentEvent(
                type=type_,
                source=EventSource.PROVIDER_NORMALIZED.value,
                monotonic_ms=0,
                payload=payload,
            )
        )

    async def say(self, text: str, **extra) -> None:
        """Simulate a target utterance: audible speech, then the transcript."""
        self._speaking = True
        await asyncio.sleep(0.3)
        self.push_event("target.transcript.final", {"text": text, **extra})
        await asyncio.sleep(0.1)
        self._speaking = False


def _runner(link: _FakeLink, tts: _FakeTTS, scenario, emitted: list):
    pipeline = CallerDecisionPipeline(scenario, PersonaResolver().resolve([]))
    return LinkConversationRunner(
        attempt_id="att_test",
        link=link,
        pipeline=pipeline,
        builder=CanonicalEventBuilder("att_test"),
        recording=AttemptRecording(sample_rate=16_000),
        tts=tts,
        emit=lambda event: emitted.append(event) or asyncio.sleep(0),
        turn_silence_s=0.6,
        end_of_turn_grace_s=0.1,
        asr_lag_grace_s=0.1,
        tail_s=0.05,
    )


async def _wait_for(predicate, timeout: float = 8.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("timed out waiting for condition")
        await asyncio.sleep(0.02)


async def test_happy_path_ends_natural_success(scenario):
    link, tts, emitted = _FakeLink(), _FakeTTS(), []
    runner = _runner(link, tts, scenario, emitted)
    task = asyncio.create_task(runner.run())
    try:
        await asyncio.sleep(0.2)
        await link.say("Hi, how can I help?")
        await _wait_for(lambda: len(tts.requests) == 1)

        satisfied = ["authentication_complete", "objective_fulfilled"]
        await link.say("All done!", assertions=satisfied)
        await _wait_for(lambda: len(tts.requests) == 2)

        await link.say("You're welcome.", assertions=satisfied)
        reason = await asyncio.wait_for(task, timeout=8.0)
    finally:
        if not task.done():
            task.cancel()
    assert reason == "NATURAL_SUCCESS"
    # A continuous stream went out: far more frames than the TTS bursts alone.
    assert len(link.sent) > 40
    assert runner.terminal_reason == "NATURAL_SUCCESS"


async def test_stale_duplicate_does_not_retrigger_reply(scenario):
    link, tts, emitted = _FakeLink(), _FakeTTS(), []
    runner = _runner(link, tts, scenario, emitted)
    task = asyncio.create_task(runner.run())
    try:
        await asyncio.sleep(0.2)
        await link.say("What is your account id?")
        await _wait_for(lambda: len(tts.requests) == 1)
        # A late re-delivery of the exact utterance we just answered is history,
        # not a new turn.
        link.push_event(
            "target.transcript.final", {"text": "What is your account id?"}
        )
        await asyncio.sleep(1.5)
        assert len(tts.requests) == 1
    finally:
        task.cancel()


async def test_target_hangup_terminates_call(scenario):
    link, tts, emitted = _FakeLink(), _FakeTTS(), []
    runner = _runner(link, tts, scenario, emitted)
    task = asyncio.create_task(runner.run())
    await asyncio.sleep(0.2)
    link.push_event("connection.closed", {})
    reason = await asyncio.wait_for(task, timeout=5.0)
    assert reason == "TARGET_HUNG_UP"


async def test_caller_opens_when_target_does_not_speak_first(scenario):
    link, tts, emitted = _FakeLink(target_speaks_first=False), _FakeTTS(), []
    runner = _runner(link, tts, scenario, emitted)
    task = asyncio.create_task(runner.run())
    try:
        await _wait_for(lambda: len(tts.requests) == 1, timeout=5.0)
    finally:
        task.cancel()
