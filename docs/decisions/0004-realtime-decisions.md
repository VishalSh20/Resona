# Realtime control plane decisions (Prompt 5)

## 1. WebSocket auth is passed as a `token` query parameter

Browsers cannot set an `Authorization` header on a WebSocket handshake, so both
the runner channel and the live UI channel accept `?token=<jwt>`. The runner
token must carry `scope=runner` **and** an `attempt_id` claim matching the path
attempt; the live channel requires `scope=user`. Failures close the socket with
policy-violation code `1008` before `accept()`.

## 2. Runtime events keep the runner-provided `event_id` as the row id

The canonical envelope's `event_id` is the runtime event's identity, so it is
validated against the `evt_` prefix and stored as the `runtime_event` primary
key (rather than generating a new ULID and discarding the runner's id).

## 3. `runtime_event.turn_id` links only to already-materialized turns

The turn reference in an event may arrive before the turn is materialized, and
`runtime_event.turn_id` is a foreign key. To keep ingestion append-only and
never fail on ordering, the FK is populated only when the referenced `CallTurn`
already exists; the canonical turn reference is retained in the event payload.
The materializer creates the turn (using the runner's logical turn id) so later
events link to it.

## 4. Duplicate events are ignored, never overwritten

Two dedup rules are enforced before insert: `(call_attempt_id, sequence)` and
`(source, provider_event_id)`. A duplicate is reported back to the caller as a
no-op (`duplicate_sequence` / `duplicate_provider`) rather than raising, matching
"reject or safely deduplicate". The database unique constraints remain the final
backstop.

## 5. Pub/Sub defaults to a no-op and is installed at startup

`realtime.pubsub` exposes a `PubSub` protocol. The process-wide instance starts
as `NoOpPubSub` so unit tests never touch Redis; the API lifespan installs
`RedisPubSub`, and `WorkerSettings.on_startup` does the same for workers.
Publication is best-effort — a publish failure is logged, never raised, so a
lost live update cannot fail the state change that produced it.

## 6. Materialization runs synchronously for v1

The design prefers enqueuing normalization rather than doing all DB work inline.
For v1 the raw event is appended and then materialized in the same transaction;
materialization is a pure function of the event log, so it can be moved to an
asynchronous ARQ job without changing semantics. Full turn/tool lifecycle
updates and language/derived events land with the caller runtime (Prompt 6/7).
