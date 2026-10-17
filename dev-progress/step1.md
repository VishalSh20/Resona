# Prompt 1 — Foundation and Skeleton: Progress

## Status: Complete

The VoiceEval backend foundation is implemented, tested, and running in Docker.
The repository contained only design docs, so the `backend/` package was created
from scratch (no existing caller/Pipecat code to preserve).

## What was built

### Project structure
```
backend/
├── pyproject.toml          # Python 3.13, uv, core stack deps
├── uv.lock
├── alembic.ini
├── alembic/
│   ├── env.py              # async migration environment
│   ├── script.py.mako
│   └── versions/0001_initial_foundation.py
├── Dockerfile              # uv-based image, shared by api/worker/runner
├── docker-compose.yml      # v1 local environment
├── .env.example            # safe placeholders, no secrets committed
├── .dockerignore
├── README.md
├── src/voiceeval/
│   ├── main.py             # FastAPI app, middleware, error handlers, /health, /ready
│   ├── core/               # config, logging, errors, ids, clocks
│   ├── auth/               # jwt, dependencies (user/runner scopes)
│   ├── db/                 # session, base, models/
│   ├── api/                # router, dependencies, routes/
│   ├── workers/            # arq queue topology + bootable WorkerSettings
│   ├── storage/            # ObjectStore protocol
│   ├── observability/      # OpenTelemetry tracer wiring
│   └── (runtime, realtime, orchestration, services, schemas,
│        metrics, judges, aggregation)  # package stubs for later prompts
└── tests/                  # 19 tests, all passing
```

### Implemented capabilities
- **Configuration** (`pydantic-settings`) — all specified env vars: APP_*, DATABASE_URL,
  REDIS_URL, JWT_*, OBJECT_STORAGE_MODE, LOCAL_OBJECT_STORAGE_PATH, S3_*,
  OPENAI_API_KEY, SARVAM_API_KEY, OTEL_EXPORTER_OTLP_ENDPOINT, plus runtime
  timeout defaults (stall 10s, wall-clock 180s, max 300s) as config, not constants.
- **Structured JSON logging** — timestamp/level/logger/message/request_id/trace_id
  via contextvars.
- **Request IDs** — `X-Request-ID` accepted or generated, echoed back.
- **JWT** — `sub/iss/exp/iat/scope` claims, `user` and `runner` scopes, short-lived
  runner token carrying `attempt_id`. No signup/identity UX.
- **IDs** — ULID + domain-prefix abstraction (`EntityKind` → `new_id`/`kind_of`/`ensure_kind`),
  covering all 24 documented prefixes.
- **Errors** — consistent envelope `{"error": {code, message, request_id}}` with
  global exception handlers.
- **FastAPI** — `GET /health` (liveness), `GET /ready` (Postgres + Redis checks, 503 when down),
  mounted `/api/v1` router.
- **DB/Alembic** — async engine/session, declarative base, async `env.py`, empty
  `0001` baseline migration.
- **Docker** — v1 environment (api, worker, runner, postgres, redis, minio); runner
  under `profiles: ["runner"]` as a disposable process.

## Verification (all passing)
```bash
uv sync                        # Python 3.13.13, lock file generated
uv run pytest                  # 19 passed
uv run uvicorn voiceeval.main:app --reload   # starts, /health returns 200
uv run alembic upgrade head    # online, against running Postgres
uv run alembic downgrade -1    # verified
uv run alembic upgrade head    # verified
docker compose up -d           # all services healthy
```
`GET /ready` → `200 {"status":"ok","checks":{"postgres":"ok","redis":"ok","object_storage":"local"}}`

## Issues encountered and resolved
1. **MinIO image unavailable** — MinIO deleted Docker Hub images and auth-gated
   Quay.io. Replaced with `coollabsio/minio:latest` (community rebuild from
   official releases). For production, pin a specific `RELEASE.*` tag.
2. **MinIO healthcheck** — UBI9-micro base has no `curl`/`wget`; switched to a
   bash `/dev/tcp` TCP probe with a 15s `start_period`.
3. **ARQ worker crash** — ARQ requires at least one registered function; added a
   placeholder `ping` handler so the worker boots.

## Decisions not specified by design docs
- JWT default secret is a long placeholder; real deployments must override via `JWT_SECRET`.
- Object storage defaults to `local` mode for v1; S3 wiring lands with the media APIs.

## Deferred to later prompts
- Prompt 2: domain persistence layer + migrations
- Prompt 3: REST API + validation + capability negotiation
- Prompt 4: plan preparation, manifest, ARQ orchestration
- Prompt 5: runner control WebSocket + runtime events
- Prompt 6: CallRunner + target adapters + Pipecat caller
- Prompt 7: metrics, judges, aggregation, results, forensics
- Prompt 8: hardening, tests, documentation

## What you may still need to do
- Fill real secrets in `backend/.env` (copy from `.env.example`) before real use.
- `git init` + commit if version control is wanted (repo is not yet a git repo).
