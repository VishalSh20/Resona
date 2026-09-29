# VoiceEval Backend

Backend-only implementation of the VoiceEval voice-agent evaluation platform:
a FastAPI control plane, specialized ARQ workers, and a disposable realtime call
runner. The design contract lives in [`../docs`](../docs); the requirement →
implementation → test trace is in [`../docs/requirements-matrix.md`](../docs/requirements-matrix.md).

## Architecture

One Python application, several process roles (never microservices):

```text
FastAPI control plane ─── PostgreSQL (domain + results)
        │                ─ Redis (ARQ queues + live Pub/Sub)
        │                ─ MinIO / local object store (media)
        ├── ARQ workers: validation · execution · metrics · judges · aggregation
        └── runner (disposable, horizontally scalable): CallRunner + caller + adapter
                                   │
                                   ▼
                         third-party voice agent
```

Three truths are kept separate: **TEST TRUTH** (evaluator revisions +
`execution_manifest`), **OBSERVED TRUTH** (`call_run` → `call_attempt` → events /
turns / tool calls / state transitions / media) and **EVALUATION TRUTH**
(`metric_result` + `judge_execution` + `evidence` → `aggregate_result` →
`composite_score_result`).

A `CallRun` is a logical statistical repetition; a `CallAttempt` is one physical
attempt. Retries create attempts, never repetitions.

## Stack

- Python 3.13, managed with `uv`
- FastAPI + Pydantic v2
- SQLAlchemy 2 (async) + asyncpg + Alembic
- PostgreSQL, Redis, MinIO/S3
- ARQ worker queue, PyJWT, websockets, OpenTelemetry, structured JSON logging

## Local setup

```bash
cd backend
uv venv --python 3.13
uv sync
cp .env.example .env      # then fill in values; never commit .env
```

## Commands

```bash
uv run uvicorn voiceeval.main:app --reload           # control plane
uv run pytest                                        # tests
uv run alembic upgrade head                          # apply migrations
uv run alembic downgrade -1                          # roll back one migration
uv run alembic check                                 # schema == metadata
uv run python scripts/run_workers.py                 # all ARQ workers (one process per queue)
WORKER_QUEUE=voiceeval:queue:metrics uv run arq voiceeval.workers.arq.WorkerSettings  # a single queue
uv run python -m voiceeval.runtime.fake_target       # deterministic fake target (local dev)
uv run python -m voiceeval.runtime --attempt-id att_X --telemetry-url <ws-url>   # runner
```

## Environment variables

See [`.env.example`](.env.example). Key groups:

| Group | Variables |
|---|---|
| App | `APP_ENV`, `APP_HOST`, `APP_PORT` |
| Database | `DATABASE_URL` |
| Redis | `REDIS_URL` |
| JWT | `JWT_SECRET`, `JWT_ISSUER`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| Storage | `OBJECT_STORAGE_MODE=local\|s3`, `LOCAL_OBJECT_STORAGE_PATH`, `S3_*` |
| Providers | `OPENAI_API_KEY`, `SARVAM_API_KEY` |
| Observability | `OTEL_EXPORTER_OTLP_ENDPOINT` |
| Runtime | `RUNNER_BACKEND_URL`, stall/timeout defaults, `max_attempts_per_run` |

No secret is committed; `.env` is gitignored.

## Authentication

The whole `/api/v1` surface requires a `user`-scope bearer JWT. Interactive
clients sign up / sign in; service accounts mint tokens out of band.

```text
POST /api/v1/auth/register   { email, password, username? }  -> 201 + token
POST /api/v1/auth/login      { email, password }             -> 200 + token
GET  /api/v1/auth/me                                         -> the identity
```

Passwords are hashed with the standard library's scrypt (`users.password_hash`).
`register`/`login` are the only unauthenticated HTTP endpoints besides the
HMAC-signed `GET /api/v1/media/blob`. To mint a token without an account:

```bash
uv run python -m voiceeval.auth.cli --sub operator@example.com
# runner tokens (short-lived, attempt-bound) are minted by the dispatcher, or:
uv run python -m voiceeval.auth.cli --sub runner-1 --scope runner --attempt att_X
```

WebSockets authenticate with a `token` query parameter (user JWT for the live
channel, runner token for the control channel).

## Database migrations

Alembic is async and reads `DATABASE_URL` from settings.

```bash
uv run alembic upgrade head    # 0001 foundation, 0002 domain, 0003 plan source, 0004 immutability triggers, 0005 user password
uv run alembic current
uv run alembic downgrade -1
```

Migration `0004` installs `BEFORE UPDATE OR DELETE` triggers that make
`runtime_event`, `execution_manifest` and `media_artifact` immutable at the
database level.

## Docker

```bash
cd backend
docker compose up -d                              # postgres, redis, minio, api, worker
docker compose logs -f api
docker compose --profile runner up -d runner      # disposable runner container
docker compose config                             # validate the compose file
```

## Worker execution

ARQ workers listen on exactly one queue each, so the deployment runs one worker
process per named queue. `scripts/run_workers.py` starts them all (the compose
`worker` service uses it); `WorkerSettings.queue_name` is taken from
`WORKER_QUEUE` (fallback `voiceeval:queue:execution`).

```text
voiceeval:queue:validation    validate_evaluator_revision
voiceeval:queue:execution     execution_plan_start · execution_run_start · execution_attempt_start
voiceeval:queue:metrics       compute_attempt_metrics
voiceeval:queue:judges        compute_run_judges
voiceeval:queue:aggregation   compute_plan_aggregation
```

Every enqueue uses a deterministic `_job_id` (e.g. `evaluation:metrics:{attempt}`)
so a retried dispatch cannot duplicate work.

## Runner execution

The runner is disposable and horizontally scalable. The orchestrator dispatches
`python -m voiceeval.runtime` per attempt; the runner connects to the target
through a versioned adapter, drives the deterministic caller loop, normalizes
provider observations into canonical events, evaluates stop conditions, records
media and streams telemetry + a terminal outcome back over
`WS /internal/v1/attempts/{attempt_id}/stream`.

`RUNNER_DISPATCH_MODE` selects how an attempt is handed to a runner:
`subprocess` (default) spawns an isolated process; `inline` runs the runner
inside the worker — no separate runner container, handy for local development.

For local end-to-end runs, start the deterministic fake target and point a target
revision at it:

```bash
uv run python -m voiceeval.runtime.fake_target          # ws://localhost:8790/target
# target revision: adapter_name=fake, endpoint_config={"url": "ws://localhost:8790/target"}
```

## API usage

Batch API under `/api/v1` (all require a bearer token):

```text
POST       /api/v1/auth/register|login                     sign up / sign in  (unauthenticated)
GET        /api/v1/auth/me                                 current identity
POST/GET   /api/v1/targets                                 target identity
POST       /api/v1/targets/{id}/revisions                  validated revision
POST/GET   /api/v1/evaluators, /evaluators/{id}/revisions  evaluator config
POST       /api/v1/evaluator-revisions/{id}/validate       async validation (202)
POST       /api/v1/evaluator-revisions/{id}/approve        VALIDATED -> APPROVED
POST/GET   /api/v1/benchmarks, /benchmarks/{id}/versions
POST       /api/v1/benchmark-versions/{id}/freeze
POST/GET   /api/v1/test-descriptors[/{id}/revisions]       custom-plan descriptor
POST/GET   /api/v1/evaluation-plans                        create/list/get
GET        /api/v1/evaluation-plans/{id}/items|runs        plan items / logical runs
POST       /api/v1/evaluation-plans/{id}/prepare|execute|cancel|resume
GET        /api/v1/evaluation-plans/{id}/results|aggregates|composite|manifest
GET        /api/v1/call-runs/{id}, /call-runs/{id}/forensics
POST       /api/v1/call-runs/{id}/retry                    retry an infra failure
GET        /api/v1/call-runs/{id}/attempts                 attempt lineage
GET        /api/v1/call-attempts/{id}[/events|/conversation|/media]
GET        /api/v1/metric-results/{id}[/evidence]
GET        /api/v1/media/{artifact_id}/url                 short-lived signed URL
WS         /api/v1/evaluation-plans/{plan_id}/live         live observation
```

`GET /call-attempts/{id}/events` supports `limit`, `offset`, `source`, `type`,
`from_ms` and `to_ms`. State-changing requests require an `Idempotency-Key`
header.

## Example evaluation lifecycle

```text
create target ──▶ create target revision
              ──▶ create evaluator ──▶ create revision ──▶ validate ──▶ approve
              ──▶ create plan ──▶ prepare (capability negotiation + manifest + items)
              ──▶ execute ──▶ workers expand runs/attempts ──▶ runner (fake target)
              ──▶ runtime events materialized ──▶ metrics ──▶ judge ──▶ aggregation
              ──▶ composite ──▶ forensic result retrieval
```

`scripts/smoke_e2e.py` runs this end to end against live Postgres + Redis using
the deterministic fake target:

```bash
uv run python scripts/smoke_e2e.py
```

## Tests

```bash
uv run pytest                 # full suite (unit; DB-free by design)
uv run pytest tests/test_api_auth.py tests/test_workers.py
```

Testing is intentionally simple for v1: `pytest`, `pytest-asyncio`, `httpx`
`ASGITransport` and in-process fakes. No Testcontainers.

## Status

Prompts 1–8 are implemented. See the final report in
[`../docs/decisions/0007-hardening-decisions.md`](../docs/decisions/0007-hardening-decisions.md)
for what is complete, what is partial, and what is deliberately deferred
(WebRTC media transport, async materialization, secret-reference resolution).

Frontend-enabling additions (multi-queue worker launcher, sign-up/sign-in, run
retry, manifest/test-descriptor/read endpoints, event filters, media persistence,
plan-completion fix) are recorded in
[`../docs/decisions/0008-auth-signup-decisions.md`](../docs/decisions/0008-auth-signup-decisions.md)
and
[`../docs/decisions/0009-frontend-enabling-endpoints.md`](../docs/decisions/0009-frontend-enabling-endpoints.md).
