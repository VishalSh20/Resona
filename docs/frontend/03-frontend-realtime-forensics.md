# VoiceEval — Realtime, Timeline & Forensic UX v0.1

## 1. Purpose

This document defines the realtime browser behavior and forensic inspection model.

The backend deliberately separates:

```text
Target WS/WebRTC
Runner telemetry/control channel
Browser live UI WebSocket
```

The browser only participates in the third channel.

The Browser UI WebSocket is:

```text
WS /api/v1/evaluation-plans/{plan_id}/live
```

It is an observability feed, not a media transport.

---

# 2. Live connection lifecycle

## 2.1 Initial page load

```text
Open /evaluations/:planId/live
       ↓
GET plan
       ↓
GET result/progress snapshot
       ↓
render stable initial state
       ↓
open browser WebSocket
```

This avoids a blank page while the socket connects.

---

# 3. WebSocket client state machine

```text
DISCONNECTED
    ↓
CONNECTING
    ↓
CONNECTED
    ↓
RECEIVING
    ├── transient error → RECONNECTING
    └── close            → DISCONNECTED
```

Recommended client states:

```ts
type LiveConnectionState =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'closed'
  | 'error';
```

Show a small connection indicator:

```text
● Live
```

or:

```text
↻ Reconnecting
```

Do not block the rest of the page when the live channel is disconnected.

---

# 4. Reconnect strategy

The backend contract supplies live status events but does not define a replay cursor in the browser protocol.

Therefore the safe client behavior is:

```text
socket disconnects
   ↓
reconnect
   ↓
refetch authoritative plan snapshot
   ↓
refetch selected run if needed
   ↓
resume socket
```

Do not invent client-side event replay from an assumed sequence number.

Runtime event sequence numbers are for attempt event ordering; they are not a guaranteed UI WebSocket replay API.

---

# 5. Live event reducer

Every live message should update the query cache rather than maintaining a shadow data store.

Example:

```ts
switch (message.type) {
  case 'plan.status.changed':
    queryClient.setQueryData(
      ['plans', planId],
      patchPlanStatus(...)
    );
    break;

  case 'run.status.changed':
    patchRunStatus(...);
    break;

  case 'attempt.status.changed':
    patchAttemptStatus(...);
    break;

  case 'metric.computed':
    invalidateRunMetrics(...);
    break;

  case 'judge.completed':
    invalidateRunJudges(...);
    break;

  case 'aggregate.updated':
    invalidatePlanAggregates(planId);
    break;

  case 'composite.updated':
    invalidatePlanComposite(planId);
    break;
}
```

Use invalidation when the live event is a notification rather than a complete representation.

---

# 6. Live progress model

A plan is a collection of logical repetitions.

For example:

```text
25 evaluators × 3 repetitions = 75 CallRuns
```

The live UI should therefore represent:

```text
75 logical samples
```

with run state:

```text
queued
running
completed
infrastructure_failed
cancelled
```

Physical attempts are secondary.

---

# 7. Repetition matrix

Primary visualization:

```text
                   REP 1     REP 2     REP 3
credit_card        ✓         ●         ○
refund             ✓         ✓         ●
complaint          ✓         ✕         ○
identity           ✓         ✓         ✓
```

Legend:

```text
✓ completed
● running
○ queued
✕ infrastructure failed
```

If a run has multiple attempts:

```text
✓ ²
```

where the superscript denotes two physical attempts.

Hover:

```text
Run run_01J
Repetition 2

Attempt #1
TRANSPORT / failed

Attempt #2
RUNNING
```

This makes the statistical/infrastructure distinction visible.

---

# 8. Live selected-run panel

When a user selects a running cell:

```text
Credit Card Unblock
Run 2

RUNNING

Attempt #2
STARTING → CONNECTING → RUNNING

Elapsed
21.4 s

Connection
ready

Turns
7

Tool calls
2

Latest event
agent.audible.start
16.82 s
```

Do not reconstruct a detailed event stream from the live plan feed alone.

The live plan feed is coarse-grained.

For detailed inspection, fetch:

```http
GET /api/v1/call-attempts/{attempt_id}/events
GET /api/v1/call-attempts/{attempt_id}/conversation
```

---

# 9. Runtime event model in the forensic viewer

The canonical event envelope includes:

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
payload
provider_event_id
```

Required/optional field presence should be reflected honestly.

Example event row:

```text
184
agent.audible.start
derived

12,420 ms
12:35:22.420 UTC

turn_17
```

Click opens full inspector.

---

# 10. Event taxonomy

Group events into visual channels.

### Connection

```text
connection.requested
connection.signaling.*
connection.ice.*
connection.ready
connection.warning
connection.error
connection.closed

connection.ws.*
connection.rtc.*
```

### Media

```text
caller.media.*
caller.speech.*
caller.audible.*

agent.media.*
agent.speech.*
agent.audible.*
```

### Text

```text
agent.text.first
agent.text.delta
agent.text.final
```

### Turn

```text
turn.start
turn.end
turn.interrupted
turn.overlapped
```

### Language

```text
caller.language.detected
caller.code_switch.detected
agent.language.detected
agent.code_switch.detected
```

### Tool

```text
tool.call.start
tool.call.args
tool.call.result
tool.call.end
```

### Caller decision

```text
caller.state.initialized
caller.action.selected
caller.utterance.realized
caller.interruption.scheduled
caller.recovery.used
caller.assertion.updated
caller.terminal
```

---

# 11. Event source filter

Provide filter chips:

```text
All
Provider raw
Provider normalized
Runtime
Derived
Caller
Metric
```

Default:

```text
Provider normalized
Runtime
Derived
Caller
```

Raw provider data should be available but not dominate the initial forensic view.

---

# 12. Event type filter

Searchable:

```text
Search event type…
```

Examples:

```text
tool.call.end
agent.audible.start
turn.interrupted
```

---

# 13. Time range filter

The event endpoint supports:

```text
from_ms
to_ms
```

UI pattern:

```text
Timeline range
[ 10.0s ] — [ 20.0s ]
```

Changing the range updates the event query.

---

# 14. Conversation materialization

A `CallTurn` is a derived semantic object and can be revised after late provider events.

Therefore the UI must label it as:

```text
Materialized turn
```

not:

```text
raw event
```

Useful visual distinction:

```text
RAW
runtime event stream

MATERIALIZED
conversation turns
```

This teaches the user the provenance model without requiring documentation.

---

# 15. Timeline lanes

Use one synchronized timeline with lanes:

```text
┌──────────────────────────────────────────────────────────────────┐
│  Time 10s       15s        20s        25s        30s              │
├──────────────────────────────────────────────────────────────────┤
│ Caller audio     ████████                 ██████                  │
│ Agent audio                 ███████████                           │
│ Caller speech    ██████                   ████                   │
│ Agent audible               █████████                            │
│ Turns            T12         T13       T14         T15            │
│ Tools                        #3        #4                        │
│ State                      auth ✓                                  │
│ Connection      ready -------------------------------- close     │
└──────────────────────────────────────────────────────────────────┘
```

All rows share the same x-coordinate.

---

# 16. Clock display

Backend timing explicitly distinguishes:

```text
wall clock
runner monotonic clock
media clock / RTP timestamp
sequence number
```

UI:

- use monotonic milliseconds for latency analysis
- use wall clock for human-facing timestamps
- show media timestamps in a secondary inspector where useful
- never imply all clocks are identical

Header example:

```text
12.420s
UTC 18:05:22.420
media 918273
event #184
```

---

# 17. Turn card interactions

Every turn card supports:

```text
select
copy text
open events
seek audio
open related evidence
```

For caller turns show:

```text
reference text
observed text if available
reference language
observed language
transcript source
confidence
```

For agent turns:

```text
observed text
observed language
provider provenance
```

This is crucial for WER interpretation.

---

# 18. Transcript provenance UI

Use a small badge beside every transcript:

```text
REFERENCE
PROVIDER INPUT
PROVIDER OUTPUT
INDEPENDENT ASR
HUMAN
UNKNOWN
```

Example:

```text
"Mera card block ho gaya hai"
REFERENCE · caller_reference
```

If target input transcript is unavailable:

```text
Agent input WER
NOT_AVAILABLE

Reason:
Target input transcript is not exposed.
```

Do not label an independent ASR measurement as target-agent WER.

---

# 19. TTFA visualization

For a TTFA evidence view:

```text
caller.audible.end             agent.audible.start
       │                                │
       ▼                                ▼
───────●────────────────────────────────●──────
     8.200s                           8.920s

TTFA = 720 ms
clock = runner_monotonic
```

A click on either endpoint jumps to the exact event.

---

# 20. TTFT visualization

```text
caller turn end                  agent.text.first
       │                               │
       ▼                               ▼
───────●───────────────────────────────●──────
      8.2s                           8.68s

TTFT = 480 ms
```

Only show TTFT when the target text stream capability exists and the metric is computed.

Otherwise:

```text
TTFT
NOT_AVAILABLE
Target text stream unavailable
```

---

# 21. Interruption visualization

Example timeline:

```text
Agent speaking
██████████████████
                  ↑ caller speech begins
                  │
                  ├───── interruption latency ─────┐
                                                    ↓
Agent stops
████████████████████████
```

Show:

```text
interruption_detected
agent_stopped
caller_continued
latency
```

This distinguishes interruption from mere overlap.

---

# 22. State timeline

State transitions appear as a vertical ledger synchronized with the timeline:

```text
v6
authenticated
false → true
trigger:
authentication.completed

v7
current_intent
authenticate → unblock_card
trigger:
caller.action.selected
```

Expandable patch details:

```json
[
  {
    "path": "/authenticated",
    "from": false,
    "to": true
  }
]
```

---

# 23. Tool timeline

Tool calls should appear as blocks spanning:

```text
start_ms → end_ms
```

Inside each block:

```text
tool name
status
duration
```

Click opens arguments/result.

---

# 24. Evidence-to-source navigation

The forensic UI must support bidirectional traversal.

### Metric → evidence → source

```text
MetricResult
  ↓
Evidence
  ↓
Turn / Event / Tool / State / Audio
```

### Source → supported metric

```text
Turn 19
  ↓
Evidence
  ↓
MetricResult
  ↓
Aggregate
```

The second direction is useful when debugging one conversation segment.

---

# 25. Audio architecture in the UI

Backend distinguishes:

```text
original / wire artifact
analysis artifact
clip
mixed
```

Display a representation selector:

```text
Source
Original
Analysis
```

If a clip exists:

```text
Evidence clip
```

Do not silently replace original audio with analysis audio.

---

# 26. Audio buffering behavior

Signed URLs are short-lived.

When playback starts:

```text
Need URL?
  ├── no → use cached URL
  └── yes → fetch /media/:id/url
```

If the URL expires:

```text
refresh signed URL
resume playback
```

Never expose `object_uri` as a public download path.

---

# 27. Attempt terminal handling

Every attempt has exactly one terminal runtime event.

UI shows:

```text
TERMINAL

status: completed
termination: NATURAL_SUCCESS
terminal event: #391
```

If the attempt fails:

```text
FAILED
failure class: TRANSPORT
termination: CONNECTION_FAILURE
```

The terminal event becomes an immutable anchor in the forensic timeline.

---

# 28. Forensic query strategy

Use lazy loading.

Initial:

```text
GET run
GET forensics summary
```

On opening forensic view:

```text
GET conversation
GET events
GET media
```

On selecting a metric:

```text
GET metric
GET evidence
```

Do not download all event payloads and all media metadata for every run in a plan.

---

# 29. Forensic layout responsiveness

Desktop:

```text
conversation | timeline | inspector
```

Tablet:

```text
conversation
timeline
inspector
```

Mobile:

```text
turn
  ↓
timeline
  ↓
inspector
```

Use a bottom sheet for evidence/source inspection on mobile.
