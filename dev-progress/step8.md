# Prompt 8 — Hardening, Tests, Documentation: Progress

## Status: Complete

Prompt 8 is a review-and-harden pass. The implementation was inspected against
all six source documents, a requirements matrix was built, and the gaps it
surfaced were closed with code, database constraints, tests and documentation.

The full requirement → implementation → test trace lives in
[`../docs/requirements-matrix.md`](../docs/requirements-matrix.md); the decisions
and the security/observability reviews live in
[`../docs/decisions/0007-hardening-decisions.md`](../docs/decisions/0007-hardening-decisions.md).

## What was built

### Security — the API surface is now authenticated
- Every `/api/v1` route requires a `user`-scope bearer JWT (router-level
  `require_user_dep`). `require_user` had been dead code since Prompt 3.
- `GET /api/v1/media/blob` is deliberately unauthenticated (split into its own
  router) and authorised by its short-lived HMAC-signed URL.
- Token issuance CLI: `python -m voiceeval.auth.cli` + `create_user_token` —
  no public signup, per the Prompt 1 rule.

### Observability — tracing and correlation
- `init_tracing()` is now actually called (app import, ARQ startup, runner CLI)
  and is idempotent.
- A `span()` helper annotates the documented paths: API request, ARQ jobs,
  orchestrator plan/run/dispatch, target connection, caller execution, metric
  computation, judge invocation, aggregation.
- `plan_id`/`run_id`/`attempt_id` are contextvars in structured logging and are
  bound via `bind_execution_context(...)` in the engines, orchestrator and runner.

### Idempotency hardening
- Request body hash persisted (`request_hash`); reusing a key with a different
  body is flagged distinctly.
- The SELECT-then-INSERT race is closed: the DB unique violation is translated
  to a clean 409 instead of a 500.

### Immutability — database backstop (migration `0004`)
- `BEFORE UPDATE OR DELETE` triggers on `runtime_event`, `execution_manifest`
  and `media_artifact` raise on mutation, beyond application convention. Derived
  tables stay mutable (rebuildable projections).

### Domain gap — motive assertion state machine
- Added `AssertionState` (PENDING → SATISFIED/UNSATISFIED/…/NO_OBSERVABLE_EVIDENCE/
  UNKNOWN) and `assertion_state(verdict, oracle)`.
- The LLM judge now lands in the `CONVERSATION_EVIDENCE` tier when its verdict is
  grounded in evidence, making that precedence level real.

### Bug fix
- `InlineRunnerDispatcher` never committed, so an inline run's terminal state and
  materialized objects were rolled back. It now commits after the run (found by
  the smoke test).

### Tests (313 total; +35 this pass)
- `test_api_auth.py` — 401/403, public signed blob, 422/400 validation, error
  envelope, authorized reads (session stubbed, no DB).
- `test_workers.py` — deterministic ARQ job identities, eligibility gate,
  aggregation trigger, registered handlers.
- `test_observability.py` — log context fields/restoration, span trace ids,
  idempotent init.
- `test_idempotency.py` — request-hash binding, key reuse, race → 409.
- `test_judges.py` — assertion states + conversation/LLM oracle tiers.

### Documentation
- `backend/README.md` — architecture, setup, uv commands, env vars, migrations,
  docker, worker/runner execution, API usage, example lifecycle, tests.
- `docs/requirements-matrix.md` — the Prompt 8 requirements matrix.
- `docs/decisions/0007-hardening-decisions.md` — decisions + security and
  observability reviews.

## Verification (all passing)
```bash
uv sync                                     # 99 packages, lock respected
uv run pytest                               # 313 passed
uv run alembic upgrade head                 # 0004 applied
uv run alembic downgrade -1 && upgrade head # round-trips
uv run alembic check                        # schema == metadata
docker compose config                       # valid
uv run python scripts/smoke_e2e.py          # ALL CHECKS PASSED
```
Live trigger check (Docker Postgres): UPDATE `execution_manifest`, UPDATE
`runtime_event` and DELETE `media_artifact` all raise.

End-to-end smoke (live Postgres + Redis, deterministic fake target): target →
revision → evaluator → validate → approve → plan → prepare (manifest) → execute
→ 3 repetitions = 3 CallRuns → 3 completed attempts → 168 runtime events → 4
turns → 15 aggregates → composite → forensic bundle. Plan reaches `completed`.

## Known limitations / deferred
- WebRTC media transport is interface + validation contract only (not executed).
- Deterministic model behaviour is not claimed (real providers are
  nondeterministic).
- Async (ARQ-queued) materialization is still synchronous in v1.
- Endpoint secret references are validated but not resolved at dispatch time.
- Full idempotency *response replay* is out of scope (409 semantics retained).

## What you may still need to do
- `docker compose down` the local Postgres/Redis containers if no longer needed.
- Provide real `JWT_SECRET` / provider keys in `backend/.env` for real use.
