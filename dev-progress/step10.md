# Step 10 — Frontend v0.4 (Simulations, Runs & Generation): Progress

## Status: Complete (config + generation); results/live/forensics deferred

Rewrote the Resona frontend around the v0.4 domain model and the two AI
generation workflows, matching the backend config+generation milestone in
Step 9. Removed the v0.3 evaluator/plan surface and replaced it with a
**Simulations → Runs → RunEvaluators** flow.

## What changed

### Navigation / IA
- Removed the **Evaluators** and **Evaluations** tabs; added **Simulations**.
- `primaryNav`: Overview / Simulations / Benchmarks / Targets.
- Router rewritten: `/simulations`, `/simulations/new`,
  `/simulations/:simulationId`, `/runs/:runId`, plus kept `/benchmarks` and
  `/targets`.
- Updated `OverviewPage`, `Breadcrumbs`, `CommandPalette` copy.

### Types, constants, API layer
- `types/api.ts` + `types/domain.ts` rewritten to v0.4: added
  `SimulationDto`, `RunDto`, `RunEvaluatorDto`, generation DTOs; kept leaf
  runtime/forensic DTOs/VMs; removed v0.3 evaluator/plan/result types.
- New constants: `metrics.ts` (v0.4 catalogue), `personalities.ts`,
  `backgrounds.ts`, `languages.ts`; deleted `validation.ts`.
- New API clients: `lib/api/simulations.ts`, `lib/api/runs.ts`,
  `lib/api/generation.ts`; `lib/queryKeys.ts` rewritten; `lib/mappers/index.ts`
  trimmed to leaf mappers; deleted `plans/evaluators/testDescriptors.ts` +
  `websocket/planLive.ts`.
- New `components/forms/ChipGroup.tsx` (toggleable multi-select chips).

### Features
- `features/simulations/` — list page; 3-step create wizard (Describe →
  Preferences with Workflow-A suggestion + hand-adjustable chips → Review);
  overview page (config + runs + "new run" target/revision picker).
- `features/runs/` — run detail (status + evaluators table), "Generate
  evaluations" dialog (captures a `SimulationWorkflowSpec` → Workflow B),
  evaluator editor dialog (PATCH), and "Mark ready" action.

### Deleted v0.3 code
- `features/{evaluations,evaluators,live,results,forensics}` and the old
  `features/runs`; `lib/api/{plans,evaluators,testDescriptors}.ts`,
  `lib/websocket/planLive.ts`, `lib/constants/validation.ts`,
  `components/status/CompositeScoreCard.tsx`, and stale tests
  (`mappers.test.ts`, `live.test.ts`, `contentSchema.test.ts`).

### Benchmarks fix
- `features/benchmarks/cases.ts` + `BenchmarkVersionPage.tsx` + `cases.test.ts`
  now read `case_definition` instead of the removed `evaluator_revision_id`.

## Verification (all passing)
```bash
cd frontend
npm run build   # tsc -b && vite build — clean
npm test        # 19 passed (5 files)
```

## Deferred (separate pass, matches backend Step 9 deferral)
- Results, live console, forensics, metric inspector — re-keyed to
  `run`/`run_evaluator` once the backend execution/results pipeline is migrated.
- `CallRun`/`CallAttempt`/`ExecutionManifest` frontend types for the new
  `run_id`/`run_evaluator_id`/snapshot shape.

## Manual run instructions
- Backend: `cd backend && uv run uvicorn voiceeval.main:app --reload` (or via
  `scripts/run_workers.py` / Docker) with Postgres migrated to `0006`.
- Frontend: `cd frontend && npm run dev` (Vite; `VITE_API_BASE_URL` default
  `/api/v1`, proxied to the backend).
- Flow: create a target + revision → `/simulations/new` (Describe → Suggest
  preferences → adjust → Create) → simulation overview → New run (target +
  revision) → run detail → Generate evaluations → edit → Mark ready.
