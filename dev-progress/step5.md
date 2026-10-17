# Prompt 5 — Runner Control WebSocket + Runtime Events: Progress

## Status: Complete

The backend realtime control plane is implemented: a runner telemetry/control
WebSocket with short-lived runner auth, append-only runtime-event ingestion with
sequence/provider dedup, event materialization, Redis Pub/Sub fan-out, and the
live plan observation WebSocket.

## What was built

### Runner control channel
- `realtime/runner_auth.py` — `authenticate_runner` (scope + attempt binding)
  and `authenticate_user` for the live channel.
- `realtime/protocol.py` — Pydantic schemas for `runner.register`,
  `runner.heartbeat`, `runtime.event`, the canonical event envelope, and the
  server control messages `attempt.cancel`, `attempt.terminate`,
  `runner.heartbeat_ack`.
- `realtime/runner_ws.py` — `RunnerSession` (protocol logic) plus the
  `WS /internal/v1/attempts/{attempt_id}/stream` endpoint. Rejects invalid,
  expired, wrong-attempt and non-runner tokens.
- `realtime/registry.py` — `ConnectionRegistry` mapping an attempt to its live
  connection queues so control commands can be delivered.

### Runtime event ingestion + materialization
- `realtime/event_ingestion.py` — `RuntimeEventIngestor`: preserves the
  runner-provided `event_id`, dedups by `(attempt, sequence)` and
  `(source, provider_event_id)`, appends to the append-only event log.
- `realtime/materializer.py` — `EventMaterializer`: caller state/action events →
  `state_transition`, `turn.start`/`turn.end` → `call_turn`, `tool.call.*` →
  `tool_call`. Derived objects are rebuildable from the raw log.
- Repository additions: `RuntimeEventRepository.event_exists` /
  `provider_event_exists`, `add_event(event_id=...)`, and a new
  `MaterializationRepository` (turns, tool calls, state transitions).

### Pub/Sub + live channel
- `realtime/pubsub.py` — `PubSub` protocol, `NoOpPubSub` (default),
  `RedisPubSub`, the 7 event-family constants, `plan_events_channel`, best-effort
  `publish_plan_event`. The orchestrator and `PlanService` publish
  plan/run/attempt status changes.
- `realtime/live_ws.py` — `WS /api/v1/evaluation-plans/{plan_id}/live` (user JWT)
  subscribing to the plan's Redis channel.
- Redis pub/sub installed at API lifespan and ARQ worker startup.

### Wiring
- `realtime/routes.py` mounts both WebSocket routers; `main.py` includes the
  internal router, `api/router.py` includes the live router.
- `orchestration/executor.py` and `services/plans.py` publish status changes.

## Verification (all passing)
```bash
uv run pytest          # 132 passed (107 prior + 25 new)
uv run alembic check   # No new upgrade operations detected (no schema change)
```
Live checks against the running containers:
- WebSocket endpoints: bad token → close 1008, wrong-attempt token → close 1008,
  valid runner token → `register` + `heartbeat` → `runner.heartbeat_ack`, live WS
  with a user token connects.
- Redis Pub/Sub: one published `attempt.status.changed` reached 2 subscribers.
- DB ingestion: event stored, duplicate `sequence` deduped,
  `caller.action.selected` materialized a `StateTransition`; rolled back cleanly.

## Decisions
`docs/decisions/0004-realtime-decisions.md` — query-param auth, runner event_id
as PK, deferred turn FK, ignore-not-raise dedup, no-op-by-default pub/sub,
synchronous v1 materialization.

## Deferred to later prompts
- Prompt 6: CallRunner + target adapters + Pipecat caller (real runner that
  connects to the runner WS and emits the canonical event stream).
- Prompt 7: metric/judge/aggregation result computation and their Pub/Sub
  producers (metric.computed, judge.completed, aggregate.updated,
  composite.updated).
- Async (ARQ-queued) materialization replaces the synchronous v1 path.

## What you may still need to do
- Nothing for Prompt 5 — no migration is needed (no schema change).
