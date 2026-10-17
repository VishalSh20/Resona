# Frontend — Add Simulation Flow: Progress

## Status: Complete — frontend built and verified against a live rebuilt backend.

Implemented `docs/V2-changes/resona_add_simulation_frontend_spec.md` as a polished
multi-step wizard, and propagated the backend's `backgrounds → call_ambience` /
`run_evaluator.background` removal across the whole frontend.

## Flow

```text
Target(0) → Configuration(1) → [preference generation loader] → Personas(2)
          → Metrics(3) → Review(4) → Evaluators(5)
```

The preference-generation loader is an internal transition, not a step.

## What was built

### Wizard (`features/simulations/wizard/`)
- `SimulationFormShell` — header + `StepIndicator`, content card, sticky action
  bar (reachable however long the form gets).
- `StepIndicator` — 6 steps on `md+`, compact "Step n of 6" below.
- `SimulationTargetStep` — name, agent cards (provider logo + provider name),
  version `Select`, fixed-height description textarea. Empty state when the
  agent has no revisions.
- `SimulationConfigurationStep` — evaluator count (`NumberInput`, 1–100),
  language cards (typographic code, no flags), call-ambience cards.
- `PreferenceGenerationLoader` — centered sparkle + rotating messages every
  1.2s (`Making evaluation preferences… / Choosing helpful metrics… / Finding
  relevant personas… / Preparing your evaluation…`), fade/slide, plus the
  error + **Try again** state.
- `PersonaSelectionStep` / `MetricSelectionStep` — persona cards and
  family-grouped metric cards, each with name + short description.
- `SimulationReviewStep`, `SimulationEvaluatorsStep` — existing review summary
  and evaluator-generation form.
- `types.ts` — `SimulationDraft`, `EvaluatorWorkflowDraft`, step constants,
  `isEvaluatorCountValid`.
- `SimulationCreateWizardPage` — orchestrates draft state, per-step validation,
  preference call, create, and generation. Data persists across Back/Continue;
  duplicate submits are blocked while async work runs.

### Reusable primitives
- `components/forms/SelectableCard` — border/ring selected state (`border-foreground
  ring-1 ring-foreground/15`) + check icon, never a filled background; single
  keyboard-accessible toggle button (`aria-pressed`).
- `components/forms/SelectionGrid` — `repeat(auto-fit, minmax(min(100%, Npx), 1fr))`
  so grids wrap and never force horizontal overflow.
- `components/forms/ChipGroup` — selected state converted to the same
  border/ring treatment (applies to the run evaluator editor too).
- `components/brand/ProviderLogo` — official brands via `simple-icons`
  (ElevenLabs, LiveKit, Pipecat); Vapi/Retell fall back to a generic Lucide icon.

### Backend preference call
Reused the existing `POST /generation/simulation-preferences` endpoint and
`SimulationPreferencesRequest/Response` DTOs (`available_metrics` /
`available_personalities` in, `metrics` / `personalities` out). Recommended
metrics + personas are auto-selected and remain user-editable. New
`useSimulationPreferences` hook in `features/simulations/queries.ts`.

## Schema propagation (backend already migrated; frontend was stale)

- `types/api.ts` — `SimulationDto.backgrounds → call_ambience`;
  `RunEvaluatorDto.background` removed, `scenario_config` added.
- `lib/constants/backgrounds.ts` (caller profiles) **deleted**; replaced by
  `lib/constants/ambience.ts` (`CALL_AMBIENCE_OPTIONS` mirroring the backend
  `CallAmbience` enum: QUIET, NOISY, PEOPLE_TALKING, MUSIC, TRAFFIC, OFFICE,
  CALL_CENTRE, CAR).
- `lib/api/simulations.ts` + `lib/api/runs.ts` inputs updated.
- `SimulationOverviewPage` renders call ambience; `SimulationListPage` copy
  updated.
- `RunDetailPage` — dropped the per-evaluator Background column/editor (the
  column no longer exists server-side); "only personality" copy.
- `features/benchmarks/{cases.ts,cases.test.ts,BenchmarkVersionPage.tsx}` —
  removed the stale case `background` field (benchmark case definitions are
  RunEvaluator-compatible and no longer carry it).
- Metrics and personalities catalogs gained `description` fields for the cards.

## Dependencies

- Added `simple-icons` (brand marks). Tree-shaken — production bundle 682 kB
  (gzip 208 kB).

## Verification

```bash
npm run build   # tsc -b && vite build — clean
npm test        # 22 passed (incl. new wizard validator + ambience parity)
npm run dev     # serves; wizard + ProviderLogo modules transform (200)
```

## Live end-to-end verification

The api/worker images were rebuilt and the DB migrated to head (0011 → 0013).

```bash
docker compose up -d --build api worker
docker compose exec api alembic upgrade head   # 0011 → 0012 → 0013
```

Live OpenAPI now matches the frontend DTOs: `SimulationCreate` exposes
`call_ambience` (no `backgrounds`); `RunEvaluatorRead` exposes `scenario_config`
(no `background`).

API smoke test (`register → targets → create simulation → preferences`):

```text
auth: 201
targets: 200 count= 2
revisions: 200 count= 1
create simulation: 201
  call_ambience echoed: ['QUIET', 'NOISY']
  has 'backgrounds' key: False
  first run id: run_01M43W3NZ201Y2NQ96YF0MAZWT
preferences: 200
  body: {'metrics': ['task_completion', 'relevancy', 'context_retention'],
         'personalities': ['IMPATIENT', 'CONFUSED']}
```

Left a `sim-smoke@example.com` user and a "Frontend smoke simulation" row in the
dev DB from the smoke test (no simulation-delete endpoint to clean up with).

## Assumptions / deviations

- Kept a **Name** field on Target: the backend requires `simulation.name`, and
  the spec's Page 1 omits it. Preferred the simplest implementation consistent
  with the existing UI.
- Treated the spec's "personas" as the backend `personalities` (single source of
  truth; no duplicate domain model introduced).
- Language cards use a typographic code (`EN`, `HI`) or a `Languages` icon — no
  country flags.

## Follow-up — Run page action states

`RunDetailPage` now derives its actions purely from run status:

- **draft** (created, never executed) → **Mark ready** (disabled while it has no
  evaluators or the transition is in flight).
- **ready** (never executed, cleared to run) → **Run** button (placeholder; its
  wiring to `POST /runs/{id}/start` is deferred).
- **executed** (`queued` / `running` / `partial` / `completed` / `cancelled`) →
  no action buttons; the page is view-only.

Removed the "Generate evaluations" button + its mutation/error surface from the
run page (evaluators are generated by the Add Simulation flow). The evaluator
editor is unchanged.
