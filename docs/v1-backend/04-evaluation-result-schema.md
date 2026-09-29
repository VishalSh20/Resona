# VoiceEval — Evaluation Results Schema v0.3 (Strengthened)

## 1. Result hierarchy

```text
Evaluation Plan
   │
   ├── Evaluator
   │      ├── Run 1
   │      │    └── Attempt(s)
   │      │
   │      ├── Run 2
   │      │    └── Attempt(s)
   │      │
   │      └── Run 3
   │           └── Attempt(s)
   │
   ├── Metric Results
   ├── Aggregates
   └── Composite Score
```

A logical run is the statistical sample. Physical attempts are infrastructure history.

The Product Scope requires three independent repetitions and keeps run-by-run results inspectable. fileciteturn0file0L830-L866

---

## 2. `metric_result`

```json
{
  "id": "mr_01J...",
  "call_run_id": "run_01J...",
  "call_attempt_id": "att_01J...",

  "metric": {
    "key": "semantic_understanding",
    "version": "2.1"
  },

  "status": "computed",

  "value": {
    "numeric": 2.0
  },

  "unit": "score",
  "scale": {
    "min": 1,
    "max": 5
  },

  "method": "structured_judge",

  "measurement_basis": {
    "input_provenance": [
      "call_turns",
      "runtime_events"
    ]
  },

  "confidence": 0.96,

  "judge_execution_id": "judge_01J...",
  "evidence_ids": [
    "ev_01J..."
  ],

  "computed_at": "2026-09-29T12:40:00Z"
}
```

---

## 3. Metric status contract

```text
COMPUTED
NOT_AVAILABLE
NOT_APPLICABLE
INVALID
ERROR
```

### `NOT_AVAILABLE`

Required signal was not exposed by the target.

### `NOT_APPLICABLE`

The scenario genuinely does not exercise the metric.

### `INVALID`

The evaluator itself cannot be evaluated meaningfully.

### `ERROR`

The metric was applicable and evidence existed, but computation failed.

None of these should silently map to zero.

---

## 4. Confidence semantics

Do not blindly attach a confidence number to every metric.

Recommended:

```text
Deterministic metrics
  confidence = NULL
  evidence_quality = high/medium/low

LLM/structured judge metrics
  confidence = judge output or calibrated confidence
```

A deterministic TTFA measurement does not become "95% confident" merely because the system is functioning.

---

## 5. Deterministic metrics

Examples:

```text
TTFT
TTFA
interruption_latency
turn_duration
call_duration

agent_input_wer
independent_asr_wer

tool_argument_exactness
tool_order_correctness
duplicate_tool_calls
```

Store the measurement basis.

Example:

```json
{
  "metric": "ttfa",
  "value_numeric": 720,
  "unit": "ms",
  "method": "deterministic",

  "measurement_basis": {
    "start_event": "caller.audible.end",
    "end_event": "agent.audible.start",
    "clock": "runner_monotonic"
  }
}
```

---

## 6. Structured judge

The source defines a structured numerical/decision judge ("Jev"). fileciteturn0file0L701-L723

Use a strict schema:

```json
{
  "motive_fulfilled": false,
  "semantic_understanding": 2,
  "response_clarity": 4,
  "context_retention": 3,
  "language_adaptation": 3,

  "reason_codes": [
    "MISINTERPRETED_MOTIVE",
    "FAILED_RECOVERY"
  ]
}
```

The output is parsed and validated.

Malformed output:

```text
judge_execution = INVALID
metric_result = ERROR
```

Never silently coerce malformed model output into a valid score.

---

## 7. LLM judge

The richer LLM judge should answer:

```text
Why did the failure happen?
What was misunderstood?
Which exact turns support the conclusion?
What should the agent have done?
Which failure pattern applies?
```

Do not ask the LLM to recompute deterministic metrics.

---

## 8. Rubric anchors

Every qualitative metric needs a versioned rubric.

Example:

```yaml
metric: misunderstanding_recovery
rubric_version: "1.0"

1:
  definition: "Agent fails to update after explicit correction."

3:
  definition: "Agent updates after repeated correction."

5:
  definition: "Agent quickly recognizes and correctly repairs the misunderstanding."
```

Rubric anchors reduce evaluator drift and judge inconsistency.

---

## 9. Motive fulfillment

Represent motive as a set of weighted assertions.

```yaml
assertions:
  - id: authenticate
    weight: 0.25

  - id: unblock_card
    weight: 0.60

  - id: caller_ack
    weight: 0.15
```

Each assertion has:

```text
verdict
evidence
oracle_type
confidence if inferential
```

Example:

```json
{
  "assertion_id": "unblock_card",
  "verdict": "satisfied",
  "oracle": "tool_event",
  "evidence": ["tool_9"]
}
```

The final motive result can be:

```text
FULFILLED
PARTIALLY_FULFILLED
NOT_FULFILLED
UNKNOWN
```

For the dashboard's 0–5 convenience scale, map the structured outcome transparently rather than letting an LLM invent a number.

---

## 10. Outcome evidence precedence

Use this order:

```text
1. External/state oracle
2. Verified tool result
3. Provider structured event
4. Conversation evidence
5. LLM-only inference
```

If sources disagree:

```text
outcome_status = CONFLICT
```

with all conflicting evidence retained.

Do not silently collapse the conflict.

---

## 11. Evidence object

```json
{
  "id": "ev_01J...",
  "metric_result_id": "mr_01J...",

  "source_type": "turn",
  "source_id": "turn_19",

  "start_ms": 11720,
  "end_ms": 13100,

  "quote": "Nahi, replacement nahi chahiye.",
  "rationale": "Caller explicitly corrected the agent."
}
```

Allowed:

```text
turn
event
tool_call
audio
state_transition
```

Audio evidence should include an exact offset so the UI can seek directly to the relevant moment.

---

## 12. Aggregate result

For each evaluator and metric:

```json
{
  "scope": "evaluator",
  "sample_count": 3,
  "coverage_count": 3,

  "mean": 4.0,
  "median": 4.0,
  "min": 3.0,
  "max": 5.0,
  "stddev": 1.0,

  "p95": null,
  "percentile_status": "insufficient_sample"
}
```

### Small-sample rule

With the MVP's three repetitions:

```text
show:
  all raw values
  mean
  median
  min
  max
  standard deviation

do not imply a stable P95 estimate
```

The schema supports P95 once the sample count crosses a configured threshold.

---

## 13. Aggregation units

For boolean:

```text
true_count
false_count
success_rate
```

For categorical:

```text
category_counts
category_percentages
```

For continuous:

```text
mean
median
min
max
stddev
optional percentiles
```

For ordinal 1–5 judge metrics:

```text
mean
median
distribution
```

Keep the complete raw sample set.

---

## 14. Coverage

Every aggregate exposes:

```text
sample_count
coverage_count
availability_ratio
```

Example:

```text
25 evaluators
× 3 runs
= 75 logical samples

metric computed for 68
metric unavailable for 7

availability = 90.67%
```

Coverage is not a score.

---

## 15. Composite score model

Never compute:

```text
(4.2 + 0.8 + 812 + 6.8) / 4
```

Instead:

```text
raw metric
   ↓
metric normalization
   ↓
0–100
   ↓
category score
   ↓
category weights
   ↓
composite
```

The source's illustrative category weights can remain configurable, e.g. motive 40%, conversation 35%, voice 15%, language 10%. fileciteturn0file0L907-L923

But the production implementation must version the actual normalization functions and coverage policy.

---

## 16. Missing metric policy

Define:

```yaml
coverage_policy:
  required_metrics:
    - motive_fulfillment
    - semantic_understanding

  optional_metrics:
    - tool_argument_correctness

  composite:
    minimum_coverage_ratio: 0.90
    renormalize_optional_weights: false
```

Preferred behavior:

```text
critical metric unavailable
→ composite = INCOMPLETE

optional metric unavailable
→ no score contribution
→ unavailable_weight reported
```

Do not silently redistribute missing weight.

---

## 17. Composite result

```json
{
  "status": "complete",
  "score_0_100": 85.4,

  "coverage_ratio": 0.97,
  "unavailable_weight": 0.03,

  "category_scores": {
    "motive_fulfillment": 88.0,
    "conversation_quality": 84.0,
    "voice_performance": 91.0,
    "language_adaptation": 79.0
  }
}
```

Dashboard must expose the coverage alongside the score.

---

## 18. Failure taxonomy

Persist normalized reason codes.

Examples:

```text
MISINTERPRETED_MOTIVE
FAILED_RECOVERY
LOST_CONTEXT
UNNECESSARY_REPETITION
UNSUPPORTED_CLAIM
POOR_CLARIFICATION
LANGUAGE_MISMATCH
INTERRUPTION_IGNORED
TOOL_SELECTION_ERROR
TOOL_ARGUMENT_ERROR
TOOL_RESULT_MISREAD
STALL
CONNECTION_FAILURE
```

One run can contain multiple reasons.

---

## 19. Result reproducibility manifest

Every final aggregate should be traceable to:

```text
evaluation_plan
execution_manifest
metric definition versions
judge versions
aggregation version
composite definition version
```

Never regenerate old results with "current" metric logic.

---

## 20. Forensic API response shape

```json
{
  "evaluation_plan": {},
  "evaluator": {},
  "run": {},
  "attempt": {},

  "summary": {
    "metrics": [],
    "scores": []
  },

  "conversation": {
    "turns": [],
    "events": [],
    "tool_calls": []
  },

  "evidence": [],
  "media": []
}
```

This supports the intended:

```text
aggregate
→ evaluator
→ run
→ turn
→ evidence
→ audio
```

forensic workflow. fileciteturn0file0L1141-L1198
