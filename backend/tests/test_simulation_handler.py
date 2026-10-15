"""Simulation handler: capacity-aware batching of call dispatches.

Exercises the batching contract directly (one logical call per evaluator, never
more in flight than capacity) without a database.
"""

from __future__ import annotations

from voiceeval.db.models import runtime
from voiceeval.domain.enums import CallRunStatus
from voiceeval.orchestration.simulation_handler import BatchedSimulationHandler
from voiceeval.realtime.pubsub import RUN_PROGRESS, set_pubsub


class _Scalars:
    def __init__(self, values):
        self._values = values

    def all(self):
        return list(self._values)


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _Scalars(self._values)


class FakeSession:
    """Returns the seeded call runs for any ``select`` and records commits."""

    def __init__(self, call_runs):
        self._call_runs = call_runs
        self.committed = 0

    async def execute(self, stmt):
        return _Result(list(self._call_runs))

    async def flush(self):
        pass

    async def commit(self):
        self.committed += 1


class RecordingPubSub:
    def __init__(self):
        self.published = []

    async def publish(self, channel, message):
        self.published.append((channel, message))

    async def subscribe(self, channel):
        return
        yield {}


def _call_run(index: int, status: str = CallRunStatus.QUEUED.value) -> runtime.CallRun:
    return runtime.CallRun(
        id=f"callrun_{index}",
        run_id="run_1",
        run_evaluator_id=f"runeval_{index}",
        repetition_no=1,
        status=status,
    )


def _handler(**kwargs) -> BatchedSimulationHandler:
    kwargs.setdefault("max_concurrent_calls", 2)
    kwargs.setdefault("max_concurrent_per_target", 2)
    return BatchedSimulationHandler(**kwargs)


async def test_schedule_dispatches_up_to_capacity(monkeypatch):
    enqueued: list[str] = []

    async def fake_enqueue(call_run_id):
        enqueued.append(call_run_id)

    monkeypatch.setattr(
        "voiceeval.workers.enqueue.enqueue_execution_call_run", fake_enqueue
    )
    call_runs = [_call_run(i) for i in range(5)]
    session = FakeSession(call_runs)

    await _handler().schedule(session, "run_1")

    assert enqueued == ["callrun_0", "callrun_1"]
    running = [cr for cr in call_runs if cr.status == CallRunStatus.RUNNING.value]
    assert len(running) == 2
    assert session.committed == 1


async def test_schedule_tops_up_after_a_terminal(monkeypatch):
    enqueued: list[str] = []

    async def fake_enqueue(call_run_id):
        enqueued.append(call_run_id)

    monkeypatch.setattr(
        "voiceeval.workers.enqueue.enqueue_execution_call_run", fake_enqueue
    )
    call_runs = [_call_run(i) for i in range(5)]
    session = FakeSession(call_runs)
    handler = _handler()

    await handler.schedule(session, "run_1")
    # One in-flight call finishes and frees a slot.
    call_runs[0].status = CallRunStatus.COMPLETED.value
    await handler.schedule(session, "run_1")

    assert enqueued == ["callrun_0", "callrun_1", "callrun_2"]
    running = [cr for cr in call_runs if cr.status == CallRunStatus.RUNNING.value]
    assert len(running) == 2


async def test_schedule_respects_per_target_cap(monkeypatch):
    enqueued: list[str] = []

    async def fake_enqueue(call_run_id):
        enqueued.append(call_run_id)

    monkeypatch.setattr(
        "voiceeval.workers.enqueue.enqueue_execution_call_run", fake_enqueue
    )
    call_runs = [_call_run(i) for i in range(4)]
    session = FakeSession(call_runs)

    await _handler(max_concurrent_calls=10, max_concurrent_per_target=1).schedule(
        session, "run_1"
    )

    assert enqueued == ["callrun_0"]


async def test_schedule_does_not_redispatch_when_full(monkeypatch):
    enqueued: list[str] = []

    async def fake_enqueue(call_run_id):
        enqueued.append(call_run_id)

    monkeypatch.setattr(
        "voiceeval.workers.enqueue.enqueue_execution_call_run", fake_enqueue
    )
    call_runs = [_call_run(i) for i in range(5)]
    session = FakeSession(call_runs)
    handler = _handler()

    await handler.schedule(session, "run_1")
    await handler.schedule(session, "run_1")

    assert enqueued == ["callrun_0", "callrun_1"]


async def test_schedule_publishes_progress(monkeypatch):
    async def fake_enqueue(call_run_id):
        return None

    monkeypatch.setattr(
        "voiceeval.workers.enqueue.enqueue_execution_call_run", fake_enqueue
    )
    pubsub = RecordingPubSub()
    set_pubsub(pubsub)
    try:
        call_runs = [_call_run(i) for i in range(5)]
        await _handler().schedule(FakeSession(call_runs), "run_1")
    finally:
        set_pubsub(None)

    progress = [m for _, m in pubsub.published if m["type"] == RUN_PROGRESS]
    assert progress, "expected a run.progress event"
    assert progress[-1]["data"] == {
        "run_id": "run_1",
        "total": 5,
        "queued": 3,
        "running": 2,
        "completed": 0,
        "infrastructure_failed": 0,
        "cancelled": 0,
    }
