# Prompt 3 — REST API + Validation + Capability Negotiation: Progress

## Status: Complete

The configuration, evaluator and benchmark API surfaces are implemented along
with asynchronous validation, the capability matrix and idempotency.

## What was built

### Adapter registry (`runtime/adapters/`)
Versioned registry that rejects unknown adapters at target-revision creation.
Seeded with `fake@1.0.0` and `websocket@1.0.0` (WebRTC stays interface-only).

### Capability matrix (`services/capabilities.py`)
- Flattens a nested capability snapshot into canonical keys
  (`target_text_stream`, `tool_calls`, `target_input_transcript`, …).
- `MetricRequirement` rules for the 11 documented metrics.
- `negotiate()`: required metric with a missing capability → BLOCKING; optional
  metric with a missing capability → warning + `NOT_AVAILABLE` (never zero).

### Pydantic schemas (`schemas/`)
Request/response contracts for targets, target revisions, evaluators, evaluator
revisions, benchmarks and benchmark versions. SQLAlchemy models never leak into
the API layer.

### Services (`services/`)
- `TargetService` — revision creation validates the endpoint config (raw secrets
  rejected, secret references allowed), the adapter, the capability snapshot, and
  derives a stable `config_hash`.
- `EvaluatorService` — revision creation produces `DRAFT`; `request_validation`
  moves `DRAFT → VALIDATING`, records a job and enqueues it (never inline);
  `approve` enforces `VALIDATED → APPROVED`.
- `BenchmarkService` — version create/list and freeze (draft-only).
- `IdempotencyService` — reserves an `Idempotency-Key`, rejecting duplicates.

### Validation worker (`services/validation/`)
Nine independent validators (schema, scenario, motive, state, success
conditions, behaviour, language, criteria, capabilities) aggregated into a
`ValidationReport`. The ARQ job `validate_evaluator_revision`
(`workers/jobs/validation.py`) runs them, persists the report and advances the
revision `VALIDATING → VALIDATED` (pass) or `→ DRAFT` (error).

### ARQ (`workers/arq.py`)
Registered `validate_evaluator_revision` and added `enqueue_validation`, wired to
the validation queue.

### API routes (`api/routes/`)
`targets`, `evaluators` + `evaluator-revisions`, `benchmarks` +
`benchmark-versions` — full create/list/get plus `validate` (202) and `approve`
and `freeze`. State-changing endpoints require an `Idempotency-Key` header.

### Decisions
`docs/decisions/0002-api-validation-decisions.md` — v1 auth deferral, 409
idempotency semantics, adapter seeding, dual capability scopes, DRAFT fallback.

## Verification (all passing)
```bash
uv run pytest        # 79 passed (56 prior + 23 new)
uv run alembic check # unchanged (no schema change in Prompt 3)
```
- OpenAPI resolves all 15 new routes under `/api/v1`.
- Live-Postgres service smoke test (target → revision → evaluator → revision →
  validate → worker outcome → approve → benchmark → freeze) passed and rolled
  back cleanly.

## Deferred to later prompts
- Prompt 4: plan preparation, manifest construction, ARQ orchestration, plan
  execute/cancel/resume.
- Prompt 5: runner control WebSocket + runtime event ingestion.
- Prompt 6: CallRunner + target adapters + Pipecat caller.
- Prompt 7: metrics, judges, aggregation, results, forensics.
- Prompt 8: hardening (auth wiring, response-replay idempotency, security review).
