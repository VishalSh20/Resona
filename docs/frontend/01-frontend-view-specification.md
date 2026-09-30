# VoiceEval — Frontend Views & User Flows v0.1

## 1. View inventory

The product should ship around the following views:

```text
01  Overview Dashboard
02  Evaluation Plans List
03  Create Evaluation Plan
04  Evaluation Plan Overview
05  Evaluation Live Console
06  Evaluation Results
07  Evaluator Library
08  Evaluator Revision Editor
09  Evaluator Validation View
10  Benchmark Library
11  Benchmark Version View
12  Target Library
13  Target Revision View
14  Logical Run Detail
15  Physical Attempt / Forensic Viewer
16  Metric / Evidence Inspector
17  Execution Manifest Viewer
```

The application should not expose every database entity as an independent CRUD screen. Views are composed around workflows.

---

# 2. Overview Dashboard

Route:

```text
/
```

### Purpose

Give a high-signal view of what is happening and what deserves attention.

### Layout

```text
┌─────────────────────────────────────────────────────────────────┐
│ VoiceEval                              New evaluation  ⌘K       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Active evaluations     Completed this week     Coverage         │
│  2 running             18 plans                94.1%             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ Recent evaluations                                               │
│                                                                 │
│ Plan                    Target        Progress       Status      │
│ Support benchmark       Acme v12      69/75          Running     │
│ Hindi QA                Vox v3        75/75          Completed   │
│                                                                 │
├─────────────────────────────┬───────────────────────────────────┤
│ Failure patterns             │ Recent evaluator revisions        │
│                             │                                   │
│ 3 infrastructure failures   │ credit_card_unblock v7           │
│ 4 motive failures           │ language_switch v3               │
└─────────────────────────────┴───────────────────────────────────┘
```

### Important cards

**Active Evaluations**

```text
running plans
queued plans
```

**Recent Results**

Show:

```text
composite
coverage
plan status
logical runs
```

**Failure Patterns**

Use normalized failure codes from the backend, not free-form labels.

**Recent Revisions**

Show:

```text
evaluator name
revision
status
validation summary
```

### Interaction

Clicking a row opens its domain page.

No score should be shown without an adjacent indication of coverage where coverage materially affects interpretation.

---

# 3. Evaluation Plans List

Route:

```text
/evaluations
```

### Table

Columns:

```text
Plan
Kind
Target
Scope
Repeats
Progress
Status
Created
```

Row example:

```text
Customer Support v12
benchmark
Acme Support / revision 4
25 evaluators
3×
72/75
RUNNING
29 Sep, 18:20
```

### Filters

```text
status
kind
target
created range
```

### Bulk behavior

Avoid destructive bulk actions in MVP.

Primary action:

```text
New evaluation
```

---

# 4. Create Evaluation Plan

Route:

```text
/evaluations/new
```

Use a wizard because preparation is a meaningful backend operation.

## Step 1 — Scope

Choose:

```text
Benchmark
Custom evaluator/test descriptor
```

### Benchmark branch

Select:

```text
Benchmark
Frozen version
```

Only frozen benchmark versions are executable.

### Custom branch

Select:

```text
Test descriptor revision
```

---

## Step 2 — Target

Choose:

```text
Agent target
Executable target revision
```

Show target revision details:

```text
transport
adapter
adapter version
config hash
capability snapshot
```

Capability visualization:

```text
Audio
Caller ingress       ✓
Agent egress         ✓

Transcript
Target input         —
Target output        ✓
Independent ASR      ✓

Events
Turn boundaries      ✓
Text stream          ✓
Interruptions        —
Connection events    ✓

Tools
Calls                ✓
Results              ✓
```

Do not expose secrets from endpoint configuration.

---

## Step 3 — Evaluators / Cases

Benchmark flow:

```text
Benchmark version
   ↓
case list
   ↓
evaluator revision for each case
```

Allow:

```text
search
filter
enable/disable
inspect evaluator revision
```

Show sequence number.

Custom flow may show generated evaluator candidates after a generator process where supported by the backend contract.

---

## Step 4 — Repeat count

Show the statistical meaning explicitly.

```text
Repetitions
[ 3 ]

25 evaluators × 3 repetitions = 75 logical samples
```

Secondary note:

```text
Retries do not create additional logical samples.
```

---

## Step 5 — Preparation / Capability Gate

Button:

```text
Prepare evaluation
```

Backend operation:

```http
POST /api/v1/evaluation-plans/{id}/prepare
```

The UI transitions:

```text
Draft
  ↓
Preparing
  ↓
Capability check
  ↓
Execution manifest created
  ↓
Ready
```

Display blockers.

Example:

```text
Cannot execute

2 blocking capability mismatches

✕ agent_input_wer
  requires target input transcript

✕ tool_argument_correctness
  requires tool calls
```

Optional metrics should instead display:

```text
Will be NOT_AVAILABLE for this target
```

The distinction is important.

---

# 5. Evaluation Plan Overview

Route:

```text
/evaluations/:planId/overview
```

### Header

```text
Support Benchmark
RUNNING

Target
Acme Support · revision 12

75 logical samples
52 completed · 11 running · 12 queued

[Live] [Results] [Runs] [Manifest]
```

### Progress visualization

Use a segmented progress bar:

```text
████████████████████░░░░░░ 69 / 75
```

Then a compact status line:

```text
completed 57
running 7
queued 11
failed 0
cancelled 0
```

Backend plan terminal states:

```text
draft
ready
queued
running
partial
completed
cancelled
```

The UI must retain `partial` as a real state.

---

# 6. Evaluation Live Console

Route:

```text
/evaluations/:planId/live
```

This is the operational center.

## Layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ LIVE · Support Benchmark                         69 / 75             │
├──────────────────────────────┬───────────────────────────────────────┤
│ Repetition matrix            │ Selected run                          │
│                              │                                       │
│ Evaluator      1   2   3    │ credit_card_unblock · Run 2           │
│ credit_card     ✓   ●   ·    │                                       │
│ refund          ✓   ✓   ●    │ Attempt 1 → failed                    │
│ complaint       ✓   ·   ·    │ Attempt 2 → running                   │
│ ...                          │                                       │
├──────────────────────────────┼───────────────────────────────────────┤
│ Status stream                │ Runtime summary                       │
│ 18:42:02 attempt started     │ connection   ready                   │
│ 18:42:03 turn started       │ turns        7                         │
│ 18:42:04 tool call           │ tools        2                         │
│ ...                          │ elapsed      21.4 s                   │
└──────────────────────────────┴───────────────────────────────────────┘
```

### Matrix

A cell represents a **CallRun**, not a physical attempt.

States:

```text
queued
running
completed
infrastructure_failed
cancelled
```

If attempts > 1:

```text
✓²
```

or a small retry marker.

Tooltip:

```text
Run 2
2 attempts
Attempt 1: TRANSPORT failure
Attempt 2: running
```

### Live stream

Browser subscribes to:

```text
WS /api/v1/evaluation-plans/{plan_id}/live
```

Supported messages:

```text
plan.status.changed
run.status.changed
attempt.status.changed
metric.computed
judge.completed
aggregate.updated
composite.updated
```

The stream is observability only.

---

# 7. Evaluation Results

Route:

```text
/evaluations/:planId/results
```

## Header

```text
Evaluation completed
75 logical samples

Composite
82.4 / 100

Coverage
94.7%

[Inspect coverage] [Manifest]
```

If composite is incomplete:

```text
Composite incomplete
Coverage 88.4%
Unavailable weight 12.0%
Missing critical metrics 2
```

Do not render a fake score.

---

## 7.1 Category score cards

Render only categories exposed by the composite result.

Example:

```text
Motive
88.2

Conversation
81.4

Voice
79.1

Language
91.0
```

Weights and normalization must come from `CompositeScoreDefinition`.

---

## 7.2 Metric results table

Columns:

```text
Metric
Category
Value
Unit
Coverage
Status
Trend/distribution
```

Example:

```text
TTFA
Voice
720 ms
90.7%
COMPUTED
median 690 ms

Semantic understanding
Conversation
4.0 / 5
100%
COMPUTED
3 · 4 · 5

Agent input WER
Transcript
—
0%
NOT_AVAILABLE
Target input transcript unavailable
```

---

## 7.3 Evaluator heatmap

Rows:

```text
evaluator revisions
```

Columns:

```text
motive
semantic
clarity
context
interruption
language
coverage
```

Cell can show:

```text
4.0
```

Hover reveals:

```text
Runs: 3
Values: 3, 4, 5
Mean: 4.0
Coverage: 100%
```

For n=3, do not imply stable percentile estimates. The backend explicitly requires raw values, mean, median, min/max and standard deviation to remain visible.

---

# 8. Evaluator Library

Route:

```text
/evaluators
```

## Table

```text
Name
Key
Suite
Latest revision
Status
Validation
Updated
```

Example:

```text
Credit Card Unblock
credit_card_unblock
custom
v7
APPROVED
0 errors / 1 warning
29 Sep
```

### Status progression

```text
GENERATED
DRAFT
VALIDATING
VALIDATED
APPROVED
EXECUTED
```

`rejected` is also a revision state in the domain schema and must be supported.

---

# 9. Evaluator Revision Editor

Route:

```text
/evaluators/:evaluatorId/revisions/:revisionId/editor
```

This is the most structured authoring page in the product.

Use a two-pane editor:

```text
┌──────────────────────┬───────────────────────────────────────────┐
│ Sections             │ Editor                                    │
│                      │                                           │
│ Scenario             │ Persona                                  │
│ Language             │ Age        [28]                          │
│ Facts                │ Personality [mildly_frustrated]           │
│ Initial state        │ Traits                                  │
│ Motive               │ [initially_cooperative]                   │
│ Behaviour            │ [interrupt_once]                          │
│ Stop conditions      │                                           │
│ Criteria             │                                           │
│ Randomization        │                                           │
└──────────────────────┴───────────────────────────────────────────┘
```

## Editor sections

### Persona

Represent:

```text
age
personality
traits[]
```

### Language

Represent:

```text
primary
allowed[]
adaptation_rule
```

### Environment

Represent:

```text
noise_profile
```

### Facts

Use editable rows:

```text
fact id
type
value
```

Do not hide fact values inside raw JSON by default.

### Initial state

Use key/value state rows.

### Motive

Represent:

```text
objective
assertions
```

Each assertion editor:

```text
id
type
required
weight
oracle / expectation
```

### Behaviour

Represent:

```text
allowed actions
recovery.max_attempts
```

### Stop conditions

Represent:

```text
natural_success
recovery_exhausted
irrecoverable_objective_failure
conversation_stall_ms
wall_clock_timeout_ms
```

### Evaluation criteria

Rows:

```text
metric
required
```

### Randomization

Represent:

```text
policy version
```

---

# 10. Evaluator Validation View

Route:

```text
/evaluators/:evaluatorId/revisions/:revisionId/validation
```

### Summary

```text
VALIDATED

0 blocking errors
2 warnings

Validator 1.4.2
Generated 29 Sep 2026
```

### Check list

```text
Scenario validity              PASS
Motive validity                PASS
State consistency              PASS
Success conditions             PASS
Behaviour validation           PASS
Language validation            PASS
Criteria validation            PASS
Capability validation          WARNING
Observability                  WARNING
```

Each row expands:

```text
details
affected metric
required capability
suggested user action
```

The backend defines validation as a gate before execution; the UI should make that gate visually explicit.

---

# 11. Benchmark Library

Route:

```text
/benchmarks
```

Table:

```text
Benchmark
Key
Latest version
Cases
Status
Last frozen
```

Benchmark version states:

```text
draft
frozen
retired
```

---

# 12. Benchmark Version View

Route:

```text
/benchmarks/:benchmarkId/versions/:versionId
```

### Header

```text
Customer Support Benchmark
v12
FROZEN 🔒

25 cases
Manifest hash …
Frozen 29 Sep 2026
```

### Cases table

```text
#
Case key
Evaluator
Revision
Enabled
```

Clicking a case opens the evaluator revision inspector without leaving the benchmark context.

---

# 13. Target Library

Route:

```text
/targets
```

Table:

```text
Target
Provider
Latest revision
Transport
Capabilities
Updated
```

Example:

```text
Acme Support
acme
rev 12
WebSocket
9 / 12 observable capabilities
```

---

# 14. Target Revision View

Route:

```text
/targets/:targetId/revisions/:revisionId
```

Tabs:

```text
Overview
Connection
Capabilities
Configuration
Revision history
```

## Overview

Show:

```text
revision_no
transport
adapter_name
adapter_version
config_hash
created_by
created_at
```

## Connection

Show non-secret `endpoint_config`.

Never reveal secret material.

## Capabilities

Render nested capability matrices.

### Example

```text
AUDIO

caller_ingress       ✓
agent_egress         ✓

TRANSCRIPT

target_input         ✕
target_output        ✓
independent_asr      ✓

EVENTS

turn_boundaries      ✓
text_stream          ✓
interruptions        ✕
connection_events    ✓

TOOLS

calls                ✓
results              ✓
```

---

# 15. Logical Run Detail

Route:

```text
/evaluations/:planId/runs/:runId
```

The page emphasizes:

```text
CallRun = statistical sample
```

Header:

```text
Credit Card Unblock
Run 2 / repetition 2

COMPLETED

Duration 34.8 s
Attempts 2
Selected attempt #2
```

### Attempt list

```text
Attempt 1
FAILED
TRANSPORT
ICE connection failed
6.2 s

Attempt 2
COMPLETED
NATURAL_SUCCESS
34.8 s
```

### Run metrics

Show metric results associated with the selected attempt.

### Run-level judge

Show:

```text
judge
status
latency
parsed output
reason codes
```

### Retry

Only show:

```text
Retry infrastructure failure
```

when the run is eligible under backend retry semantics.

Never present retry as a new repetition.

---

# 16. Physical Attempt / Forensic Viewer

Route:

```text
/evaluations/:planId/runs/:runId/forensics
```

This is the deepest interface.

## Desktop layout

```text
┌──────────────────────────────────────────────────────────────────┐
│ Run / Attempt header                                             │
├──────────────────────────────────────────────────────────────────┤
│ Timeline + audio                                                 │
├───────────────┬─────────────────────┬────────────────────────────┤
│ Conversation  │ Event stream        │ Inspector                  │
│               │                     │                            │
│ Turn cards    │ evt 184             │ selected event            │
│               │ evt 185             │ payload                  │
│ Tool calls    │ evt 186             │ evidence                  │
│ State         │ ...                 │ audio seek                │
└───────────────┴─────────────────────┴────────────────────────────┘
```

### Header facts

Show:

```text
attempt status
termination reason
failure class
eligible_for_evaluation
runner version
adapter version
transport version
trace ID
started_at
finished_at
duration
```

---

# 17. Conversation Inspector

Use turn cards rather than a chat bubble UI.

A turn is an analytical object.

Example:

```text
TURN 17 · CALLER · 12.420s → 15.810s

Mera card block ho gaya hai

Language
Hinglish

Transcript source
caller_reference

Reference audio
[▶ 12.420 — 15.810]

Events
caller.speech.start
caller.audible.start
turn.start
turn.end
```

Agent turn:

```text
TURN 18 · AGENT

Sure, I can help you replace the card.

Transcript source
provider

Observed language
en
```

The UI should distinguish:

```text
reference_text
observed_text
```

instead of pretending they are the same thing.

---

# 18. Timeline

Primary x-axis:

```text
runner monotonic milliseconds
```

Secondary information:

```text
wall clock
media timestamp when available
```

Rows:

```text
CALLER AUDIO
AGENT AUDIO
TURNS
TEXT
TOOLS
STATE
CONNECTION
METRICS
```

Example:

```text
12.4s       15.8s
│────────────│
caller      speaking

15.8s       16.5s
             │───── agent media

16.1s
       agent.audible.start
```

Metric calculations should visually connect their start/end evidence.

---

# 19. Audio Inspector

A media artifact card shows:

```text
track
representation
format
codec
sample rate
channels
duration
clock domain
size
sha256
```

Playback uses:

```http
GET /api/v1/media/{media_artifact_id}/url
```

The frontend never requests the S3 object directly through application data endpoints.

### Controls

```text
Play / Pause
±5 sec
Playback speed
Seek
Download/open source
```

Original and analysis representations must remain visually distinct.

---

# 20. Tool Call Inspector

Represent one logical tool call as:

```text
#4 unblock_card
SUCCEEDED

00:22.14 → 00:23.05
Duration 912 ms

Arguments
{
  "card_last_four": "4821"
}

Result
{
  ...
}
```

Show its event lineage:

```text
tool.call.start
tool.call.args
tool.call.result
tool.call.end
```

If no tool events are available for the target, show:

```text
Tool observability unavailable
```

not:

```text
No tools were called
```

---

# 21. State Transition Inspector

Display a chronological state ledger:

```text
v6
/authenticated
false → true

trigger
authentication.completed

event
evt_231
```

Expandable JSON for complex patches.

Also show:

```text
recovery_count
current_intent
conversation_phase
```

where present in the caller snapshot/event payloads.

---

# 22. Event Inspector

Runtime events show the complete canonical envelope:

```text
event_id
call_attempt_id
sequence
type
source
monotonic_ms
wall_clock
media_timestamp
turn_id
provider_event_id
payload
```

Source badge:

```text
provider_raw
provider_normalized
runtime
derived
caller
metric
```

Raw provider payload must be visually marked as raw/untrusted evidence.

---

# 23. Evidence Drawer

Every evidence item should be directly actionable.

Example:

```text
Evidence · ev_01J

Source
TURN
turn_19

Time
11.720s → 13.100s

Quote
"Nahi, replacement nahi chahiye."

Rationale
Caller explicitly corrected the agent.

[Open turn]
[Seek audio]
[Open event]
```

Allowed source types:

```text
turn
event
tool_call
audio
state_transition
```

The frontend should provide one-click traversal among all linked objects.

---

# 24. Metric Inspector

Route/modal:

```text
/evaluations/:planId/metrics/:metricResultId
```

### Header

```text
Semantic Understanding
4.0 / 5
COMPUTED
structured_judge v2.1
```

### Detail

```text
Method
structured_judge

Confidence
0.96

Input provenance
call_turns
runtime_events

Judge execution
judge_01J…

Evidence
3 sources
```

### Measurement basis

For deterministic metrics display structured basis:

```text
start event
end event
clock
```

For example:

```text
TTFA
720 ms

start:
caller.audible.end @ 8200 ms

end:
agent.audible.start @ 8920 ms

clock:
runner_monotonic
```

---

# 25. Execution Manifest Viewer

Route:

```text
/evaluations/:planId/manifest
```

This should feel like a forensic "sealed envelope".

Show:

```text
Manifest
schema_version

Target snapshot
Evaluator snapshot
Benchmark snapshot
Caller snapshot
Metric snapshot
Judge snapshot
Aggregation snapshot
Composite snapshot

manifest hash
created_at
```

Each section expands to:

```text
IDs
versions
content hashes
model identifiers
prompt hashes
adapter/runtime versions
```

Do not make any field editable.

---

# 26. End-to-end user flows

## Flow A — Create and run a benchmark

```text
Benchmarks
  ↓
Open frozen version
  ↓
Run benchmark
  ↓
Select target revision
  ↓
Review capability matrix
  ↓
Prepare plan
  ↓
Capability validation
  ↓
Execution manifest
  ↓
Ready
  ↓
Execute
  ↓
Live console
  ↓
Results
```

## Flow B — Fix a validation failure

```text
Evaluator revision
  ↓
Validate
  ↓
Blocking error
  ↓
Open failed check
  ↓
Jump to evaluator section
  ↓
Edit
  ↓
New revision
  ↓
Validate
  ↓
Approve
```

A user edit creates another revision; do not silently mutate an executed revision.

## Flow C — Investigate a poor metric

```text
Results
  ↓
Metric aggregate
  ↓
Evaluator
  ↓
Run
  ↓
Selected attempt
  ↓
Metric result
  ↓
Evidence
  ↓
Turn / event / tool / state / audio
```

This follows the backend's primary observability chain.

## Flow D — Diagnose infrastructure failure

```text
Plan
  ↓
Runs
  ↓
Run 17
  ↓
Attempts
  ├── Attempt 1 · TRANSPORT
  └── Attempt 2 · completed
```

The failure remains in history while selected evidence comes from the eligible attempt.

---

# 27. Cancellation flow

```text
User clicks Cancel
      ↓
Confirm dialog
      ↓
POST /evaluation-plans/{id}/cancel
      ↓
plan = CANCELLED
      ↓
live event updates
      ↓
queued runs cancel
running attempts terminate
```

Running attempts should visibly transition through termination rather than instantly disappearing.

---

# 28. Resume/retry flow

The UI must expose two distinct operations.

### Retry run

For an infrastructure-failed logical run:

```text
Run detail
  ↓
Retry infrastructure failure
  ↓
POST /call-runs/{run_id}/retry
```

### Resume plan

For unfinished logical repetitions:

```text
Plan
  ↓
Resume
  ↓
POST /evaluation-plans/{plan_id}/resume
```

Do not create a generic "retry plan" button.

---

# 29. Result completion states

### Complete

```text
COMPLETED
75 / 75 logical runs terminal
composite complete
```

### Partial

```text
PARTIAL
74 / 75 logical runs terminal
1 logical run unresolved/failed
```

### Incomplete composite

```text
Plan may be completed,
but composite is INCOMPLETE.

Coverage 88%
Unavailable weight 12%
Missing: target_input_wer
```

These are separate concepts and should never be represented by one "failed" badge.
