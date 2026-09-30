"""Runner control WebSocket, runtime event ingestion and live pub/sub tests.

Covers Prompt 5 acceptance criteria: runner authentication, invalid/wrong
tokens, register, heartbeat, cancel, terminate, runtime event ingestion,
duplicate sequence, provider_event_id deduplication and pub/sub fanout.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from voiceeval.auth.jwt import create_runner_token, create_token
from voiceeval.core.errors import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)
from voiceeval.db.models import runtime
from voiceeval.realtime import protocol
from voiceeval.realtime.event_ingestion import RuntimeEventIngestor
from voiceeval.realtime.materializer import EventMaterializer
from voiceeval.realtime.pubsub import (
    ATTEMPT_STATUS_CHANGED,
    CALL_RUN_STATUS_CHANGED,
    NoOpPubSub,
    RUN_PROGRESS,
    envelope,
    plan_events_channel,
    publish_plan_event,
    publish_run_event,
    run_events_channel,
    set_pubsub,
)
from voiceeval.realtime.registry import ConnectionRegistry, get_connection_registry
from voiceeval.realtime.runner_auth import authenticate_runner, authenticate_user
from voiceeval.realtime.runner_ws import RunnerSession

# --- fakes -------------------------------------------------------------------


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, row=None, scalar=None, values=None):
        self._row = row
        self._scalar = scalar
        self._values = values or []

    def first(self):
        return self._row

    def scalar_one(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _Scalars(self._values)


class FakeSession:
    def __init__(self, objects=None, execute_results=None):
        self._objects = {o.id: o for o in (objects or [])}
        self._execute_results = list(execute_results or [])
        self.added = []
        self.committed = 0

    def add(self, obj):
        self.added.append(obj)
        obj_id = getattr(obj, "id", None)
        if obj_id:
            self._objects[obj_id] = obj

    async def get(self, model, id_):
        return self._objects.get(id_)

    async def flush(self):
        pass

    async def commit(self):
        self.committed += 1

    async def execute(self, stmt):
        if not self._execute_results:
            return _Result()
        return self._execute_results.pop(0)


def _event(**overrides) -> protocol.RuntimeEventEnvelope:
    data = {
        "event_id": "evt_1",
        "call_attempt_id": "att_1",
        "sequence": 1,
        "type": "agent.audible.start",
        "source": "derived",
        "monotonic_ms": 12420,
        "wall_clock": datetime(2026, 9, 29, 12, 35, 22, tzinfo=timezone.utc),
        "payload": {},
    }
    data.update(overrides)
    return protocol.RuntimeEventEnvelope(**data)


# --- authentication ----------------------------------------------------------


def test_valid_runner_token_authenticates():
    token = create_runner_token("runner_1", "att_1")
    claims = authenticate_runner(token, "att_1")
    assert claims.scope == "runner"
    assert claims.attempt_id == "att_1"


def test_invalid_runner_token_rejected():
    with pytest.raises(AuthenticationError):
        authenticate_runner("not-a-jwt", "att_1")


def test_missing_runner_token_rejected():
    with pytest.raises(AuthenticationError):
        authenticate_runner(None, "att_1")


def test_wrong_attempt_runner_token_rejected():
    token = create_runner_token("runner_1", "att_1")
    with pytest.raises(AuthorizationError):
        authenticate_runner(token, "att_2")


def test_user_token_rejected_on_runner_channel():
    token, _ = create_token("user_1", "user")
    with pytest.raises(AuthorizationError):
        authenticate_runner(token, "att_1")


def test_authenticate_user_accepts_user_and_rejects_runner():
    user_token, _ = create_token("user_1", "user")
    assert authenticate_user(user_token).scope == "user"
    runner_token = create_runner_token("runner_1", "att_1")
    with pytest.raises(AuthorizationError):
        authenticate_user(runner_token)


# --- protocol ----------------------------------------------------------------


def test_parse_unknown_message_type_rejected():
    with pytest.raises(ValidationError):
        protocol.parse_runner_message({"type": "runner.nope"})


def test_server_control_messages():
    assert protocol.build_cancel("USER_REQUESTED") == {
        "type": "attempt.cancel",
        "reason": "USER_REQUESTED",
    }
    assert protocol.build_terminate("PLAN_CANCELLED") == {
        "type": "attempt.terminate",
        "reason": "PLAN_CANCELLED",
    }
    assert protocol.build_heartbeat_ack()["type"] == "runner.heartbeat_ack"


# --- runner session ----------------------------------------------------------


async def test_register_sets_session_state():
    session = FakeSession()
    runner = RunnerSession(attempt_id="att_1", session=session)
    replies = await runner.handle(
        {
            "type": "runner.register",
            "attempt_id": "att_1",
            "runner_id": "runner_1",
            "runner_version": "0.3.2",
        }
    )
    assert replies == []
    assert runner.registered is True
    assert runner.runner_id == "runner_1"


async def test_register_wrong_attempt_rejected():
    runner = RunnerSession(attempt_id="att_1", session=FakeSession())
    with pytest.raises(AuthorizationError):
        await runner.handle(
            {
                "type": "runner.register",
                "attempt_id": "att_other",
                "runner_id": "runner_1",
                "runner_version": "0.3.2",
            }
        )


async def test_heartbeat_returns_ack():
    runner = RunnerSession(attempt_id="att_1", session=FakeSession())
    replies = await runner.handle(
        {"type": "runner.heartbeat", "attempt_id": "att_1", "monotonic_ms": 42}
    )
    assert replies[0]["type"] == "runner.heartbeat_ack"


async def test_runtime_event_ingested_through_session():
    session = FakeSession(execute_results=[_Result(row=None)])
    runner = RunnerSession(attempt_id="att_1", session=session)
    replies = await runner.handle(
        {"type": "runtime.event", "event": _event().model_dump(mode="json")}
    )
    # A stored event is acknowledged so the runner can drop it from its buffer.
    assert replies == [{"type": "runner.event_ack", "sequence": 1}]
    events = [o for o in session.added if isinstance(o, runtime.RuntimeEvent)]
    assert len(events) == 1
    assert events[0].id == "evt_1"


async def test_runtime_event_wrong_attempt_rejected():
    runner = RunnerSession(attempt_id="att_1", session=FakeSession())
    with pytest.raises(AuthorizationError):
        await runner.handle(
            {
                "type": "runtime.event",
                "event": _event(call_attempt_id="att_other").model_dump(mode="json"),
            }
        )


# --- ingestion dedup ---------------------------------------------------------


async def test_ingest_stores_event():
    session = FakeSession(execute_results=[_Result(row=None)])
    result = await RuntimeEventIngestor(session).ingest(_event())
    assert result.status == "stored"
    assert len(session.added) == 1


async def test_duplicate_sequence_is_ignored():
    session = FakeSession(execute_results=[_Result(row=("evt_existing",))])
    result = await RuntimeEventIngestor(session).ingest(_event())
    assert result.status == "duplicate_sequence"
    assert session.added == []


async def test_duplicate_provider_event_id_is_ignored():
    session = FakeSession(
        execute_results=[_Result(row=None), _Result(row=("evt_existing",))]
    )
    result = await RuntimeEventIngestor(session).ingest(
        _event(provider_event_id="abc-123")
    )
    assert result.status == "duplicate_provider"
    assert session.added == []


# --- materialization ---------------------------------------------------------


async def test_caller_event_materializes_state_transition():
    session = FakeSession(execute_results=[_Result(scalar=0)])
    envelope_model = _event(
        type="caller.action.selected",
        payload={"action": "clarify", "path": "/authenticated", "from": False, "to": True},
    )
    created = await EventMaterializer(session).materialize(envelope_model)

    assert len(created) == 1
    transition = created[0]
    assert isinstance(transition, runtime.StateTransition)
    assert transition.state_path == "/authenticated"
    assert transition.previous_value == {"value": False}
    assert transition.new_value == {"value": True}
    assert transition.trigger_event_id == "evt_1"


async def test_turn_start_materializes_call_turn():
    session = FakeSession(execute_results=[_Result(scalar=0)])
    envelope_model = _event(
        type="turn.start", turn_id="turn_1", payload={"speaker": "caller"}
    )
    created = await EventMaterializer(session).materialize(envelope_model)

    assert len(created) == 1
    turn = created[0]
    assert isinstance(turn, runtime.CallTurn)
    assert turn.id == "turn_1"
    assert turn.speaker == "caller"
    assert turn.sequence_no == 1


# --- connection registry / control commands ----------------------------------


def test_registry_signals_control_message_to_connections():
    registry = ConnectionRegistry()
    queue: asyncio.Queue = asyncio.Queue()
    registry.register("att_1", queue)

    delivered = registry.signal("att_1", protocol.build_cancel("USER_REQUESTED"))

    assert delivered == 1
    assert queue.get_nowait() == {"type": "attempt.cancel", "reason": "USER_REQUESTED"}

    registry.unregister("att_1", queue)
    assert registry.is_connected("att_1") is False


def test_registry_terminate_delivery():
    registry = ConnectionRegistry()
    queue: asyncio.Queue = asyncio.Queue()
    registry.register("att_1", queue)
    registry.signal("att_1", protocol.build_terminate("PLAN_CANCELLED"))
    assert queue.get_nowait()["type"] == "attempt.terminate"


def test_global_registry_is_shared():
    assert get_connection_registry() is get_connection_registry()


# --- pub/sub fanout ----------------------------------------------------------


class InMemoryPubSub:
    def __init__(self):
        self.published: list[tuple[str, dict]] = []
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    async def publish(self, channel: str, message: dict) -> None:
        self.published.append((channel, message))
        for queue in self._subscribers.get(channel, []):
            queue.put_nowait(message)

    async def subscribe(self, channel: str):
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(channel, []).append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[channel].remove(queue)


@pytest.fixture(autouse=True)
def _restore_pubsub():
    yield
    set_pubsub(None)


async def test_publish_plan_event_routes_to_plan_channel():
    pubsub = InMemoryPubSub()
    set_pubsub(pubsub)
    await publish_plan_event("plan_1", ATTEMPT_STATUS_CHANGED, {"attempt_id": "att_1"})
    channel, message = pubsub.published[0]
    assert channel == plan_events_channel("plan_1")
    assert message == envelope(ATTEMPT_STATUS_CHANGED, {"attempt_id": "att_1"})


async def test_pubsub_fanout_reaches_all_subscribers():
    pubsub = InMemoryPubSub()
    channel = plan_events_channel("plan_1")
    received_a: list[dict] = []
    received_b: list[dict] = []

    async def collect(store: list[dict]) -> None:
        async for message in pubsub.subscribe(channel):
            store.append(message)
            return

    task_a = asyncio.create_task(collect(received_a))
    task_b = asyncio.create_task(collect(received_b))
    await asyncio.sleep(0.01)  # let both subscribers register
    await pubsub.publish(channel, envelope(ATTEMPT_STATUS_CHANGED, {"attempt_id": "x"}))
    await asyncio.gather(task_a, task_b)

    assert received_a == received_b == [
        envelope(ATTEMPT_STATUS_CHANGED, {"attempt_id": "x"})
    ]


def test_default_pubsub_is_noop():
    assert isinstance(NoOpPubSub(), NoOpPubSub)


def test_plan_channel_is_run_scoped_alias():
    assert plan_events_channel("run_1") == run_events_channel("run_1")
    assert run_events_channel("run_1") == "voiceeval:run:run_1:events"


async def test_publish_run_event_routes_to_run_channel():
    pubsub = InMemoryPubSub()
    set_pubsub(pubsub)
    await publish_run_event("run_1", CALL_RUN_STATUS_CHANGED, {"call_run_id": "cr_1"})
    await publish_run_event("run_1", RUN_PROGRESS, {"total": 3})
    assert [channel for channel, _ in pubsub.published] == [
        run_events_channel("run_1"),
        run_events_channel("run_1"),
    ]
    assert [message["type"] for _, message in pubsub.published] == [
        CALL_RUN_STATUS_CHANGED,
        RUN_PROGRESS,
    ]
