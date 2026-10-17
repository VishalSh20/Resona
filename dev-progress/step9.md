# Step 9 — v0.4 Config + Generation Flow (Milestone 1): Progress

## Status: Complete (config + generation); results/execution + frontend deferred

This pass finishes the backend **configuration + AI-generation** flow of the
v0.4 migration. The v0.4 domain model (`Simulation → Run → RunEvaluator`) and the
two generation workflows were already largely implemented; this pass completed
the lifecycle, cleaned up the superseded v0.3 config layer, fixed a mounted-but-
broken benchmark path, and made the test suite green for the milestone.

The **results / execution** pipeline and the **frontend** are deliberately out of
scope here and are listed under "Deferred" below.

## What already existed (v0.4, done before this pass)

- Migration `0006` (Simulation / Run / RunEvaluator / CallRun / CallAttempt +
  run-scoped result tables).
- Models (`db/models/domain.py`), enums (`RunStatus`, `Personality`,
  `Background`, `MetricKey`), run state machine (`RUN_TRANSITIONS`).
- Generation: `generation/` Workflow A (`SimulationPreferencesWorkflow`) +
  Workflow B (`EvaluationsWorkflow`) + registries + deterministic validation;
  `llm/` provider abstraction (OpenAI/Anthropic/OpenRouter) + Jev decision model.
- Config services/repos: `SimulationService`, `RunService`, `SimulationRepository`,
  `RunRepository`, `RunEvaluatorRepository`.
- Mounted routes: auth / targets / simulations / run_evaluators (`/runs`) /
  benchmarks / generation.

## What this pass changed

### Completed the run lifecycle
- `RunService.mark_ready()` — validates the run exists and has ≥1 evaluator, then
  transitions `draft → ready` via `RunRepository.transition_run` (state machine).
- `POST /api/v1/runs/{run_id}/ready` route.

### Fixed the benchmark-case regression (mounted surface)
- `BenchmarkRepository.add_case` now takes `case_definition` (JSONB) instead of
  the removed `evaluator_revision_id`.
- `services/benchmarks.parse_manifest_cases` now reads a RunEvaluator-compatible
  `case_definition` (explicit object or inline `scenario` /
  `expected_output_prompt` / `metrics` / `languages` / `background` /
  `personality`).

### Added tests for the config + generation layer
- `tests/test_simulations.py` — SimulationService + `SimulationCreate` bounds.
- `tests/test_runs.py` — create_run, generate_evaluators (stubbed workflow),
  update_evaluator membership/editable guards, mark_ready guards + transition.
- `tests/test_generation_api.py` — Workflow A route (success + validation + auth),
  Workflow B route validation + 404, mark-ready 404, `POST /simulations` 201/422.

### Deleted superseded v0.3 config files
- `schemas/{evaluators,plans,test_descriptors}.py`
- `services/{evaluators,plans,test_descriptors}.py`
- `api/routes/{evaluators,plans,test_descriptors}.py`
- `db/repositories/{evaluators,plans,test_descriptors}.py`

### Deleted stale/deferred v0.3 tests
`test_plans.py`, `test_services.py`, `test_validators.py`,
`test_orchestration.py`, `test_results.py`, `test_evaluation_wiring.py`,
`test_frontend_enablers.py`, `test_workers.py`.

### Repaired partial tests
- `test_state_machines.py` → Run + CallRun + Attempt transitions (dropped
  evaluator/plan).
- `test_guards.py` → dropped `ensure_evaluator_revision_mutable` (removed).
- `test_domain_models.py` → v0.4 table set + asserts removed tables are absent.
- `test_realtime.py` → dropped the one v0.3 orchestrator test.
- `test_benchmark_cases.py` → `case_definition` shape.
- `test_api_auth.py` → auth checks point at mounted routes; blob test skipped.
- Quarantined 14 deferred result-part tests (metrics/judges/capabilities/
  evaluation-pipeline) with `pytest.mark.skip(reason="deferred …")`.

### Kept the deferred execution/results modules import-safe
- `aggregation/__init__.py` lazily re-exports `AggregationEngine` /
  `AGGREGATION_VERSION` (PEP 562) so pure aggregation tests don't require the
  run-scoped engine.
- `orchestration/terminal.py` imports `ExecutionOrchestrator` lazily.
- (`aggregation/engine.py`, `orchestration/*`, `metrics/engine.py`,
  `judges/engine.py`, `runtime/loader.py`, `workers/*`, `services/results.py`,
  `api/routes/results.py`, `api/routes/runs.py`, `schemas/results.py` remain as
  the deferred results/execution layer — not re-keyed yet.)

## Verification (all passing)

```bash
cd backend
uv run pytest                 # 281 passed, 15 skipped
uv run alembic upgrade head   # applied 0005 -> 0006
uv run alembic check          # No new upgrade operations detected
```

The 15 skips are the deferred result/execution tests (removed v0.3 metric
catalogue, `JudgeEngine`, the full result chain) plus the signed media-blob route
(test re-added in the results pass).

Live smoke against real Postgres + real OpenAI (Workflow A) and real Jev
(Workflow B), `evaluator_count=1`:

- Workflow A selected: metrics `[context_retention, instruction_following,
  empathy, task_completion, code_switching_accuracy]`, personalities
  `[SUPPORTIVE, COOPERATIVE, IMPATIENT, DEMANDING, SKEPTICAL, EMOTIONAL]`.
- Simulation + Run created; Workflow B generated 1 RunEvaluator with a realistic
  scenario and a metric-grounded judge prompt; edit + `mark_ready` (`ready`) OK.

## Deferred (next passes)

1. **Results / execution pass** — re-key `CallRunRepository`, `ResultRepository`,
   `orchestration/*`, `metrics|judges|aggregation` engines, `runtime/loader.py`,
   `workers/*`, retry (`/call-runs/{id}/retry`), and results/forensics routes to
   `run` / `run_evaluator`; rewrite `scripts/smoke_e2e.py`; restore the quarantined
   tests.
2. **Frontend pass** — rewrite `frontend/src` types/api/mappers/features/routing
   to Simulation / Run / RunEvaluator + the generation endpoints; update
   `docs/frontend/00/01/02`.

## What you may still need to do
- Run `uv run alembic upgrade head` on any other environment (the local DB was at
  `0005` and has now been migrated to `0006`; 0006 is a breaking, non-additive
  migration that drops the v0.3 tables).
