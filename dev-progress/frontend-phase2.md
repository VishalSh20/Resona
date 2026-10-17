# Frontend — Phase 2 (Configuration): Progress

## Status: Complete

Targets, target revisions, the evaluator library/editor/validation view, and
benchmarks are implemented against the backend contract.

## What was built (under `frontend/`)

### Targets
- `TargetListPage` — table with provider, latest revision, transport, and
  observable-capability count (per-target revision queries).
- `TargetCreatePage` — React Hook Form + Zod.
- `TargetOverviewPage` — target metadata, latest revision, revision list.
- `TargetRevisionCreatePage` — transport/adapter select, endpoint-config JSON
  (with a client mirror of the backend raw-secret guard), and a structured
  capability-snapshot editor; posts with an `Idempotency-Key`.
- `TargetRevisionPage` — tabs: Overview / Connection / Capabilities /
  Configuration / Revision history.

### Evaluators
- `EvaluatorListPage`, `EvaluatorCreatePage`, `EvaluatorOverviewPage`.
- `EvaluatorRevisionEditorPage` — two-pane structured editor (Scenario,
  Language, Environment, Facts, Initial state, Motive, Behaviour, Stop
  conditions, Criteria, Randomization) plus a Raw JSON mode; saving creates a
  **new** revision (never mutates the source); Validate/Approve actions; content
  seeding is idempotent so a background status poll cannot clobber edits.
- `EvaluatorValidationPage` + `ValidationCheckList` — summary and per-check
  results (PASS/WARNING/ERROR) from the validation report.

### Benchmarks
- `BenchmarkListPage`, `BenchmarkCreatePage`, `BenchmarkOverviewPage`.
- `BenchmarkVersionCreatePage`, `BenchmarkVersionPage` — header with FROZEN
  indicator, cases read from the version manifest, manifest inspector, freeze.

### Shared layer
- Domain components: PageHeader, CopyableId, HashBadge, ImmutableBadge,
  JsonInspector, MetaList, CapabilityMatrix, Loading/Error/Empty states.
- Form helpers: FormField, StringListInput, KeyValueEditor, NumberInput.
- TanStack Query hooks per feature with the documented key structure.
- Evaluator content model (`features/evaluators/content.ts`) and a client
  structural Zod schema (`contentSchema.ts`).
- Constants: metrics, capabilities (+ affected-metric inverse), validation
  labels, adapters.
- Additional shadcn primitives: select, switch, tabs, textarea, label.

### Backend enabler
The validation report was persisted but never exposed, so the Validation view
had no data source. Added an additive read endpoint:
`GET /api/v1/evaluator-revisions/{revision_id}/validation-report`
(repository method + `ValidationReportRead`/`ValidationCheckRead` schema +
service method + route). No domain semantics changed.

## Verification
```bash
# frontend
npm run build   # clean
npm test        # 23 passed (status, formatters, capabilities, target config,
                #             evaluator content schema, benchmark cases)
# backend
uv run pytest   # 131 passed
# live end-to-end (local API against dockerized Postgres/Redis, cleaned up after)
target -> revision (raw secret rejected 400) -> evaluator -> revision
  -> validate (202) -> worker outcome -> validation-report 200
  valid content   -> revision validated, report passed  (0 blocking)
  invalid metric  -> revision draft,     report failed  (1 blocking: capability_validity)
benchmark -> version -> freeze (frozen)
```

## Known limitations / deviations
- The evaluator content editor operates on the backend's snake_case wire shape
  (validated by the backend validators) rather than mapping to a camelCase view
  model, so what is saved is exactly what is validated.
- Evaluator and benchmark lists derive "latest revision/version" via per-parent
  queries; there is no enriched list endpoint yet.
- Benchmark cases are read from the version manifest's `cases` array; there is
  no cases endpoint.
- Client validation is advisory; the backend remains the executable gate.

## Pre-existing backend issues discovered (not introduced here)
1. **ARQ queue mismatch** — jobs are enqueued to `voiceeval:queue:validation` /
   `voiceeval:queue:execution`, but `WorkerSettings` sets no `queue_name`, so the
   worker consumes ARQ's default `arq:queue`. Named-queue jobs are therefore
   never consumed (confirmed via Redis keys); validation/execution never
   complete in a running system. Blocks the live Validation view.
2. **Duplicate `content_hash` → 500** — `UNIQUE(content_hash)` is global, so
   saving two revisions with identical content returns
   `500 INTERNAL_ERROR` instead of a `409 CONFLICT`.

## Deferred to later phases
- Phase 3 — Plan wizard, preparation, plan overview, live console, WebSocket.
- Phase 4 — Results dashboard, metric tables, aggregates, composite, heatmap.
- Phase 5 — Run/attempt detail, conversation, timeline, events, tools, state,
  media, evidence, manifest (forensics).
