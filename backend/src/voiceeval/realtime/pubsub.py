"""Redis Pub/Sub fan-out for live plan observation.

Runtime/status changes are published to a per-plan channel; the live plan
WebSocket subscribes and forwards them to UI clients. Publishing never touches
the audio path. A ``PubSub`` implementation is looked up through
:func:`get_pubsub` so tests can substitute an in-memory implementation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Protocol

import redis.asyncio as redis

from voiceeval.core.config import get_settings

# The published event families the UI subscribes to.
PLAN_STATUS_CHANGED = "plan.status.changed"
RUN_STATUS_CHANGED = "run.status.changed"
CALL_RUN_STATUS_CHANGED = "call_run.status.changed"
ATTEMPT_STATUS_CHANGED = "attempt.status.changed"
RUN_PROGRESS = "run.progress"
METRIC_COMPUTED = "metric.computed"
JUDGE_COMPLETED = "judge.completed"
AGGREGATE_UPDATED = "aggregate.updated"
COMPOSITE_UPDATED = "composite.updated"


def run_events_channel(run_id: str) -> str:
    """Live-observation channel for a run (the v0.4 domain key)."""
    return f"voiceeval:run:{run_id}:events"


# Deprecated v0.3 name; the channel is run-scoped now and producers pass run_id.
plan_events_channel = run_events_channel


def envelope(event_type: str, data: dict) -> dict:
    return {"type": event_type, "data": data}


class PubSub(Protocol):
    async def publish(self, channel: str, message: dict) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict]: ...


class NoOpPubSub:
    """Default implementation: publishing is a no-op and nothing is subscribed.

    The real Redis-backed implementation is installed at application/worker
    startup so unit tests never touch Redis.
    """

    async def publish(self, channel: str, message: dict) -> None:
        return None

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:  # pragma: no cover
        return
        yield {}


class RedisPubSub:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or get_settings().redis_url

    async def publish(self, channel: str, message: dict) -> None:
        client = redis.from_url(self._redis_url, decode_responses=True)
        try:
            await client.publish(channel, json.dumps(message, default=str))
        finally:
            await client.aclose()

    async def subscribe(self, channel: str) -> AsyncIterator[dict]:
        client = redis.from_url(self._redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()
            await client.aclose()


_pubsub: PubSub = NoOpPubSub()


def get_pubsub() -> PubSub:
    return _pubsub


def set_pubsub(pubsub: PubSub | None) -> None:
    """Install the process-wide pub/sub implementation (startup / tests)."""
    global _pubsub
    _pubsub = pubsub if pubsub is not None else NoOpPubSub()


async def publish_plan_event(plan_id: str, event_type: str, data: dict) -> None:
    """Best-effort publish of a live-observation event for a plan.

    Publication failures are logged, never raised: losing a live update must not
    fail the state change that produced it.
    """
    try:
        await get_pubsub().publish(
            plan_events_channel(plan_id), envelope(event_type, data)
        )
    except Exception as exc:  # pragma: no cover - depends on live Redis
        logging.getLogger("voiceeval.realtime").warning(
            "failed to publish %s for plan %s: %s", event_type, plan_id, exc
        )


async def publish_run_event(run_id: str, event_type: str, data: dict) -> None:
    """Best-effort publish of a live-observation event for a run."""
    await publish_plan_event(run_id, event_type, data)
