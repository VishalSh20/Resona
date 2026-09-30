"""CallRunner tests: deterministic end-to-end run, materialization, stop paths.

The fake target server gives the runtime a real websocket endpoint, so these
tests exercise the actual transport, framing, decoding, caller loop, stop
conditions and telemetry — with no third-party provider or database.
"""

from __future__ import annotations

import socket

import pytest

from voiceeval.db.models import runtime as runtime_models
from voiceeval.realtime.materializer import EventMaterializer
from voiceeval.realtime.protocol import RuntimeEventEnvelope
from voiceeval.runtime.adapters import (
    FakeTargetAdapter,
    FakeTargetServer,
    FakeScript,
    agent_turn,
    tool_turn,
)
from voiceeval.runtime.events import EventType
from voiceeval.runtime.runner import CallRunner
from voiceeval.runtime.stop_conditions import StopConditionEngine
from voiceeval.runtime.telemetry import (
    RecordingTelemetrySink,
    build_stream_url,
)


class _Result:
    def scalar_one(self):
        return 0

    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []


class NullSession:
    """Captures materialized objects without a database."""

    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def get(self, model, id_):
        return None

    async def execute(self, stmt):
        return _Result()


async def _run(script=None, *, endpoint=None, stall_ms=10_000, sink=None, scenario=None):
    server = await FakeTargetServer(script).start() if endpoint is None else None
    try:
        sink = sink or RecordingTelemetrySink(
            attempt_id="att_1", runner_id="runner-1", runner_version="runner.v1"
        )
        engine = StopConditionEngine(
            stall_ms=stall_ms,
            wall_clock_timeout_ms=5_000,
            max_wall_clock_timeout_ms=5_000,
        )
        runner = CallRunner(
            attempt_id="att_1",
            adapter=FakeTargetAdapter(),
            endpoint_config={"url": endpoint or server.url},
            scenario=scenario,
            telemetry=sink,
            stop_engine=engine,
        )
        outcome = await runner.run()
        return outcome, sink
    finally:
        if server is not None:
            await server.stop()


def _closed_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


# --- end to end --------------------------------------------------------------


async def test_end_to_end_fake_call_reaches_natural_success(scenario):
    outcome, sink = await _run(scenario=scenario)

    assert outcome.stop_reason == "NATURAL_SUCCESS"
    assert outcome.terminal_status == "completed"
    assert outcome.eligible is True
    assert outcome.audio_bytes_sent > 0
    assert outcome.media and outcome.media[0].sha256

    types = [e.type for e in sink.events]
    for required in (
        EventType.CONNECTION_READY.value,
        EventType.CALLER_STATE_INITIALIZED.value,
        EventType.CALLER_ACTION_SELECTED.value,
        EventType.CALLER_UTTERANCE_REALIZED.value,
        EventType.AGENT_TEXT_FINAL.value,
        EventType.TOOL_CALL_START.value,
        EventType.TOOL_CALL_RESULT.value,
        EventType.TURN_START.value,
        EventType.TURN_END.value,
        EventType.CALLER_TERMINAL.value,
        EventType.ATTEMPT_TERMINAL.value,
    ):
        assert required in types, required

    # Sequences are strictly increasing and unique within the attempt.
    sequences = [e.sequence for e in sink.events]
    assert sequences == sorted(set(sequences))
    assert all(e.call_attempt_id == "att_1" for e in sink.events)


async def test_recorded_events_materialize_turns_tools_and_state(scenario):
    _outcome, sink = await _run(scenario=scenario)

    session = NullSession()
    materializer = EventMaterializer(session)
    for event in sink.events:
        await materializer.materialize(RuntimeEventEnvelope(**event.to_envelope()))

    turns = [o for o in session.added if isinstance(o, runtime_models.CallTurn)]
    tools = [o for o in session.added if isinstance(o, runtime_models.ToolCall)]
    transitions = [o for o in session.added if isinstance(o, runtime_models.StateTransition)]

    assert turns and any(t.speaker == "caller" for t in turns)
    assert any(t.speaker == "agent" for t in turns)
    assert tools and tools[0].tool_name == "verify_identity"
    assert transitions and any(t.state_path for t in transitions)


async def test_terminal_event_reports_the_stop_reason(scenario):
    _outcome, sink = await _run(scenario=scenario)
    terminal = [e for e in sink.events if e.type == EventType.ATTEMPT_TERMINAL.value]
    assert len(terminal) == 1
    assert terminal[0].payload["reason"] == "NATURAL_SUCCESS"
    assert terminal[0].payload["eligible"] is True


# --- stop paths --------------------------------------------------------------


async def test_recovery_exhaustion_is_a_semantic_outcome(scenario):
    script = FakeScript(
        greeting=agent_turn("t0", text="Hello"),
        batches=[
            tool_turn("t1", "verify_identity", {"m": 1}),
            agent_turn("t2", text="Hmm"),
            agent_turn("t3", text="Still here"),
            agent_turn("t4", text="Still nothing"),
        ],
    )
    outcome, _ = await _run(script, scenario=scenario)
    assert outcome.stop_reason == "RECOVERY_EXHAUSTED"
    assert outcome.terminal_status == "failed"
    assert outcome.failure_class is None
    assert outcome.eligible is True


async def test_connection_failure_is_retryable_transport(scenario):
    outcome, _ = await _run(endpoint=f"ws://127.0.0.1:{_closed_port()}/target", scenario=scenario)
    assert outcome.stop_reason == "CONNECTION_FAILURE"
    assert outcome.failure_class == "transport"


async def test_silent_target_times_out_as_stall(scenario):
    script = FakeScript(greeting=agent_turn("t0", text="Hello"), batches=[])
    outcome, _ = await _run(script, stall_ms=150, scenario=scenario)
    assert outcome.stop_reason == "CONVERSATION_STALL"
    assert outcome.terminal_status == "timed_out"
    assert outcome.failure_class == "timeout"


async def test_control_cancel_terminates_the_attempt(scenario):
    sink = RecordingTelemetrySink(
        attempt_id="att_1", runner_id="runner-1", runner_version="runner.v1"
    )
    await sink.push_control({"type": "attempt.cancel", "reason": "USER_REQUESTED"})
    outcome, _ = await _run(scenario=scenario, sink=sink)
    assert outcome.stop_reason == "CANCELLED"
    assert outcome.terminal_status == "cancelled"
    assert outcome.failure_class == "cancelled"


# --- telemetry ---------------------------------------------------------------


def test_build_stream_url_converts_scheme_and_binds_attempt():
    url = build_stream_url("http://backend:8000/", "att_9", "tok en")
    assert url == "ws://backend:8000/internal/v1/attempts/att_9/stream?token=tok%20en"
    assert build_stream_url("https://h", "att_1", "t").startswith("wss://h")


async def test_envelope_is_accepted_by_the_runner_protocol(scenario):
    _outcome, sink = await _run(scenario=scenario)
    envelope = RuntimeEventEnvelope(**sink.events[-1].to_envelope())
    assert envelope.call_attempt_id == "att_1"
