# Prompt 2 — Domain Model, SQLAlchemy, Migrations: Progress

## Status: Complete

The complete domain persistence layer is implemented, migrated, and tested.

## What was built

### Domain vocabulary and state machines
- `src/voiceeval/domain/enums.py` — StrEnum values for every enum-like column
  (transport, statuses, sources, kinds, metric value types, etc.).
- `src/voiceeval/domain/state_machines.py` — explicit transition functions for
  evaluator revision, evaluation plan, call run, and call attempt. Arbitrary
  status mutation raises `InvalidStateTransitionError`.

### SQLAlchemy 2 async models
- `db/models/support.py` — `users`, `user_roles`, `idempotency_keys`, `jobs`.
- `db/models/domain.py` — targets, test descriptors, evaluators, benchmarks,
  evaluation plans/items, execution manifests (TEST TRUTH).
- `db/models/runtime.py` — call runs, attempts, turns, runtime events, tool
  calls, state transitions, media artifacts (OBSERVED TRUTH).
- `db/models/results.py` — metric/judge definitions, metric results, evidence,
  aggregates, composite scores (EVALUATION TRUTH).
- `db/models/mixins.py` — id/timestamp mixins; prefixed-ULID `TEXT` primary keys.
- `db/models/__init__.py` — imports every module so `Base.metadata` is complete.

### Constraints (database-level, not convention)
- `UNIQUE(agent_target_id, revision_no)` and `UNIQUE(agent_target_id, config_hash)`
- `UNIQUE(evaluator_id, revision_no)` and `UNIQUE(content_hash)`
- `UNIQUE(evaluation_plan_id, plan_item_id, repetition_no)`
- `UNIQUE(call_run_id, attempt_no)` and `UNIQUE(call_attempt_id, sequence_no)`
- `UNIQUE(source, provider_event_id)` for provider deduplication
- CHECK constraints on every status/enum column, `repeat_count >= 1`,
  `kind=benchmark => benchmark_version_id IS NOT NULL`, and the
  `metric_result` value-representation contract.
- JSONB for evaluator content, capability maps, snapshots, payloads, judge
  output; PostgreSQL `TIMESTAMPTZ` for all timestamps.

### Immutability guards (`db/guards.py`)
Service-level guards (backed by DB constraints where practical) against mutation
of executed/approved evaluator revisions, frozen benchmark versions, execution
manifests, raw runtime events, and original media artifacts.

### Repositories (`db/repositories/`)
Async SQLAlchemy 2 repositories: `TargetRepository`, `EvaluatorRepository`,
`BenchmarkRepository`, `EvaluationPlanRepository`, `CallRunRepository`,
`CallAttemptRepository`, `RuntimeEventRepository`, `MetricRepository`,
`JudgeRepository`, `ResultRepository`. Business logic stays out of these — they
perform domain operations and never leak models into the API layer.

### Alembic migration
- `alembic/versions/0002_domain_model.py` — creates all 32 tables, constraints,
  indexes, and the circular `call_run.selected_attempt_id` FK (separate
  `ALTER TABLE`). Hand-written to mirror the models exactly.

### Decisions
- `docs/decisions/0001-persistence-layer-decisions.md` — ULID-vs-UUID keys,
  evaluator `rejected` preservation, `metric_result.value_type` denormalization,
  attempt lifecycle/terminal-class split, bare ULIDs for prefix-less entities.

## Verification (all passing)
```bash
uv run pytest                # 56 passed (19 prior + 37 new)
uv run alembic upgrade head  # applied 0001 -> 0002
uv run alembic downgrade -1  # clean rollback
uv run alembic upgrade head  # re-applied
uv run alembic check         # No new upgrade operations detected (schema == metadata)
```
A live-Postgres repository smoke test (target → revision → evaluator → plan →
run → attempt → event → metric → evidence → aggregate) succeeded and was rolled
back, leaving no data behind.

## Deferred to later prompts
- Prompt 3: REST API, endpoint-config validation, capability negotiation,
  validation worker, benchmark freeze/approve flows.
- Prompt 4: plan preparation, manifest construction, ARQ orchestration.
- Prompt 5: runner WebSocket + runtime event ingestion.
- Prompt 6: CallRunner + target adapters + Pipecat caller.
- Prompt 7: metrics, judges, aggregation, results, forensics.
