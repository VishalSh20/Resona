# VoiceEval — State Machines, Validation & Failure Semantics v0.3

## 1. Evaluator revision state machine

```text
GENERATED
   ↓
DRAFT
   ↓
VALIDATING
   ├──── error ───→ DRAFT
   │
   └──── pass ────→ VALIDATED
                       ↓
                    APPROVED
                       ↓
                    EXECUTED
```

Once referenced by an immutable execution manifest:

```text
content cannot change
```

A user edit creates another revision.

---

## 2. Evaluation plan state machine

```text
DRAFT
  ↓
READY
  ↓
QUEUED
  ↓
RUNNING
  ├── partial failure ──→ PARTIAL
  │
  └─────────────────────→ COMPLETED
```

Any nonterminal state may become:

```text
CANCELLED
```

`COMPLETED` means all logical repetitions reached a terminal state, not that every attempt succeeded.

---

## 3. Logical call run state machine

```text
QUEUED
  ↓
RUNNING
  ↓
COMPLETED
```

Exceptional terminals:

```text
INFRASTRUCTURE_FAILED
CANCELLED
```

A run may contain several physical attempts.

---

## 4. Physical call attempt state machine

```text
QUEUED
   ↓
STARTING
   ↓
CONNECTING
   ↓
RUNNING
   ↓
TERMINATING
   ↓
TERMINAL
```

Terminal classes:

```text
COMPLETED
FAILED
TIMED_OUT
CANCELLED
```

A failed attempt is retained forever.

---

## 5. Attempt retry rule

Example:

```text
Logical Run 2

Attempt 1 → WebRTC ICE failure
Attempt 2 → target connection succeeds
```

Then:

```text
CallRun = one statistical sample
Attempts = infrastructure history
```

No extra aggregate sample is created.

---

## 6. Retry policy

Retry allowed for:

```text
runner crash
connection setup failure
transient provider failure
temporary queue/worker failure
```

Do not auto-retry a semantic failure as though it were infrastructure failure:

```text
agent misunderstood caller
caller exhausted recovery budget
motive failed
```

These are valid evaluation outcomes.

---

## 7. Evaluation eligibility

An attempt can become:

```text
eligible_for_evaluation = true
```

when it has enough evidence to support the metric set.

Examples:

### Connection failed before audio

```text
TTFA = NOT_AVAILABLE
voice metrics = NOT_AVAILABLE
connection metric = FAILED
```

### Call reached meaningful conversation but timed out

```text
conversation metrics = COMPUTABLE
motive fulfillment = FAILED/UNKNOWN depending on evidence
termination_reason = WALL_CLOCK_TIMEOUT
```

This avoids turning infrastructure failures into fake semantic failures.

---

## 8. Validation gate

An evaluator is executable only when:

```text
scenario valid
motive valid
state consistent
success conditions evaluable
behavior executable
language rules coherent
criteria evaluable
required capabilities present
```

The Product Scope explicitly requires validation for these categories. fileciteturn0file0L292-L329

---

## 9. Capability matrix

| Metric | Required signal | Missing signal |
|---|---|---|
| TTFT | target text stream | NOT_AVAILABLE |
| TTFA | agent audio + caller turn timing | NOT_AVAILABLE |
| Target-agent input WER | target input transcript | NOT_AVAILABLE |
| Independent ASR WER | caller/reference audio + independent ASR | COMPUTABLE as separate metric |
| Interruption latency | caller + agent audio timing | NOT_AVAILABLE |
| Tool selection | tool calls | NOT_AVAILABLE |
| Tool args | tool args | NOT_AVAILABLE |
| Tool result handling | tool results | NOT_AVAILABLE |
| Voice quality | agent audio | NOT_AVAILABLE |
| Language adaptation | observed agent language + caller language profile | NOT_AVAILABLE |
| Motive fulfillment | evaluable assertions | BLOCKING INVALID when required oracle is absent |

---

## 10. Capability negotiation is a plan-time operation

Do not discover missing observability halfway through 75 calls.

Before execution:

```text
target revision
   ↓
capability snapshot
   ↓
metric requirements
   ↓
evaluator requirements
   ↓
validation
   ↓
execution plan
```

The plan records the result.

---

## 11. WebRTC validation

A target claiming WebRTC support must define enough signaling information to create the peer connection.

Required contract may include:

```text
signaling URL/method
offer/answer format
ICE candidate exchange method
codec expectations
authentication mechanism
audio track expectations
```

WebRTC's own API does not define application-level signaling, so "WebRTC endpoint" alone is not sufficient as an integration contract. citeturn826333search2

---

## 12. Motive assertion state machine

```text
PENDING
  ↓
SUPPORTED_BY_EVIDENCE
  ↓
SATISFIED

or

PENDING
  ↓
CONTRADICTED
  ↓
UNSATISFIED

or

PENDING
  ↓
NO_OBSERVABLE_EVIDENCE
  ↓
UNKNOWN
```

Final motive status:

```text
FULFILLED
PARTIALLY_FULFILLED
NOT_FULFILLED
UNKNOWN
CONFLICT
```

---

## 13. Stop-condition precedence

The runtime checks terminal conditions after every normalized event.

Recommended precedence:

```text
1. NATURAL_SUCCESS
2. RECOVERY_EXHAUSTED
3. IRRECOVERABLE_OBJECTIVE_FAILURE
4. CONVERSATION_STALL
5. WALL_CLOCK_TIMEOUT
6. CONNECTION_FAILURE
```

However, retain the first triggering evidence event.

---

## 14. Natural success

Success requires all `required=true` motive assertions to be satisfied.

Example:

```text
authentication complete
AND
card unblocked
AND
caller acknowledges resolution
```

Then:

```text
caller.action = end_call
```

The source explicitly models natural success around motive fulfillment and caller acknowledgement. fileciteturn0file0L743-L757

---

## 15. Recovery budget

The caller gets:

```text
max_recovery_attempts = N
```

Every explicit correction increments:

```text
recovery_count
```

When:

```text
recovery_count > max_recovery_attempts
```

terminate with:

```text
RECOVERY_EXHAUSTED
```

Do not let the caller become endlessly forgiving; that would hide agent failures.

---

## 16. Conversation stall

Use:

```text
last meaningful agent response
```

not merely:

```text
last network packet
```

Example:

```text
no audible agent response > 10s
→ CONVERSATION_STALL
```

The source uses a 10-second example threshold. fileciteturn0file0L788-L799

---

## 17. Wall-clock timeout

MVP defaults from scope:

```text
default = 180s
maximum = 300s
```

Store the configured timeout in the execution manifest so old runs remain interpretable. fileciteturn0file0L801-L809

---

## 18. Judge validation

Judge output is accepted only if:

```text
JSON parses
schema validates
required fields exist
ranges are valid
reason codes are known
referenced evidence exists
```

Otherwise:

```text
judge_execution = INVALID
```

---

## 19. Judge injection defense

Observed target text is untrusted.

The judge prompt should conceptually be:

```text
TRUSTED INSTRUCTIONS
--------------------
evaluation policy
rubric
evaluator definition

UNTRUSTED OBSERVED DATA
-----------------------
caller text
agent text
provider events
tool payloads
```

Do not allow the target agent to modify:

```text
rubric
score range
evaluation rules
system instructions
```

---

## 20. Idempotency

Every state-changing execution request uses an idempotency key.

Example:

```text
plan:{plan_id}:execute:v1
```

The same request must not create duplicate logical repetitions.

---

## 21. Worker job model

```text
Job
├── id
├── type
├── target_id
├── attempt
├── status
├── idempotency_key
├── input_hash
├── started_at
├── finished_at
├── error_code
└── created_at
```

Safe retry:

```text
generation
validation
metrics
judging
aggregation
```

Voice calls require attempt-level retry semantics.

---

## 22. Data corruption guards

Enforce:

```text
no mutation of executed evaluator revision
no mutation of frozen benchmark version
no mutation of execution manifest
no mutation of raw runtime events
no mutation of media artifact hash/object pointer
```

If reprocessing is required:

```text
new derived result version
```

not a rewritten historical artifact.

---

## 23. Statistical safeguards

For `n < configured_percentile_min_samples`:

```text
p95 = NULL
percentile_status = insufficient_sample
```

Dashboard still exposes all raw repetitions.

The MVP's three runs therefore emphasize:

```text
run values
mean
median
range
variance/stddev
```

rather than implying precision the sample cannot support.

---

## 24. Composite safeguards

Composite score is:

```text
COMPLETE
```

only when:

```text
all critical metrics available
AND
coverage_ratio >= configured threshold
```

Otherwise:

```text
INCOMPLETE
```

with:

```text
coverage_ratio
unavailable_weight
missing_metrics
```

---

## 25. Remaining hard limitations

These cannot be fully eliminated by architecture:

### Black-box observability

A provider may not expose internal ASR, tool, or token timing. The platform must honestly report missing signals.

### Ground-truth absence

Without a state oracle or trustworthy tool/result evidence, some motive outcomes remain inferential.

### Model-judge uncertainty

LLM judgments require calibration against a human-reviewed set. Versioning lets you measure drift but does not remove it.

### Synthetic-caller realism

A synthetic caller can approximate a behavior distribution; it is not equivalent to a statistically representative population of real customers.

These are product limitations, not implementation bugs.
