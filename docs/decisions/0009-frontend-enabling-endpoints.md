# Frontend-enabling backend changes

## Context

Completing the frontend (execution, results, forensics) and running the full
lifecycle end to end surfaced gaps where the backend contract, as implemented,
could not support the UI's required flows and could not execute at all outside
the inline smoke test. This record captures each change and why it is the least
complex way to satisfy the documented semantics.

## 1. ARQ consumes the queues it is fed (critical)

`WorkerSettings` set no `queue_name`, so ARQ 0.28 workers listened on the default
`arq:queue` while every helper enqueued to `voiceeval:queue:*`. **No validation or
execution job was ever consumed.** ARQ 0.28 workers listen on exactly one queue,
so the named-queue design is preserved by launching one worker process per queue:

- `WorkerSettings.queue_name` is resolved from `WORKER_QUEUE` (fallback
  `voiceeval:queue:execution`).
- `scripts/run_workers.py` starts one worker per `ALL_QUEUES` and shuts them down
  together; `docker-compose.yml` uses it for the `worker` service.

## 2. Duplicate content/config hashes return `409`, not `500`

`UNIQUE(content_hash)` and `UNIQUE(agent_target_id, config_hash)` are correct
(content-addressed) constraints, but a collision surfaced as an unhandled
`IntegrityError`. Both services now catch it, roll back, and raise
`ConflictError` (`CONTENT_ALREADY_EXISTS` / `CONFIG_ALREADY_EXISTS`).

## 3. Enabling read endpoints (additive)

The UI contract requires data the API did not expose. Added, read-only unless
noted, with no change to domain semantics:

- `GET /api/v1/evaluation-plans/{id}/runs` — logical runs for progress/matrix.
- `GET /api/v1/call-runs/{id}/attempts` — attempt lineage for run detail.
- `POST /api/v1/call-runs/{id}/retry` — retry an `infrastructure_failed` run.
- `GET /api/v1/evaluation-plans/{id}/manifest` — the sealed manifest.
- Event filters on `GET /call-attempts/{id}/events` (`source`, `type`, `from_ms`,
  `to_ms`) so the forensic stream can be filtered server-side.
- `plan.created_at`; `call_attempt.execution_manifest_id`, `transport_version`,
  `created_at`; turn language profiles / audio artifact ids / confidence.
- Test-descriptor endpoints (`/test-descriptors`, `.../revisions`,
  `/test-descriptor-revisions/{id}`) — custom plans require a descriptor revision
  and there was no way to create one.

## 4. Retention semantics of a retry

A retry never creates another `CallRun` (statistical sample). Since
`INFRASTRUCTURE_FAILED` is terminal for a run, a manual retry (and plan resume)
**reopens** it to `RUNNING` through an explicit, narrow transition
(`reopen_call_run_for_retry`) and adds a physical attempt. Only
`INFRASTRUCTURE_FAILED` can be reopened; completed/cancelled runs stay terminal.

## 5. Plan completion is not gated on evaluation eligibility

A run can become terminal without producing metrics — e.g. a conversation stall
is a valid statistical sample (`ACTION_COMPLETED`) but has
`eligible_for_evaluation=False`. Completion was only detected from the judges
worker, which never ran for such a run, so the plan stayed `RUNNING` forever.
`orchestration/terminal.py` now evaluates plan completion for **every** terminal
run (skipping only retry outcomes) and enqueues aggregation when the plan is
evaluation-complete (`AggregationEngine.is_plan_evaluation_complete` already
tolerates runs with no eligible attempt).

## 6. Benchmark cases are materialized from the version manifest

A version's `manifest.cases` was stored but never turned into `benchmark_case`
rows, so benchmark plan preparation always failed with "no benchmark cases".
`BenchmarkService.create_version` now materializes them (draft versions are
mutable, so this is allowed).

## 7. Media originals are persisted to the object store

The runner recorded media metadata but discarded the bytes, so every
`GET /media/{id}/url` returned `404`. `MediaRecorder` now retains the original
bytes and the attempt's media sink writes them to the `ObjectStore`, recording
`object_uri`. Original artifacts remain immutable.

## 8. The deterministic fake target is per-connection

`FakeTargetServer` used a single shared `caller_turns_seen` counter, so two
concurrent calls to the same fake target consumed the script from one cursor and
one call stalled. Counting is now per connection.

## 9. Local execution defaults

- `RUNNER_DISPATCH_MODE=inline|subprocess` (default `subprocess`). Local dev uses
  `inline` so the worker runs the runner in-process — no separate runner
  container — which is how the end-to-end check runs.
- `python -m voiceeval.runtime.fake_target` runs the deterministic fake target as
  a standalone service on `FAKE_TARGET_PORT` (default `8790`); a `fake-target`
  compose service (profile `dev`) is provided.

## Consequences / limitations

- The queue-per-worker launcher runs six processes; container orchestration or a
  process supervisor should own them in a real deployment.
- Test descriptors are a thin config surface (name + source text); generator
  models are not implemented (the schema allows them).
- Retry/reopen is a deliberate, documented widening of the run state machine.
- Frontend-side limitations carried into v1: no audio waveform rendering
  (functional `<audio>` player with evidence seek), non-virtualized tables
  (paged "first N"), and a simplified timeline without zoom/pan.
