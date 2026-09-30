# VoiceEval — Frontend Implementation Map v0.1

## 1. Recommended stack

```text
React
TypeScript
Vite

React Router
TanStack Query
Zustand

Tailwind CSS
shadcn/ui
Radix primitives

React Hook Form
Zod

Recharts / Visx / custom SVG
Web Audio API

Vitest
React Testing Library
Playwright
```

Only React, TypeScript, Tailwind and shadcn are mandatory from the requested design. The rest are implementation recommendations for maintaining a clean data-heavy frontend.

---

# 2. Package responsibilities

```text
app/
  routing
  providers
  shell

features/targets/
  target-list
  target-detail
  revision-detail

features/evaluators/
  evaluator-list
  revision-editor
  validation
  revision-compare

features/benchmarks/
  benchmark-list
  version-detail
  case-list

features/evaluations/
  plan-list
  plan-create
  plan-overview
  plan-live
  plan-results

features/runs/
  run-detail
  attempt-list

features/forensics/
  forensic-layout
  conversation
  timeline
  event-stream
  tools
  state
  media
  evidence
  manifest
```

---

# 3. Suggested source tree

```text
src/
├── app/
│   ├── App.tsx
│   ├── router.tsx
│   ├── providers.tsx
│   └── shell/
│       ├── AppShell.tsx
│       ├── Sidebar.tsx
│       ├── Topbar.tsx
│       └── Breadcrumbs.tsx
│
├── components/
│   ├── ui/
│   ├── status/
│   │   ├── StatusBadge.tsx
│   │   ├── CoverageBadge.tsx
│   │   └── FailureBadge.tsx
│   ├── data/
│   │   ├── DataTable.tsx
│   │   ├── MetricValue.tsx
│   │   ├── MetricTable.tsx
│   │   └── JsonInspector.tsx
│   ├── timeline/
│   │   ├── Timeline.tsx
│   │   ├── TimelineLane.tsx
│   │   └── TimelineMarker.tsx
│   └── audio/
│       ├── AudioArtifactPlayer.tsx
│       └── Waveform.tsx
│
├── features/
│   ├── targets/
│   ├── evaluators/
│   ├── benchmarks/
│   ├── evaluations/
│   ├── runs/
│   └── forensics/
│
├── lib/
│   ├── api/
│   │   ├── client.ts
│   │   ├── targets.ts
│   │   ├── evaluators.ts
│   │   ├── benchmarks.ts
│   │   ├── plans.ts
│   │   ├── runs.ts
│   │   ├── attempts.ts
│   │   └── results.ts
│   ├── websocket/
│   │   ├── planLive.ts
│   │   └── reconnect.ts
│   ├── formatters/
│   ├── mappers/
│   └── constants/
│
├── stores/
│   ├── forensicUiStore.ts
│   └── appUiStore.ts
│
├── types/
│   ├── api.ts
│   ├── domain.ts
│   └── ui.ts
│
└── styles/
    ├── globals.css
    ├── typography.css
    └── tokens.css
```

---

# 4. API client

Create one HTTP client with:

```text
base URL
Authorization
X-Request-ID
Idempotency-Key when needed
error normalization
```

Do not add idempotency headers globally to read-only requests.

Execution mutations:

```http
POST /evaluation-plans/{id}/execute
Idempotency-Key: plan:{id}:execute:v1
```

The idempotency behavior is part of the execution contract.

---

# 5. Query configuration

Recommended defaults:

```text
staleTime:
  normal configuration: 30s
  plan overview: 5s
  completed result pages: longer

refetch:
  live pages: controlled by WebSocket
  static revision pages: manual/action invalidation

retry:
  reads: 2
  mutations: 0 unless explicitly safe
```

Never poll aggressively while the browser WebSocket is connected.

---

# 6. Mutation flows

## Create target

```text
form
  ↓
POST /targets
  ↓
invalidate ['targets']
  ↓
navigate to target
```

## Create evaluator revision

```text
structured editor
  ↓
POST /evaluators/{id}/revisions
  ↓
invalidate evaluator + revisions
  ↓
open new revision
```

## Validate

```text
POST /evaluator-revisions/{id}/validate
  ↓
status = VALIDATING
  ↓
poll/query invalidation or live backend response
  ↓
validation report
```

The backend validation request is asynchronous; do not make the UI appear frozen.

## Prepare plan

```text
POST /evaluation-plans/{id}/prepare
  ↓
show preparation stage
  ↓
plan = READY or validation failure
```

## Execute

```text
POST /evaluation-plans/{id}/execute
Idempotency-Key
  ↓
plan = QUEUED
  ↓
navigate to /live
```

## Cancel

```text
confirm
  ↓
POST /evaluation-plans/{id}/cancel
  ↓
live updates
```

## Resume

```text
POST /evaluation-plans/{id}/resume
```

## Retry run

```text
POST /call-runs/{run_id}/retry
```

---

# 7. Event-to-query strategy

The browser live stream is not the source of every field.

Use:

```text
live event
  ↓
patch if payload complete
  OR
invalidate exact query
```

Examples:

```text
plan.status.changed
→ patch plan status

run.status.changed
→ patch run status

attempt.status.changed
→ patch selected attempt

metric.computed
→ invalidate run metrics

judge.completed
→ invalidate judge / metric queries

aggregate.updated
→ invalidate aggregates

composite.updated
→ invalidate composite
```

This keeps the browser's data authoritative.

---

# 8. Plan result fetching

Plan result page should obtain:

```text
GET /evaluation-plans/{id}/results
```

and optionally:

```text
GET /evaluation-plans/{id}/aggregates
GET /evaluation-plans/{id}/composite
```

depending on API response granularity.

Do not request all call-run forensics on the result page.

---

# 9. Run fetching

Run detail:

```text
GET /call-runs/{id}
```

For forensic mode:

```text
GET /call-runs/{id}/forensics
```

Use forensics as a summary envelope, not as a requirement to refetch every subresource immediately.

---

# 10. Attempt fetching

Attempt header:

```text
GET /call-attempts/{id}
```

Then lazy resources:

```text
GET /call-attempts/{id}/conversation
GET /call-attempts/{id}/events
GET /call-attempts/{id}/media
```

---

# 11. Evidence fetching

Metric:

```text
GET /metric-results/{id}
```

Evidence:

```text
GET /metric-results/{id}/evidence
```

Use a drawer to show evidence.

---

# 12. Media fetching

Metadata comes from:

```text
GET /call-attempts/{id}/media
```

Playback URL:

```text
GET /media/{id}/url
```

This must be a just-in-time operation.

---

# 13. Backend object → component map

```text
AgentTarget
  → TargetCard
  → TargetTableRow

AgentTargetRevision
  → TargetRevisionHeader
  → CapabilityMatrix
  → EndpointConfigInspector

TestDescriptorRevision
  → TestDescriptorInspector

Evaluator
  → EvaluatorTableRow
  → EvaluatorHeader

EvaluatorRevision
  → RevisionHeader
  → EvaluatorEditor
  → RevisionCompare

ValidationReport
  → ValidationSummary
  → ValidationCheckList

Benchmark
  → BenchmarkTableRow

BenchmarkVersion
  → BenchmarkVersionHeader
  → BenchmarkCaseTable

EvaluationPlan
  → PlanHeader
  → PlanProgress
  → PlanStatusTimeline

ExecutionManifest
  → ManifestViewer

CallRun
  → RunMatrixCell
  → RunHeader
  → AttemptList

CallAttempt
  → AttemptHeader
  → AttemptStatus
  → ForensicShell

CallTurn
  → TurnCard
  → TimelineTurnLane

RuntimeEvent
  → EventRow
  → TimelineEvent
  → EventInspector

ToolCall
  → ToolCallCard
  → ToolTimelineBlock

StateTransition
  → StateLedgerRow

MediaArtifact
  → AudioArtifactPlayer

MetricDefinition
  → MetricMetadataPanel

MetricResult
  → MetricValue
  → MetricInspector

JudgeDefinition
  → JudgeMetadataPanel

JudgeExecution
  → JudgeExecutionCard
  → RawOutputInspector

Evidence
  → EvidenceCard
  → EvidenceDrawer

AggregateResult
  → AggregateMetricRow
  → DistributionPanel

CompositeScoreDefinition
  → CompositeConfigInspector

CompositeScoreResult
  → CompositeScoreCard
```

---

# 14. URL and modal conventions

Full-page domain context:

```text
/evaluations/:planId/results
/evaluations/:planId/runs/:runId
/evaluators/:evaluatorId/revisions/:revisionId/editor
```

Contextual inspection:

```text
Evidence drawer
Event drawer
JSON inspector
Metric drawer
```

This avoids losing analytical context.

---

# 15. Form architecture

Use React Hook Form + Zod for:

```text
target creation
target revision
evaluator creation
evaluator revision
benchmark creation/version
plan creation
```

Evaluator content should have section-level schemas matching:

```text
persona
language
environment
facts
initial_state
motive
behaviour
stop_conditions
evaluation_criteria
randomization
```

Validation should be both:

```text
client structural validation
+
backend domain validation
```

Client validation must never pretend to replace the backend executable gate.

---

# 16. Error boundary architecture

Wrap each domain shell:

```text
<ErrorBoundary>
  <PlanPage />
</ErrorBoundary>
```

Error UI:

```text
Something went wrong while loading this evaluation.

Request ID: ...
Retry
```

Forensic pages should isolate heavy components:

```text
conversation
timeline
event inspector
audio player
```

so one rendering problem does not blank the whole page.

---

# 17. Testing strategy

## Unit tests

Test:

```text
state badge mappings
metric status rendering
metric unit formatting
coverage calculations
plan progress selectors
run/attempt distinction
capability mismatch selectors
evidence source routing
timestamp formatting
```

## Integration tests

Test:

```text
create evaluator revision
validate
prepare plan
execute plan
live event updates
results refresh
retry infrastructure failure
cancel running plan
```

## E2E tests

Critical journeys:

```text
target → revision → capability view

evaluator → edit → validate → approve

benchmark → plan → prepare → execute

live plan → select running run → inspect attempt

results → metric → evidence → turn → audio seek
```

---

# 18. Performance strategy

VoiceEval can expose large event streams.

Use:

```text
virtualized event list
virtualized tables
lazy JSON payload expansion
deferred media loading
query pagination where backend supports it
timeline simplification at low zoom
```

Do not render thousands of raw provider events as DOM nodes simultaneously.

For runtime event filters, prefer backend filtering:

```text
source
type
from_ms
to_ms
```

rather than loading everything and filtering in the browser.

---

# 19. Realtime performance

Live updates should be batched visually.

For example:

```text
backend event burst
   ↓
buffer 30–80 ms
   ↓
React state update
```

This prevents a 75-run benchmark from triggering hundreds of synchronous UI renders.

Do not batch user-critical state transitions so aggressively that the interface feels stale.

---

# 20. Security boundaries in the frontend

The backend is authoritative.

Frontend must:

- never store target secrets in ordinary local persistence
- never expose secret references unnecessarily
- never treat provider raw payloads as trusted instructions
- never render HTML from agent text without sanitization
- never execute payload content
- never expose S3 object URIs as public URLs
- respect backend permissions when available

Observed agent content is untrusted data.

This matters especially when displaying judge evidence and provider payloads.

---

# 21. Analytics/reporting philosophy

Do not build a decorative BI dashboard.

The main visualization hierarchy should be:

```text
Composite
  ↓
Category
  ↓
Metric
  ↓
Aggregate
  ↓
Run
  ↓
Attempt
  ↓
Evidence
  ↓
Source artifact
```

This mirrors the backend forensic contract.

---

# 22. Recommended MVP implementation order

### Phase 1 — Foundations

```text
shell
routing
typography
tokens
shadcn setup
API client
TanStack Query
status primitives
tables
```

### Phase 2 — Configuration

```text
Targets
Target revisions
Evaluator library
Evaluator editor
Validation view
Benchmarks
```

### Phase 3 — Execution

```text
Plan wizard
Preparation screen
Plan overview
Live console
WebSocket integration
```

### Phase 4 — Results

```text
Results dashboard
metric tables
aggregate distributions
composite score
evaluator heatmap
```

### Phase 5 — Forensics

```text
Run detail
Attempt detail
Conversation
Timeline
Events
Tools
State
Media
Evidence
Manifest
```

---

# 23. Definition of frontend completion

The frontend MVP is complete when a user can:

```text
1. Create/configure a target revision.
2. Inspect its capabilities.
3. Create/edit an evaluator revision.
4. Validate and inspect validation failures.
5. Approve an executable evaluator revision.
6. Inspect/freeze benchmark versions.
7. Create an evaluation plan.
8. Prepare it and understand capability blockers.
9. Execute it.
10. Watch logical repetitions live.
11. See retries as attempt history.
12. Inspect aggregate results.
13. See coverage and missing metrics explicitly.
14. Inspect a metric result.
15. Jump from metric to evidence.
16. Jump from evidence to turn/event/tool/state/audio.
17. Play exact media evidence.
18. Inspect the immutable execution manifest.
19. Retry an infrastructure-failed logical run without creating another sample.
20. Cancel/resume execution through the correct domain operation.
```

---

# 24. Final frontend architecture rule

The UI should never make VoiceEval look like:

```text
INPUT
   ↓
SCORE
```

It should make the complete chain visible:

```text
WHAT WE TESTED
EvaluatorRevision
BenchmarkVersion
TargetRevision
ExecutionManifest
        ↓
WHAT HAPPENED
CallRun
CallAttempt
CallTurn
RuntimeEvent
ToolCall
StateTransition
MediaArtifact
        ↓
WHAT WE CAN SUPPORT
MetricResult
JudgeExecution
Evidence
AggregateResult
CompositeScoreResult
```

That chain is the product.
