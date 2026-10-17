# Frontend — Phases 3–5 + Auth: Progress

## Status: Complete

Phases 3 (Execution), 4 (Results) and 5 (Forensics) are implemented against the
live backend, real sign-up/sign-in was added, and the frontend was sewn to the
backend contract (DTOs + mappers). Every route that previously rendered a
placeholder for evaluations is now a real page.

## What was built (under `frontend/`)

### Auth
- `features/auth/` — `SignInPage`, `SignUpPage`, `useAuth` (sign in/up/out +
  session bootstrap + 401 handling), `RequireAuth` guard; `stores/sessionStore`.
- `lib/api/auth.ts`; token storage in `lib/api/client.ts` (401 emits an event).
- Router: `/signin`, `/signup` outside the shell; the app is guarded.

### Execution (Phase 3)
- `features/evaluations/` — `queries.ts`, `PlanListPage`, `PlanCreateWizardPage`
  (scope → target+capabilities → evaluators/cases → repeats → prepare),
  `PlanOverviewPage` (segmented `ProgressBar`, status counts, runs/items tabs),
  `PlanRunsPage`, `PlanManifestPage`.
- `lib/websocket/{planLive,reconnect}.ts` + `features/live/` — `usePlanLive`,
  `applyLiveEvent` (reducer that patches/invalidates the query cache),
  `RepetitionMatrix`, `PlanLivePage` with a connection indicator and status
  stream. The browser WebSocket is observation-only.

### Results (Phase 4)
- `features/results/` — `PlanResultsPage` (composite card, coverage, category
  cards, metric aggregate table, `EvaluatorHeatmap`) and `MetricInspectorPage`
  (value/status/method, measurement basis, evidence with navigation).

### Forensics (Phase 5)
- `features/runs/` — `queries.ts`, `RunDetailPage` (attempt lineage, run metrics,
  retry infrastructure failure).
- `features/forensics/` — `queries.ts`, `ForensicsPage` (header facts, timeline +
  audio, conversation | event stream | inspector, evidence), `stores/forensicUiStore`.
- Components: `Timeline`, `AudioArtifactPlayer` (signed URL, evidence seek),
  `TurnCard`, `ToolCallCard`, `StateTransitionRow`, `EventRow`.

### Backend seam
- `types/api.ts` extended with snake_case DTOs; `lib/mappers/` maps them to the
  camelCase view models. `lib/api/{plans,runs,results,attempts,media,auth,testDescriptors}.ts`
  rewritten accordingly (fixes the events/conversation shape bugs).
- `lib/queryKeys.ts` centralises the key structure shared by hooks and the live
  reducer.

## Backend changes this work depended on

Documented in `docs/decisions/0008` and `0009`:
- multi-queue ARQ worker launcher (nothing executed before);
- duplicate content/config hash → 409;
- sign-up/sign-in;
- read endpoints: plan runs, run attempts, run retry, manifest, event filters,
  `plan.created_at`, richer attempt/turn fields, test-descriptor endpoints;
- benchmark cases materialized from the manifest;
- plan completion no longer gated on evaluation eligibility;
- media bytes persisted to the object store; fake target made per-connection;
- `RUNNER_DISPATCH_MODE` + standalone fake target.

## Verification

```bash
# frontend
npm run build        # clean
npm test             # 33 passed (status, formatters, capabilities, target
                     #   config, evaluator schema, benchmark cases, mappers, live reducer)
# backend
uv run pytest        # 328 passed
uv run alembic upgrade head   # 0005
docker compose config         # OK
```

Live end-to-end (real HTTP API + multi-queue workers + inline runner + fake
target), 32/32 checks: register/login/me · 409s · target+revision · evaluator
revision · async validation via worker · approve · test descriptor · plan
create/prepare/execute · 2 logical runs completed · metrics · judges ·
aggregation · composite (INCOMPLETE with coverage + missing metrics) · results ·
manifest · runs/attempts · forensics turns+events · conversation state
transitions · event filters · media signed URL · metric evidence.

## Known limitations / deviations

- No audio waveform rendering — a functional `<audio>` player with an evidence
  seek range instead.
- Tables are not virtualized; the forensic event stream shows the first N with a
  filter-driven cap rather than paging the whole set.
- The timeline is a fixed-scale lane view (no zoom/pan).
- The plan wizard creates test descriptors/source text inline; it does not offer
  a generator (the backend schema allows one).
- Composite is INCOMPLETE when judge-backed metrics are unavailable (e.g. no
  `OPENAI_API_KEY`) — this is correct, not a bug.
