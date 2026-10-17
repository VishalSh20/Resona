# Prompt 4 — Plan Preparation, Manifest, ARQ, Orchestration: Progress

## Status: Complete

Execution planning and orchestration are implemented, tested, and wired into the
API and ARQ worker. Preparation builds an immutable execution manifest after
capability negotiation; execution expands plans into logical CallRuns and
physical CallAttempts with correct retry/cancel/resume semantics.

## What was built

### Domain model + migration
- `evaluation_plan.evaluator_revision_ids` (JSONB, nullable) — custom plans
  store the evaluator revisions they will execute; benchmark plans resolve them
  from `benchmark_case` rows at prepare time.
- `alembic/versions/0003_plan_evaluator_source.py` — adds the column; verified
  via offline `alembic upgrade head --sql`.

### Orchestration (`orchestration/`)
- `retry.py` — `RETRYABLE_FAILURE_CLASSES` plus `resolve_attempt_termination`
  (retry / completed / infrastructure_failed / cancelled) and deterministic
  `derive_run_seed` (SHA-256 of plan + evaluator + repetition identity).
- `manifest.py` — immutable, content-addressed `ExecutionManifest` snapshots
  (target, evaluators, benchmark, caller/runtime versions, metrics, judges,
  aggregation, composite) with a canonical `manifest_hash`.
- `executor.py` — `ExecutionOrchestrator`: `expand_runs`/`ensure_runs` (exactly
  `repeat_count` runs per item), `start_run`, `start_attempt`,
  `record_attempt_terminal` (retry vs finalize), `cancel_plan`, `resume_plan`.

### Services
- `services/plans.py` — `PlanService`: create (kind/version/repeat/target
  validation), prepare (target → evaluators → APPROVED check → capability
  negotiation → manifest → plan items → READY), execute (READY→QUEUED + job +
  enqueue), cancel, resume.

### ARQ (`workers/`)
- `enqueue.py` — shared queue names, job names and deterministic job ids
  (`execution:plan:{id}`, `execution:run:{id}`, `execution:attempt:{id}`).
- `jobs/execution.py` — `execution_plan_start`, `execution_run_start`,
  `execution_attempt_start`. Runner dispatch inside attempt-start is a documented
  placeholder until Prompt 6.
- `arq.py` — registers the three execution handlers (and re-exports
  `enqueue_validation`).

### API (`api/routes/plans.py` + `schemas/plans.py`)
- `POST /api/v1/evaluation-plans` (201), `GET .../`, `GET .../{id}`,
  `POST .../{id}/prepare`, `POST .../{id}/execute` (202), `POST .../{id}/cancel`,
  `POST .../{id}/resume`, plus `GET .../{id}/items`.
- All state-changing routes require an `Idempotency-Key`.

### Repositories
- `EvaluationPlanRepository` — `create_plan` stores evaluator revisions, plus
  `attach_manifest`.
- `CallRunRepository` — `start_run`, `finish_run`, `list_runs_by_status`.
- `CallAttemptRepository` — `record_terminal` (terminal class + failure class +
  eligibility).

## Verification (all passing)
```bash
uv run pytest              # 107 passed (79 prior + 28 new)
uv run alembic upgrade head --sql   # migration 0003 compiles offline
uv run alembic current     # 0003 (head), applied to live Postgres
uv run alembic check       # No new upgrade operations detected (schema == metadata)
```
- All 7 `/api/v1/evaluation-plans*` routes resolve in OpenAPI.
- Worker settings register `execution_plan_start`, `execution_run_start`,
  `execution_attempt_start`.
- Live-Postgres smoke test passed (target → evaluator(approved) → plan →
  prepare(manifest) → 3 CallRuns → infra retry spawns attempt 2 on the same run)
  and rolled back cleanly.

## Decisions
`docs/decisions/0003-plan-preparation-decisions.md` — custom evaluator source,
plan-item materialization timing, capability negotiation blocking prepare,
content-addressed manifest, failure-class-driven retry, resume-never-re-samples.

## Deferred to later prompts
- Prompt 5: runner control WebSocket + runtime event ingestion; live runner
  termination signal for cancelling *running* attempts (Prompt 4 cancels queued
  work and retains history).
- Prompt 6: CallRunner + target adapters + Pipecat caller (replaces the runner
  dispatch placeholder in `execution_attempt_start`).
- Prompt 7: metric/judge/aggregation registries and result computation.

## What you may still need to do
- Nothing for Prompt 4 — migration 0003 is applied to the live DB and verified.
