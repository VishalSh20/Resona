
# VoiceEval Backend — Codex Implementation Instructions

## HOW TO USE THIS DOCUMENT

Execute these prompts sequentially in the same Codex session/repository.

Before Prompt 1, make all six design documents available to Codex:

```text
01-architecture.md
02-domain-schema.md
03-runtime-event-schema.md
04-evaluation-result-schema.md
05-state-machines-validation.md
VoiceEval — Backend API, Realtime Protocol & Process Flow Design v0.1.md
```

These documents are the product/architecture contract.

Do not silently reinterpret them.

If an implementation detail is missing from the documents, choose the simplest production-sensible implementation that preserves the documented semantics.

If two source documents genuinely conflict:

1. identify the exact conflict,
2. preserve both pieces of information in your analysis,
3. choose the least destructive implementation,
4. document the decision in `docs/decisions/`,
5. never silently change the domain semantics.

The repository is **backend-only** for this implementation.

Do not create a frontend.

---

# GLOBAL IMPLEMENTATION CONTRACT

## Runtime

Use:

```text
Python 3.13
uv
uv venv
```

Never use:

```text
pip install ...
poetry
pipenv
conda
```

Use `uv` for dependency management and execution.

Expected bootstrap:

```bash
uv venv --python 3.13
uv sync
```

Use:

```bash
uv run ...
```

for project commands.

---

# Core stack

```text
FastAPI
Pydantic v2
SQLAlchemy 2.x async
asyncpg
Alembic
PostgreSQL
Redis asyncio client
ARQ
PyJWT
websockets
OpenTelemetry
structured JSON logging
pytest
pytest-asyncio
```

Use reasonable supporting dependencies where required, but do not introduce large frameworks merely for convenience.

---

# Architectural shape

Use one Python repository/application containing:

```text
FastAPI control plane
ARQ workers
Execution orchestrator
CallRunner runtime
Target adapters
Caller runtime
Metric engine
Judge engine
Aggregation engine
Storage abstraction
Authentication
Observability
```

Do NOT turn every component into an independently deployed microservice.

The architecture intentionally uses one control-plane application plus specialized workers. The runner remains disposable and horizontally scalable. 

---

# Suggested repository layout

Adapt this to the existing repository rather than blindly replacing it:

```text
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
│
├── alembic/
│   ├── env.py
│   └── versions/
│
├── src/
│   └── voiceeval/
│       ├── main.py
│       │
│       ├── core/
│       │   ├── config.py
│       │   ├── logging.py
│       │   ├── errors.py
│       │   ├── ids.py
│       │   └── clocks.py
│       │
│       ├── auth/
│       │   ├── jwt.py
│       │   ├── dependencies.py
│       │   ├── models.py
│       │   └── service.py
│       │
│       ├── db/
│       │   ├── session.py
│       │   ├── base.py
│       │   ├── models/
│       │   └── repositories/
│       │
│       ├── schemas/
│       │
│       ├── api/
│       │   ├── dependencies.py
│       │   ├── router.py
│       │   └── routes/
│       │
│       ├── services/
│       │
│       ├── workers/
│       │   ├── arq.py
│       │   ├── jobs/
│       │   └── settings.py
│       │
│       ├── orchestration/
│       │
│       ├── realtime/
│       │   ├── runner_protocol.py
│       │   ├── runner_ws.py
│       │   ├── live_ws.py
│       │   └── event_ingestion.py
│       │
│       ├── runtime/
│       │   ├── runner/
│       │   ├── adapters/
│       │   ├── caller/
│       │   ├── media/
│       │   ├── events/
│       │   └── state/
│       │
│       ├── metrics/
│       │
│       ├── judges/
│       │
│       ├── aggregation/
│       │
│       ├── storage/
│       │
│       └── observability/
│
└── tests/
```

Do not create unnecessary abstraction layers.

Keep business logic out of route handlers.

---

# Important domain invariants

These are non-negotiable.

## 1. Three truths

Never collapse:

```text
TEST TRUTH
EvaluatorRevision + ExecutionManifest

OBSERVED TRUTH
CallAttempt + RuntimeEvent + CallTurn + ToolCall
+ MediaArtifact + StateTransition

EVALUATION TRUTH
MetricResult + JudgeExecution + Evidence
+ AggregateResult + CompositeScoreResult
```

---

## 2. CallRun vs CallAttempt

```text
CallRun = logical statistical repetition
CallAttempt = physical execution attempt
```

Example:

```text
CallRun 1

Attempt 1 → runner crash
Attempt 2 → successful conversation
```

This is still:

```text
1 statistical sample
```

not 2.

Retries must never create another `CallRun`.

The database must enforce:

```text
UNIQUE(
    evaluation_plan_id,
    plan_item_id,
    repetition_no
)
```

---

## 3. Immutable revisions

Once an evaluator revision is referenced by an execution manifest:

```text
content cannot change
```

A new edit creates a new revision.

Likewise:

```text
frozen benchmark versions are immutable
execution manifests are immutable
raw runtime events are append-only
original media artifacts are immutable
```

---

## 4. Availability semantics

Never convert missing observability to score zero.

Valid metric statuses:

```text
COMPUTED
NOT_AVAILABLE
NOT_APPLICABLE
INVALID
ERROR
```

These meanings must remain distinct.

---

## 5. Capability negotiation

Capability compatibility happens at plan preparation time:

```text
target capability snapshot
        ↓
metric requirements
        ↓
evaluator requirements
        ↓
validation
        ↓
execution plan
```

Do not discover missing observability after calls have started.

---

## 6. State machines

Implement explicit transition functions.

Do not permit arbitrary status mutation.

Evaluator:

```text
GENERATED
→ DRAFT
→ VALIDATING
→ VALIDATED
→ APPROVED
→ EXECUTED
```

Evaluation plan:

```text
DRAFT
→ READY
→ QUEUED
→ RUNNING
→ PARTIAL / COMPLETED
→ CANCELLED
```

CallRun:

```text
QUEUED
→ RUNNING
→ COMPLETED

or

INFRASTRUCTURE_FAILED
CANCELLED
```

CallAttempt:

```text
QUEUED
→ STARTING
→ CONNECTING
→ RUNNING
→ TERMINATING
→ TERMINAL
```

Terminal attempt classes:

```text
COMPLETED
FAILED
TIMED_OUT
CANCELLED
```

The state machine definitions and retry semantics are explicit in the design. 

---

# PROMPT 1 — FOUNDATION AND SKELETON

Implement the VoiceEval backend foundation.

First inspect the repository and identify:

```text
existing Python code
existing package layout
existing caller/Pipecat code
existing config
existing Docker configuration
existing tests
existing environment files
```

Do not destroy existing caller implementation if present.

Create or adapt the backend to:

```text
Python 3.13
uv
FastAPI
Pydantic v2
SQLAlchemy 2 async
PostgreSQL
Redis
ARQ
Alembic
JWT
OpenTelemetry
structured logging
```

Implement:

### Configuration

Use `pydantic-settings`.

Environment configuration must support:

```text
APP_ENV
APP_HOST
APP_PORT

DATABASE_URL

REDIS_URL

JWT_SECRET
JWT_ISSUER
JWT_ACCESS_TOKEN_EXPIRE_MINUTES

OBJECT_STORAGE_MODE=local|s3
LOCAL_OBJECT_STORAGE_PATH

S3_ENDPOINT_URL
S3_REGION
S3_BUCKET
S3_ACCESS_KEY
S3_SECRET_KEY

OPENAI_API_KEY
SARVAM_API_KEY

OTEL_EXPORTER_OTLP_ENDPOINT
```

No secret may be committed.

Create:

```text
.env.example
```

with safe placeholders.

### FastAPI

Create:

```text
GET /health
GET /ready
```

`/health` verifies process health.

`/ready` verifies dependencies required by the control plane.

### Logging

Implement structured JSON logging with:

```text
timestamp
level
logger
message
request_id
trace_id
```

### Request IDs

Accept:

```text
X-Request-ID
```

Generate one if absent.

### JWT

Implement minimal backend JWT authentication.

JWT claims should support:

```text
sub
iss
exp
iat
scope
```

Support at least:

```text
user
runner
```

scopes.

Do not build public signup or elaborate identity-management UX.

Create the smallest support model necessary for RBAC.

### IDs

Use ULID-style identifiers with domain prefixes for externally visible entities:

```text
agt_
targetrev_
td_
tdrev_
eval_
evalrev_
bench_
benchver_
plan_
planitem_
manifest_
run_
att_
turn_
evt_
media_
tool_
state_
metric_
judge_
evidence_
job_
```

Use a proper identifier abstraction rather than manually concatenating strings.

### Error handling

Create a consistent API error envelope:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "...",
    "request_id": "..."
  }
}
```

Add global exception handling.

### Docker

Create a v1 local environment containing:

```text
api
worker
runner
postgres
redis
minio
```

The runner may initially be a manually dispatchable or ARQ-created container process.

### Acceptance criteria

Must pass:

```bash
uv sync
uv run pytest
uv run alembic upgrade head
docker compose config
```

and:

```bash
uv run uvicorn voiceeval.main:app --reload
```

must start successfully.

Do not proceed into business-domain implementation until this foundation is clean.

---

# PROMPT 2 — DOMAIN MODEL, SQLAlchemy, MIGRATIONS

Implement the complete domain persistence layer from:

```text
02-domain-schema.md
03-runtime-event-schema.md
04-evaluation-result-schema.md
05-state-machines-validation.md
```

Create SQLAlchemy 2 async models and Alembic migrations.

Implement at minimum:

```text
agent_target
agent_target_revision

test_descriptor
test_descriptor_revision

evaluator
evaluator_revision
validation_report

benchmark
benchmark_version
benchmark_case

evaluation_plan
evaluation_plan_item

execution_manifest

call_run
call_attempt
call_turn
runtime_event
tool_call
state_transition
media_artifact

metric_definition
judge_definition
judge_execution
metric_result
evidence

aggregate_result
composite_score_definition
composite_score_result
```

Also create only the required infrastructure/support tables, such as:

```text
users
user_roles
idempotency_keys
jobs
```

Keep support tables clearly separated from domain tables.

## Database requirements

Use PostgreSQL-native types where appropriate.

Use:

```text
TIMESTAMPTZ
JSONB
foreign keys
unique constraints
check constraints
```

Prefer relational columns for:

```text
identity
status
timestamps
foreign keys
version numbers
metric keys
enum-like values
```

Use JSONB for:

```text
evaluator content
provider metadata
capability maps
judge outputs
structured configuration
snapshots
```

## Required constraints

Implement:

```text
UNIQUE(agent_target_id, revision_no)

UNIQUE(agent_target_id, config_hash)

UNIQUE(evaluator_id, revision_no)

UNIQUE(content_hash)

UNIQUE(evaluation_plan_id, plan_item_id, repetition_no)

UNIQUE(call_attempt.call_run_id, attempt_no)

UNIQUE(runtime_event.call_attempt_id, sequence_no)
```

and the relevant constraints from the schemas.

For `metric_result`, enforce that exactly the value representation corresponding to the metric's `value_type` is used.

## Immutability

Do not rely only on application convention.

Create service-level guards and database-level constraints where practical to prevent mutation of:

```text
executed evaluator revisions
frozen benchmark versions
execution manifests
raw runtime events
original media metadata/hash
```

## Repositories

Create repositories for domain operations rather than generic CRUD everywhere.

Examples:

```text
TargetRepository
EvaluatorRepository
BenchmarkRepository
EvaluationPlanRepository
CallRunRepository
CallAttemptRepository
RuntimeEventRepository
MetricRepository
JudgeRepository
ResultRepository
```

Repositories must use SQLAlchemy 2 async sessions.

Do not leak SQLAlchemy models into the API schema layer.

Create dedicated Pydantic models for request/response contracts.

## Acceptance criteria

Verify:

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run pytest
```

Verify all foreign keys and uniqueness constraints are represented in migrations.

---

# PROMPT 3 — REST API + VALIDATION + CAPABILITY NEGOTIATION

Implement the configuration and evaluator API surfaces.

Base:

```text
/api/v1
```

Implement:

## Targets

```http
POST /api/v1/targets
GET /api/v1/targets
GET /api/v1/targets/{id}

POST /api/v1/targets/{id}/revisions
GET /api/v1/targets/{id}/revisions
GET /api/v1/targets/{id}/revisions/{revision_id}
```

For target revision creation:

```text
validate endpoint config
↓
validate adapter exists
↓
validate capability snapshot
↓
validate transport
↓
calculate config_hash
↓
persist
```

Never store raw secrets in `endpoint_config`.

Allow secret references only.

## Evaluators

Implement:

```http
POST /api/v1/evaluators
GET /api/v1/evaluators
GET /api/v1/evaluators/{id}

POST /api/v1/evaluators/{id}/revisions
GET /api/v1/evaluator-revisions/{id}

POST /api/v1/evaluator-revisions/{id}/validate
POST /api/v1/evaluator-revisions/{id}/approve
```

Evaluator revision creation produces:

```text
DRAFT
```

Validation must be asynchronous.

The endpoint:

```text
POST /api/v1/evaluator-revisions/{id}/validate
```

must:

```text
verify revision state
set VALIDATING
create job
enqueue validation job
return 202
```

Do not execute validation inline.

## Validation worker

Implement independent validators for:

```text
schema
scenario
motive
state
success conditions
behaviour
language
criteria
capabilities
```

Aggregate their results into:

```text
ValidationReport
```

Validation should produce:

```text
blocking errors
warnings
checks
status
validator version
```

## Capability matrix

Build a registry like:

```python
MetricRequirement(
    metric_key="ttft",
    required_capabilities={"target_text_stream"},
)
```

Implement documented capability rules including:

```text
TTFT
TTFA
target-agent input WER
independent ASR WER
interruption latency
tool selection
tool arguments
tool result handling
voice quality
language adaptation
motive fulfillment
```

Required missing capabilities:

```text
BLOCKING
```

Optional missing capabilities:

```text
warning
NOT_AVAILABLE during evaluation
```

Do not convert unsupported metrics to zero.

## Benchmarks

Implement:

```http
POST /api/v1/benchmarks
GET /api/v1/benchmarks
GET /api/v1/benchmarks/{id}

POST /api/v1/benchmarks/{id}/versions
POST /api/v1/benchmark-versions/{id}/freeze
GET /api/v1/benchmark-versions/{id}
```

Frozen benchmark versions must reject mutation.

## API behaviour

State-changing endpoints need idempotency where the design specifies it.

Use:

```text
Idempotency-Key
```

and persist request/result identity in an infrastructure idempotency table.

## Acceptance criteria

Write tests covering:

```text
duplicate revision number
duplicate config hash
invalid evaluator content
validation job creation
required capability missing
optional capability missing
invalid state transitions
frozen benchmark mutation
approved evaluator mutation
idempotent requests
```

---

# PROMPT 4 — PLAN PREPARATION, MANIFEST, ARQ, ORCHESTRATION

Implement execution planning and orchestration.

## Evaluation Plan API

Implement:

```http
POST /api/v1/evaluation-plans
GET /api/v1/evaluation-plans
GET /api/v1/evaluation-plans/{id}

POST /api/v1/evaluation-plans/{id}/prepare
POST /api/v1/evaluation-plans/{id}/execute
POST /api/v1/evaluation-plans/{id}/cancel
POST /api/v1/evaluation-plans/{id}/resume
```

## Plan creation

Support:

```text
kind=custom
kind=benchmark
```

Validate:

```text
benchmark kind requires benchmark_version_id
custom kind requires appropriate custom source
repeat_count >= 1
target revision exists
```

## Plan preparation

Preparation is a major domain operation.

Implement:

```text
load target revision
↓
load evaluator revisions
↓
verify evaluator revisions APPROVED
↓
resolve metrics
↓
resolve judges
↓
resolve aggregation definition
↓
capability negotiation
↓
create immutable ExecutionManifest
↓
expand EvaluationPlanItem
↓
READY
```

The execution manifest must snapshot:

```text
target
evaluators
benchmark
caller configuration
metrics
judges
aggregation
composite definition
runtime versions
adapter versions
policy versions
```

Store hashes.

Compute:

```text
manifest_hash
```

The manifest becomes immutable.

## Reproducibility

Store runtime information such as:

```text
runner_version
adapter_version
caller policy version
TTS model/version
ASR model/version
LLM model/version
metric implementation versions
judge versions
aggregation version
```

Also store:

```text
run_seed
```

Derive it deterministically from plan/evaluator/repetition identity.

## CallRun expansion

For each:

```text
EvaluationPlanItem
```

create exactly:

```text
repeat_count
```

logical runs.

For repeat_count = 3:

```text
repetition_no 1
repetition_no 2
repetition_no 3
```

Never duplicate them.

Use the database uniqueness constraint as the final guard.

## ARQ

Use ARQ with Redis.

Create queues/functions for:

```text
validation
generation
execution
metrics
judges
aggregation
```

Use deterministic job identities.

Infrastructure failures should be retryable.

Semantic failures must NOT be retried automatically as infrastructure failures.

Retryable categories:

```text
runner crash
connection setup failure
temporary queue/worker failure
transient provider failure
```

Do not automatically retry:

```text
motive failed
agent misunderstood
caller recovery exhausted
semantic evaluation failure
```

## Orchestrator

Implement:

```text
execution.plan.start
execution.run.start
execution.attempt.start
```

The orchestrator should:

```text
Plan
↓
CallRuns
↓
CallAttempts
↓
runner dispatch
```

An attempt must reference:

```text
call_run_id
execution_manifest_id
target_revision_id
evaluator_revision_id
run_seed
trace_id
```

## Retry semantics

For:

```text
CallRun repetition 2
```

if:

```text
Attempt 1 = infrastructure failure
```

then:

```text
Attempt 2
```

must reference the same `CallRun`.

Never create:

```text
CallRun repetition 2.5
```

or another repetition.

## Plan cancellation

Cancellation should:

```text
mark queued work cancelled
signal running attempts
retain all attempt history
```

Do not delete runtime evidence.

## Acceptance criteria

Write tests for:

```text
plan idempotency
duplicate execution requests
manifest immutability
3 repetitions create exactly 3 CallRuns
retry creates attempts, not CallRuns
semantic failure is not retried
infrastructure failure is retryable
plan cancellation
resume semantics
```

---

# PROMPT 5 — RUNNER CONTROL WEBSOCKET + RUNTIME EVENTS

Implement the backend-side realtime control plane.

This is NOT the target-agent WebSocket.

It is:

```text
Runner ↔ VoiceEval Backend
```

Route:

```text
WS /internal/v1/attempts/{attempt_id}/stream
```

The design intentionally separates this channel from the actual voice connection to the third-party target.

## Runner authentication

The backend generates a short-lived JWT for each runner.

Claims:

```text
sub=runner_id
attempt_id
scope=runner
exp
```

The WebSocket must reject:

```text
invalid token
expired token
wrong attempt_id
missing runner scope
```

## Protocol

Support:

### Runner → Backend

```json
{
  "type": "runner.register",
  "attempt_id": "att_...",
  "runner_id": "runner_...",
  "runner_version": "..."
}
```

Heartbeat:

```json
{
  "type": "runner.heartbeat",
  "attempt_id": "att_...",
  "monotonic_ms": 48291
}
```

Runtime event:

```json
{
  "type": "runtime.event",
  "event": {
    "event_id": "evt_...",
    "call_attempt_id": "att_...",
    "sequence": 184,
    "type": "agent.audible.start",
    "source": "derived",
    "monotonic_ms": 12420,
    "wall_clock": "...",
    "media_timestamp": 918273,
    "turn_id": "turn_17",
    "payload": {}
  }
}
```

### Backend → Runner

Cancellation:

```json
{
  "type": "attempt.cancel",
  "reason": "USER_REQUESTED"
}
```

Termination:

```json
{
  "type": "attempt.terminate",
  "reason": "PLAN_CANCELLED"
}
```

Heartbeat acknowledgement:

```json
{
  "type": "runner.heartbeat_ack",
  "server_time": "..."
}
```

## Runtime event ingestion

Runtime events must preserve:

```text
event_id
call_attempt_id
sequence
type
source
monotonic_ms
wall_clock
payload
```

Optional:

```text
media_timestamp
turn_id
provider_event_id
```

## Sequence enforcement

Enforce:

```text
UNIQUE(call_attempt_id, sequence)
```

Reject or safely deduplicate duplicate events.

Provider event IDs should additionally support deduplication when available.

## Event sources

Support:

```text
provider_raw
provider_normalized
runtime
derived
caller
metric
```

Raw provider events must remain intact.

Do not overwrite:

```text
provider_raw
```

with normalized events.

## Event materialization

Normalize into:

```text
runtime_event
call_turn
tool_call
state_transition
language events
derived events
```

Raw events are append-only.

Derived objects must be rebuildable.

## Pub/Sub

Publish relevant state changes through Redis Pub/Sub so live API subscribers can receive:

```text
plan.status.changed
run.status.changed
attempt.status.changed
metric.computed
judge.completed
aggregate.updated
composite.updated
```

## Live plan WebSocket

Implement:

```text
WS /api/v1/evaluation-plans/{plan_id}/live
```

Authentication:

```text
normal JWT
```

This channel is for UI/backend observation.

It is not allowed to become part of the audio path.

## Acceptance criteria

Tests must cover:

```text
runner authentication
invalid runner token
wrong attempt token
register
heartbeat
cancel
terminate
runtime event ingestion
duplicate event sequence
provider_event_id deduplication
live Redis Pub/Sub fanout
```

---

# PROMPT 6 — CALLRUNNER + TARGET ADAPTERS + PIPECAT CALLER

Now implement the realtime execution runtime.

This is the most technically sensitive part.

## Core boundary

Implement:

```python
class AgentConnection(Protocol):
    async def connect(self, config: ConnectionConfig) -> None: ...
    async def send_audio(self, chunk: AudioChunk) -> None: ...
    async def receive(self) -> AsyncIterator[RawAgentEvent]: ...
    async def close(self, reason: CloseReason) -> None: ...
    def capabilities(self) -> CapabilitySnapshot: ...
```

Keep these concepts separate:

```text
transport
provider semantics
evaluation semantics
```

## Target adapter hierarchy

Create:

```text
TargetAdapter
WebSocketAdapter
WebRTCAdapter
```

For v1:

```text
WebSocket = implemented
WebRTC = interface + validation contract only
```

Do not implement WebRTC media transport yet.

Do not falsely claim generic WebRTC compatibility.

WebRTC configuration must support the eventual concept of:

```text
signaling URL/method
SDP offer/answer
ICE
codec requirements
authentication
audio tracks
```

## WebSocket

Use:

```text
websockets
```

Build:

```text
WebSocketTransport
FrameDecoder
ProviderProtocolDecoder
CanonicalEventBuilder
```

Never assume:

```text
1 websocket message = 1 audio frame
1 websocket message = 1 turn
```

Protocol semantics belong to provider adapters.

## Adapter registry

Implement something like:

```python
AdapterRegistry.register(...)
AdapterRegistry.get(adapter_name, adapter_version)
```

Version adapters explicitly.

Unknown adapter:

```text
validation error
```

## Test adapter

Implement a deterministic fake target adapter/server for local testing.

It must be capable of emitting:

```text
audio
text
turns
tool calls
connection events
```

This gives the runtime a deterministic integration environment without depending on a real third-party provider.

---

# PIPECAT CALLER

The synthetic caller is a first-class runtime component.

Do not embed caller intelligence inside FastAPI route handlers or the orchestrator.

Create:

```text
CallerController
ScenarioState
PolicyEngine
ActionSelector
LanguageController
```

and a clear interface around the Pipecat implementation.

The caller loop must remain:

```text
Observed Agent Output
↓
State Update / Policy Evaluation
↓
Action Selection
↓
Natural-language realization
↓
TTS
↓
Audio transmission
```

The LLM must not become the authoritative scenario state machine.

The state machine owns:

```text
facts
user_goal
current_intent
authentication_state
known_information
recovery_count
allowed_actions
conversation_phase
terminal_status
```

## State versioning

Every state mutation increments:

```text
state_version
```

Create:

```text
StateTransition
```

for every state mutation.

Do not only store final state.

## Pipecat

Integrate the caller with Pipecat as the orchestration/runtime layer.

Reuse existing caller/Pipecat code in the repository if present.

Do not duplicate connectors unnecessarily.

The interface should support:

```text
start()
observe_agent_event(...)
select_action(...)
realize(...)
stream_audio(...)
stop()
```

## Sarvam

Implement provider interfaces for:

```text
Sarvam Bulbul streaming TTS
Sarvam Saaras streaming ASR
```

Keep provider credentials in configuration.

Do not hardcode secrets.

Do not couple the entire caller implementation to Sarvam-specific APIs.

Create provider abstractions:

```text
TTSProvider
ASRProvider
```

with Sarvam implementations.

The actual caller TTS/audio stream must be represented with canonical runtime events.

## Important provenance distinction

Never confuse:

```text
caller reference text
provider target input transcript
provider target output transcript
independent ASR transcript
```

The runtime schema deliberately keeps those provenance classes separate.

## Media

Create:

```text
AudioSource
TTS
Resampler
VAD
MediaRecorder
```

Maintain:

```text
original
analysis
clip/mixed where needed
```

Original artifacts are immutable.

Capture:

```text
runner monotonic timestamp
media/RTP timestamp where available
wall-clock timestamp
```

Never assume those clocks are identical.

## Canonical events

Implement at minimum:

```text
connection.*
caller.media.*
caller.speech.*
caller.audible.*
agent.media.*
agent.speech.*
agent.audible.*
agent.text.*
turn.*
caller.language.*
agent.language.*
tool.*
caller.action.*
caller.state.*
```

## StopConditionEngine

Evaluate after every normalized event.

Precedence:

```text
NATURAL_SUCCESS
RECOVERY_EXHAUSTED
IRRECOVERABLE_OBJECTIVE_FAILURE
CONVERSATION_STALL
WALL_CLOCK_TIMEOUT
CONNECTION_FAILURE
```

Retain the triggering evidence event.

Defaults:

```text
conversation stall = 10 seconds
wall-clock timeout = 180 seconds
maximum wall-clock timeout = 300 seconds
```

Make them configuration/manifest values, not hidden constants.

## Natural success

Require all required motive assertions.

For example:

```text
authentication complete
AND
objective fulfilled
AND
caller acknowledges resolution
```

then:

```text
caller.action.selected(end_call)
caller.terminal
attempt.terminal
```

## Recovery

Track:

```text
recovery_count
```

and prevent the caller from becoming infinitely forgiving.

Recovery exhaustion is a semantic result, not automatically an infrastructure failure.

## Runner lifecycle

Implement:

```text
QUEUED
STARTING
CONNECTING
RUNNING
TERMINATING
TERMINAL
```

Persist all transitions.

## Acceptance criteria

A deterministic fake target must be able to execute an end-to-end conversation through the CallRunner.

Verify:

```text
caller audio generated
target receives audio
target sends output
events normalized
turns materialized
tool calls materialized
state transitions stored
stop conditions evaluated
attempt terminated
runner telemetry delivered to backend
```

---

# PROMPT 7 — METRICS, JUDGES, AGGREGATION, RESULTS, FORENSICS

Implement the evaluation pipeline.

Architecture:

```text
eligible CallAttempt
↓
Metric Worker
↓
deterministic metric results
↓
Judge Worker
↓
judge executions
↓
Metric Results
↓
Aggregation Worker
↓
Aggregate Results
↓
Composite computation
↓
Composite Score
```

## Metric registry

Implement a versioned registry:

```python
MetricRegistry.register(...)
```

Each metric definition includes:

```text
metric_key
version
family
value_type
unit
required_capabilities
required_evidence
implementation_version
aggregation_config
normalization_config
```

## Deterministic metrics

Implement the architecture-supported deterministic metrics:

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

Do not invent target-agent input WER when the target does not expose target-input transcript data.

Correct semantics:

```text
target-agent input WER
=
caller reference
vs
target exposed input transcript
```

If target input transcript does not exist:

```text
NOT_AVAILABLE
```

Independent ASR WER must remain a separate metric.

## TTFT

Use:

```text
caller.audible.end
→ agent.text.first
```

only when target text streaming is actually exposed.

## TTFA

Use:

```text
caller.audible.end
→ agent.audible.start
```

with explicit clock basis.

## Interruption latency

Measure from:

```text
caller speech start
```

to:

```text
agent audible end
```

according to the documented event semantics.

## Judge definitions

Implement:

```text
JudgeDefinition
JudgeExecution
```

Create:

```python
LLMProvider(Protocol)
```

with an OpenAI implementation first.

Do not make OpenAI calls directly throughout the application.

Use:

```text
LLMProvider
↓
OpenAIProvider
```

## Structured judge

The structured judge must produce a strict Pydantic schema containing fields such as:

```text
motive_fulfilled
semantic_understanding
response_clarity
context_retention
language_adaptation
reason_codes
```

Validate:

```text
JSON syntax
schema
required fields
ranges
known reason codes
evidence references
```

Malformed output:

```text
judge_execution = INVALID
metric_result = ERROR
```

Never coerce malformed output.

## Prompt injection defense

Observed target text is untrusted.

Conceptually separate:

```text
TRUSTED
evaluation policy
rubric
evaluator definition

UNTRUSTED
caller text
agent text
provider events
tool payloads
```

Never allow observed target text to modify:

```text
rubric
system instructions
score ranges
evaluation rules
```

## LLM judge

The LLM judge should explain:

```text
what failed
what was misunderstood
which turns support the conclusion
what should have happened
which failure pattern applies
```

It should not recompute deterministic latency metrics.

## Motive fulfillment

Represent it as weighted assertions.

Each assertion records:

```text
verdict
evidence
oracle_type
confidence where inferential
```

Supported outcomes:

```text
FULFILLED
PARTIALLY_FULFILLED
NOT_FULFILLED
UNKNOWN
CONFLICT
```

Evidence precedence:

```text
external/state oracle
verified tool result
provider structured event
conversation evidence
LLM-only inference
```

Conflicts must remain visible.

## Evidence

Implement evidence objects that point to:

```text
turn
event
tool_call
audio
state_transition
```

Audio evidence must retain:

```text
start_ms
end_ms
```

so the UI can seek to the relevant region.

## Aggregation

For continuous metrics:

```text
mean
median
min
max
stddev
```

For boolean metrics:

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

For ordinal:

```text
mean
median
distribution
```

Expose:

```text
sample_count
coverage_count
availability_ratio
```

For n=3:

```text
p95 = null
percentile_status = insufficient_sample
```

Never imply that 3 samples provide a stable P95 estimate.

## Composite

Pipeline:

```text
raw metric
↓
normalization
↓
0-100
↓
category score
↓
category weighting
↓
composite
```

The normalization and coverage policies must be versioned.

Do not silently redistribute missing metric weight.

Composite:

```text
COMPLETE
```

only when critical metric requirements and coverage policy are satisfied.

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

## Result APIs

Implement:

```http
GET /api/v1/evaluation-plans/{plan_id}/results

GET /api/v1/evaluation-plans/{plan_id}/evaluators/{evaluator_revision_id}/results

GET /api/v1/call-runs/{run_id}

GET /api/v1/call-runs/{run_id}/forensics}

GET /api/v1/call-attempts/{attempt_id}

GET /api/v1/call-attempts/{attempt_id}/events

GET /api/v1/call-attempts/{attempt_id}/conversation

GET /api/v1/call-attempts/{attempt_id}/media

GET /api/v1/metric-results/{metric_result_id}

GET /api/v1/metric-results/{metric_result_id}/evidence

GET /api/v1/evaluation-plans/{plan_id}/aggregates

GET /api/v1/evaluation-plans/{plan_id}/composite
```

Implement pagination for potentially large event collections.

## Media URL

Do not stream large media through PostgreSQL.

Implement:

```http
GET /api/v1/media/{media_artifact_id}/url
```

Return a short-lived URL.

Use:

```text
LocalObjectStore
S3ObjectStore
```

behind:

```python
ObjectStore(Protocol)
```

For local storage, use an equivalent short-lived signed/internal access mechanism so the API contract remains consistent.

## Forensics

The forensics endpoint should reconstruct:

```text
evaluation plan
evaluator
run
attempt
metrics
judges
conversation
events
tool calls
state transitions
evidence
media
```

The intended debugging chain is:

```text
aggregate
↓
evaluator
↓
run
↓
turn
↓
evidence
↓
audio
```

## Acceptance criteria

A completed fake-target evaluation must produce:

```text
CallRun
CallAttempt
RuntimeEvents
CallTurns
ToolCalls
StateTransitions
MediaArtifacts
MetricResults
JudgeExecutions
Evidence
AggregateResults
CompositeScoreResult
```

and the result APIs must reconstruct the execution without directly exposing SQLAlchemy models.

---

# PROMPT 8 — HARDENING, TESTS, DOCUMENTATION

Now perform a full implementation review.

Do not immediately rewrite everything.

Inspect the implementation against all six source documents.

Build a requirements matrix:

```text
requirement
source document
implementation location
test location
status
```

Identify:

```text
missing behaviour
incorrect semantics
race conditions
duplicate execution paths
status transition violations
idempotency holes
immutability holes
event ordering bugs
retry bugs
missing capability guards
provenance confusion
security issues
```

## Testing strategy

Keep testing intentionally simple for v1.

Use:

```text
pytest
pytest-asyncio
unittest.mock
httpx AsyncClient
```

Do not add Testcontainers or a large integration-test framework in this phase.

Focus on:

### Domain tests

```text
state machines
immutability
repetition uniqueness
manifest hashing
metric status semantics
motive assertion transitions
```

### API tests

```text
request validation
authentication
authorization
idempotency
HTTP status codes
error envelopes
```

### Worker tests

```text
job payload
retry decisions
deterministic job identity
orchestrator expansion
completion detection
aggregation triggering
```

### Realtime tests

```text
runner protocol
heartbeat
cancel
event envelope
sequence enforcement
deduplication
Redis pub/sub
```

### Runtime tests

Use the deterministic fake voice target.

Verify:

```text
caller → target audio
target → caller output
event normalization
turn generation
tool call extraction
state transition recording
stop condition precedence
attempt termination
```

### Evaluation tests

Verify:

```text
TTFT
TTFA
NOT_AVAILABLE
NOT_APPLICABLE
INVALID
ERROR
WER provenance
judge schema validation
evidence references
aggregate calculations
coverage
composite coverage policy
```

## Security review

Verify:

```text
no secrets in endpoint_config
JWT validation
runner token scoping
attempt isolation
authorization on plan/run/attempt access
signed media URLs
provider payload treated as untrusted
LLM judge injection defense
```

## Observability review

Every important execution path should carry:

```text
request_id
trace_id
plan_id
run_id
attempt_id
```

Use OpenTelemetry spans around:

```text
API request
ARQ job
orchestrator dispatch
target connection
caller execution
metric computation
judge invocation
aggregation
```

Do not emit sensitive secrets into logs.

## Docker review

`docker compose up` should start:

```text
postgres
redis
minio
api
worker
```

and the runner should be runnable as a disposable service/container.

Provide:

```text
docker compose up -d
docker compose logs
```

instructions in README.

## Documentation

Update `README.md` with:

```text
architecture
local setup
uv commands
environment variables
database migrations
docker setup
worker execution
runner execution
API usage
example evaluation lifecycle
test commands
```

Create:

```text
docs/decisions/
```

for implementation decisions that were not explicitly specified by the design documents.

Do not rewrite the six source documents.

## Final verification

Run:

```bash
uv sync
uv run pytest
uv run alembic upgrade head
docker compose config
```

Then perform an end-to-end local smoke test:

```text
create target
↓
create target revision
↓
create evaluator revision
↓
validate evaluator
↓
approve evaluator
↓
create plan
↓
prepare plan
↓
execute plan
↓
fake target call
↓
runtime evidence
↓
metrics
↓
judge
↓
aggregation
↓
composite
↓
forensic result retrieval
```

At the end, report:

```text
implemented
partially implemented
known limitations
deferred WebRTC work
remaining provider-specific adapters
```

Do not claim WebRTC compatibility in v1.

Do not claim deterministic model behaviour where the upstream model/provider is nondeterministic.

Do not claim a metric was computed when its required evidence was unavailable.

---

# FINAL CODING RULES FOR ALL PROMPTS

1. Prefer boring, explicit code over clever abstractions.

2. Domain semantics beat framework convenience.

3. Never put realtime audio in the FastAPI control-plane request lifecycle.

4. Never make the browser part of the voice/media path.

5. Never let retries create additional statistical samples.

6. Never silently convert missing evidence into zero.

7. Never mutate immutable execution truth.

8. Preserve raw provider evidence.

9. Preserve provenance for all transcripts.

10. Keep target transport adapters separate from evaluation logic.

11. Keep caller state authoritative outside the LLM.

12. Keep LLM providers behind interfaces.

13. Keep storage providers behind interfaces.

14. Keep target adapters behind interfaces.

15. Keep metric definitions/versioning explicit.

16. Keep judge outputs schema-validated.

17. Treat observed target content as untrusted input.

18. Keep the implementation v1-local and Docker-runnable.

19. Avoid premature microservices.

20. Do not implement the frontend.

21. When a source document specifies a semantic invariant, encode it in code and test it.

22. When the documents are silent, make the least complex implementation choice and document it rather than expanding scope.