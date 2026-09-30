# VoiceEval — Frontend Product Architecture v0.1

## 0. Purpose

This document defines the frontend information architecture and application model for VoiceEval.

The frontend is a React + TypeScript application using:

- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Router
- TanStack Query for server state
- Zustand for narrowly scoped client/UI state
- WebSocket for plan-level live observability
- Web Audio APIs for waveform/playback controls
- CSS variables for the visual system
- A custom typography pairing for product identity

The frontend is not a second runtime. It is a **control, observability, analysis, and forensic interface** over the backend contract.

The backend architecture explicitly separates test truth, observed truth, and evaluation truth. The frontend must preserve that separation rather than flattening all data into a single score dashboard.

---

## 1. Product mental model

VoiceEval should feel like a laboratory for voice-agent behavior.

The user's conceptual journey is:

```text
Configure target
      ↓
Author evaluator
      ↓
Validate evaluator
      ↓
Assemble benchmark / plan
      ↓
Prepare execution contract
      ↓
Run repetitions
      ↓
Observe live execution
      ↓
Inspect results
      ↓
Trace score → evidence → event/turn/tool/audio
```

The three truths are represented consistently:

```text
TEST TRUTH
Evaluator revision
Benchmark version
Execution manifest

OBSERVED TRUTH
CallRun
CallAttempt
CallTurn
RuntimeEvent
ToolCall
StateTransition
MediaArtifact

EVALUATION TRUTH
MetricResult
JudgeExecution
Evidence
AggregateResult
CompositeScoreResult
```

The backend explicitly states this hierarchy and requires dashboards to retain the provenance chain.

---

## 2. Top-level information architecture

### Primary navigation

```text
┌─────────────────────────────────────────────────────────────┐
│ VoiceEval                                                   │
│                                                             │
│ Overview                                                    │
│ Evaluations                                                 │
│ Evaluators                                                  │
│ Benchmarks                                                  │
│ Targets                                                     │
│                                                             │
│ ─────────────────────────────────────────────────────────── │
│ Recent plans                                                │
│ Favorite targets                                            │
│                                                             │
│ [workspace/user menu]                                       │
└─────────────────────────────────────────────────────────────┘
```

### Why this structure

The backend has five API surfaces:

1. Configuration
2. Evaluator
3. Execution
4. Runtime/runner
5. Result/forensics

The UI maps them into human-facing workflows rather than mirroring those API surfaces literally.

| Product area | Primary backend objects |
|---|---|
| Overview | EvaluationPlan, AggregateResult, CompositeScoreResult, recent CallRuns |
| Evaluations | EvaluationPlan, EvaluationPlanItem, ExecutionManifest |
| Evaluators | Evaluator, EvaluatorRevision, ValidationReport |
| Benchmarks | Benchmark, BenchmarkVersion, BenchmarkCase |
| Targets | AgentTarget, AgentTargetRevision |
| Plan runtime | CallRun, CallAttempt, live events |
| Result analysis | MetricResult, AggregateResult, CompositeScoreResult, JudgeExecution |
| Forensics | CallAttempt, CallTurn, RuntimeEvent, ToolCall, StateTransition, MediaArtifact, Evidence |
| Reproducibility | ExecutionManifest, revision hashes, model/runtime versions |

---

## 3. Route tree

Use route names that reflect domain operations and user intent.

```text
/
├── /evaluations
│   ├── /new
│   └── /:planId
│       ├── /overview
│       ├── /live
│       ├── /results
│       ├── /runs
│       └── /manifest
│
├── /evaluators
│   ├── /
│   ├── /new
│   └── /:evaluatorId
│       ├── /overview
│       ├── /revisions
│       └── /revisions/:revisionId
│           ├── /editor
│           ├── /validation
│           └── /inspect
│
├── /benchmarks
│   ├── /
│   └── /:benchmarkId
│       ├── /overview
│       └── /versions/:versionId
│
└── /targets
    ├── /
    ├── /new
    └── /:targetId
        ├── /overview
        └── /revisions/:revisionId
```

Run and forensic pages should be addressable through canonical IDs even when reached through an evaluation plan:

```text
/evaluations/:planId/runs/:runId
/evaluations/:planId/runs/:runId/forensics
```

The frontend can resolve those using:

```http
GET /api/v1/call-runs/{id}
GET /api/v1/call-runs/{id}/forensics
```

---

## 4. Application shell

### Desktop

Use a restrained left rail with a wide analytical canvas.

```text
┌──────┬───────────────────────────────────────────────────────────────┐
│      │ Breadcrumb / contextual actions                    Search ⌘K │
│ NAV  ├───────────────────────────────────────────────────────────────┤
│      │                                                               │
│      │ page content                                                  │
│      │                                                               │
│      │                                                               │
│      │                                                               │
└──────┴───────────────────────────────────────────────────────────────┘
```

The shell should feel closer to a sophisticated developer tool than a generic SaaS admin panel.

### Mobile

Collapse navigation into:

```text
Top bar
  ├── menu
  ├── current context
  └── overflow actions
```

Data-heavy analytical views become horizontally scrollable rather than losing columns.

---

## 5. Global interaction model

Every page should answer three questions immediately:

1. **What object am I looking at?**
2. **What state is it in?**
3. **What can I do next?**

Examples:

```text
Evaluator revision
DRAFT
→ Edit
→ Validate
→ Compare with parent

VALIDATED
→ Inspect validation
→ Approve

Approved
→ Create evaluation plan
```

```text
Evaluation plan
RUNNING
→ View live
→ Cancel

COMPLETED
→ View results
→ Inspect runs
→ Inspect manifest
```

---

## 6. Source-of-truth UX rules

### Rule A — Do not hide immutability

Whenever the user opens:

- approved evaluator revision
- frozen benchmark version
- execution manifest
- raw provider event
- original media artifact

show an explicit immutable indicator.

Example:

```text
LOCKED
Approved evaluator revision v7
content hash
```

### Rule B — Do not turn missing observability into a zero

Metric status badges must distinguish:

```text
COMPUTED
NOT_AVAILABLE
NOT_APPLICABLE
INVALID
ERROR
```

A missing capability should render as observability state, not failure score.

### Rule C — Preserve attempts separately from samples

A run summary must read:

```text
Run 2
Repetition 2
Attempts: 2

Attempt 1  FAILED — ICE failure
Attempt 2  COMPLETED
Selected attempt: Attempt 2
```

Never render the second attempt as "Run 2 of 4".

### Rule D — Every qualitative result must be traceable

A metric card can show a score, but must also expose:

```text
Evidence: 3
↓
Turn 19
Turn 21
Tool call #4
```

---

## 7. Server/client state architecture

### Server state

TanStack Query owns:

```text
targets
target revisions
evaluators
evaluator revisions
validation reports
benchmarks
benchmark versions
benchmark cases
evaluation plans
plan results
call runs
call attempts
conversation
events
metrics
aggregates
composite
forensics
media URLs
```

Recommended key structure:

```ts
['targets']
['targets', targetId]
['targets', targetId, 'revisions']

['evaluators']
['evaluators', evaluatorId]
['evaluator-revisions', revisionId]
['evaluator-revisions', revisionId, 'validation']

['benchmarks']
['benchmarks', benchmarkId, 'versions', versionId]

['plans']
['plans', planId]
['plans', planId, 'results']
['plans', planId, 'aggregates']
['plans', planId, 'composite']

['runs', runId]
['runs', runId, 'forensics']

['attempts', attemptId]
['attempts', attemptId, 'conversation']
['attempts', attemptId, 'events']
['attempts', attemptId, 'media']

['metric-results', metricResultId]
['metric-results', metricResultId, 'evidence']
```

### Local state

Zustand should only own transient UI state:

```text
selectedRunId
selectedAttemptId
selectedTurnId
selectedEventId
timelineFilters
eventSourceFilters
metricFilters
forensicPanelLayout
audioPlaybackPosition
liveConnectionState
command palette state
```

Do not copy authoritative server objects into Zustand.

---

## 8. Live state architecture

Initial snapshot:

```text
REST
GET /evaluation-plans/:id
GET /evaluation-plans/:id/results

then

WS
/api/v1/evaluation-plans/:id/live
```

Browser WebSocket receives:

```text
plan.status.changed
run.status.changed
attempt.status.changed
metric.computed
judge.completed
aggregate.updated
composite.updated
```

The browser is only an observer.

It must never sit in the target's voice/media path.

Architecture:

```text
Third-party Agent
      ↕
CallRunner
      ↓
Runtime ingestion
      ↓
Redis / Postgres
      ↓
FastAPI UI WebSocket
      ↓
React
```

---

## 9. Data density strategy

VoiceEval contains high-cardinality runtime data.

The UI therefore uses three information densities:

### L1 — Executive

For:

- Overview
- plan header
- score summary

Show only:

```text
status
progress
score
coverage
major failures
```

### L2 — Analytical

For:

- result tables
- evaluator results
- metric distributions
- capability matrices

Show:

```text
values
distributions
coverage
status
comparison
```

### L3 — Forensic

For:

- attempt viewer
- event stream
- state transitions
- tool payloads
- media
- evidence

Show raw fields with minimal abstraction.

---

## 10. Page transition philosophy

Use progressive disclosure.

Example:

```text
Plan result
  ↓ click "semantic understanding"
Metric detail
  ↓ click evidence
Evidence drawer
  ↓ click "Turn 19"
Conversation inspector
  ↓ click audio offset
Waveform seeks to 11.720s
```

Do not make the user navigate away every time they want one layer deeper.

---

## 11. URL state

Filters that materially affect analytical views should be reflected in the URL.

Example:

```text
/evaluations/plan_123/results
  ?metric=ttfa
  &evaluator=evalrev_17
  &status=infra_failed
```

For forensic views:

```text
/evaluations/plan_123/runs/run_17/forensics
  ?attempt=att_2
  &turn=19
  &event=evt_184
```

Benefits:

- shareable investigations
- browser history
- reproducible support/debugging
- bookmarkable analysis states

---

## 12. Empty/loading/error states

### Loading

Do not use one giant skeleton.

Skeleton the actual data structures:

```text
score cards
metric rows
run matrix
timeline
```

### Empty state

Example:

```text
No evaluation plans yet

Create a benchmark or custom evaluator suite,
select an executable target revision,
and run your first evaluation.
```

### API error

Show:

```text
Could not load evaluator revision

Request ID
retry
```

Never show raw backend stack traces to normal users.

### Partial data

Use:

```text
PARTIAL
68 / 75 samples observable
```

and explain why.

---

## 13. Accessibility

Minimum requirements:

- keyboard navigable tables and drawers
- visible focus states
- no status communicated by color alone
- semantic labels for audio controls
- accessible expandable evidence sections
- `aria-live` for important live status transitions
- tooltips for abbreviated metrics
- escape closes drawers/modals
- timeline events remain keyboard selectable

Use icons plus text for status.

---

## 14. Core frontend boundaries

```text
src/
├── app/
│   ├── router/
│   ├── providers/
│   └── shell/
│
├── features/
│   ├── targets/
│   ├── evaluators/
│   ├── benchmarks/
│   ├── evaluations/
│   ├── results/
│   ├── forensics/
│   └── live/
│
├── components/
│   ├── ui/                  # shadcn primitives
│   ├── data-display/
│   ├── status/
│   ├── charts/
│   ├── timeline/
│   └── audio/
│
├── lib/
│   ├── api/
│   ├── websocket/
│   ├── formatters/
│   ├── validators/
│   └── permissions/
│
├── stores/
└── styles/
```

---

## 15. Design invariants

1. The UI never changes an executed evaluator revision.
2. The UI never changes a frozen benchmark version.
3. The UI never mutates an execution manifest.
4. Raw runtime events are shown as immutable evidence.
5. Derived turns are presented as materialized views of the event stream.
6. Missing metrics are shown explicitly.
7. Retries are nested under a logical run.
8. Coverage is always adjacent to score/composite information.
9. Every evidence item can navigate toward its source.
10. The live UI WebSocket is never the execution transport.
