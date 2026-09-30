# VoiceEval — Requirements Matrix (Prompt 8 review)

This matrix traces each documented requirement of the six source documents to
its implementation and its test, and records the status after the Prompt 8
hardening pass.

Source documents:

- `01-architecture.md` (ARCH)
- `02-domain-schema.md` (DOM)
- `03-runtime-event-schema.md` (RT)
- `04-evaluation-result-schema.md` (RES)
- `05-state-machines-validation.md` (SM)
- `VoiceEval — Backend API, Realtime Protocol & Process Flow Design v0.1.md` (API)

Status legend: **OK** implemented + tested · **HARDENED** fixed during Prompt 8 ·
**PARTIAL** implemented with a documented limitation.

Paths are relative to `backend/src/voiceeval/` and `backend/tests/`.

## Test truth / configuration

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 1 | Target + revision versioning, `UNIQUE(agent_target_id, revision_no)` / `config_hash` | DOM §4 | `db/models/domain.py::AgentTargetRevision`, migration `0002` | `test_domain_models.py::test_required_unique_constraints_present`, `test_targets.py` | OK |
| 2 | `endpoint_config` holds no raw secrets (references only) | DOM §4, ARCH §28 | `services/targets.py::find_raw_secrets` | `test_targets.py` | OK |
| 3 | Evaluator revision state machine GENERATED→DRAFT→VALIDATING→VALIDATED→APPROVED→EXECUTED | SM §1 | `domain/state_machines.py`, `services/evaluators.py` | `test_state_machines.py`, `test_services.py` | OK |
| 4 | Content-addressed revisions, `UNIQUE(content_hash)` | DOM §8 | `db/models/domain.py`, `services/evaluators.py` | `test_domain_models.py`, `test_services.py` | OK |
| 5 | Async validation (job + 202, never inline) with 9 independent validators | API §5, ARCH | `services/validation/`, `workers/jobs/validation.py` | `test_validators.py`, `test_services.py` | OK |
| 6 | Benchmark version freeze rejects mutation | DOM §12 | `services/benchmarks.py`, `db/guards.py::ensure_benchmark_version_mutable` | `test_services.py`, `test_guards.py` | OK |
| 7 | Capability negotiation at plan-prep time; required-missing is BLOCKING | ARCH §9, SM §9–10 | `services/capabilities.py::negotiate`, `services/plans.py::_negotiate` | `test_capabilities.py` | OK |
| 8 | Idempotency on state-changing requests via `Idempotency-Key` | SM §20 | `services/idempotency.py`, `api/dependencies.py` | `test_idempotency.py`, `test_api_auth.py` | HARDENED |

## Execution planning (TEST TRUTH)

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 9 | Plan state machine DRAFT→READY→QUEUED→RUNNING→PARTIAL/COMPLETED→CANCELLED | SM §2 | `domain/state_machines.py`, `services/plans.py`, `orchestration/executor.py` | `test_state_machines.py`, `test_plans.py` | OK |
| 10 | Immutable `execution_manifest` snapshotting every version + `manifest_hash` | ARCH §11, DOM §16 | `orchestration/manifest.py`, `services/plans.py` | `test_orchestration.py`, `test_plans.py` | OK |
| 11 | `run_seed` derived deterministically from plan/evaluator/repetition | ARCH §13 | `orchestration/retry.py::derive_run_seed` | `test_orchestration.py::test_run_seed_is_deterministic` | OK |
| 12 | Exactly `repeat_count` CallRuns per item; DB uniqueness as final guard | DOM §17, SM §5 | `orchestration/executor.py::expand_runs` / `ensure_runs` | `test_orchestration.py::test_expand_three_repetitions_create_exactly_three_runs` | OK |
| 13 | Retry creates a new CallAttempt, never a new CallRun/repetition | ARCH §4, SM §5 | `orchestration/executor.py::record_attempt_terminal` | `test_orchestration.py::test_retry_creates_attempt_not_run` | OK |
| 14 | Infrastructure failures retryable; semantic failures are not | SM §6 | `orchestration/retry.py::RETRYABLE_FAILURE_CLASSES` | `test_orchestration.py` | OK |
| 15 | Cancellation marks queued work, retains all attempt history | API §4 | `orchestration/executor.py::cancel_plan` | `test_orchestration.py` | OK |
| 16 | Resume never re-samples a completed repetition | API §4 | `orchestration/executor.py::resume_plan` | `test_orchestration.py::test_resume_*` | OK |

## Observed truth (runtime + realtime)

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 17 | Canonical event envelope (event_id/attempt/sequence/type/source/clocks/payload) | RT §2 | `runtime/events.py::CanonicalEventBuilder`, `realtime/protocol.py` | `test_runtime_runner.py`, `test_realtime.py` | OK |
| 18 | `UNIQUE(call_attempt_id, sequence_no)`; duplicate sequence safely ignored | RT §19–20 | `realtime/event_ingestion.py`, `db/models/runtime.py` | `test_realtime.py::test_duplicate_sequence_is_ignored` | OK |
| 19 | Provider-event dedup by `UNIQUE(source, provider_event_id)` | RT §20 | `realtime/event_ingestion.py::provider_event_exists` | `test_realtime.py::test_duplicate_provider_event_id_is_ignored` | OK |
| 20 | Raw provider events append-only; never overwritten by normalized | RT §1, §22 | `realtime/event_ingestion.py`, `alembic/versions/0004` trigger | `test_realtime.py`, live trigger check | HARDENED |
| 21 | Event materialization → call_turn / tool_call / state_transition | RT §7, §11 | `realtime/materializer.py` | `test_realtime.py`, `test_evaluation_pipeline.py` | OK |
| 22 | Runner control WS auth: scope + attempt binding; reject bad/expired/wrong token | API §5 | `realtime/runner_auth.py`, `realtime/runner_ws.py` | `test_realtime.py` | OK |
| 23 | Redis Pub/Sub families (plan/run/attempt/metric/judge/aggregate/composite) | API §5 | `realtime/pubsub.py` | `test_realtime.py` | OK |
| 24 | Live plan WS (user JWT) is observation-only, never in the audio path | API §5 | `realtime/live_ws.py` | `test_realtime.py` | OK |
| 25 | Caller state machine authoritative outside the LLM; every mutation versioned | ARCH §12, RT §11 | `runtime/caller/state.py`, `policy.py` | `test_runtime_caller.py` | OK |
| 26 | Stop-condition precedence + config timeouts; first evidence retained | SM §13–17 | `runtime/stop_conditions.py` | `test_runtime_stop_conditions.py` | OK |
| 27 | Media originals immutable; separate original/analysis representations | ARCH §14, RT §14 | `runtime/media/recorder.py`, `alembic/versions/0004` trigger | `test_runtime_media.py`, live trigger check | HARDENED |
| 28 | Three explicit clocks (monotonic / wall-clock / media) | ARCH §15 | `runtime/events.py`, `core/clocks.py` | `test_runtime_runner.py` | OK |

## Runtime execution

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 29 | `AgentConnection` boundary keeps transport ≠ provider ≠ evaluation | ARCH §8 | `runtime/connections.py`, `runtime/adapters/base.py` | `test_runtime_adapters.py` | OK |
| 30 | WebSocket implemented; WebRTC = interface + validation contract only | API §6 | `runtime/adapters/websocket.py`, `webrtc.py` | `test_runtime_adapters.py` | PARTIAL (WebRTC not executed — deferred) |
| 31 | Versioned adapter registry; unknown adapter = validation error | API §6 | `runtime/adapters/registry.py` | `test_runtime_adapters.py` | OK |
| 32 | Deterministic fake target (audio/text/turns/tools/connection events) | API §6 | `runtime/adapters/fake.py` | `test_runtime_runner.py`, `test_evaluation_pipeline.py` | OK |
| 33 | Provider abstractions TTSProvider/ASRProvider with Sarvam impls | API §6 | `runtime/providers/base.py`, `sarvam.py` | `test_runtime_providers.py` | OK |
| 34 | Transcript provenance kept distinct (caller_reference/provider_*/independent_asr) | RT §13 | `db/models/runtime.py::CallTurn`, `metrics/deterministic.py` | `test_metrics.py` | OK |

## Evaluation truth

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 35 | Versioned metric registry (key, version, value_type, capabilities, evidence) | RES §5 | `metrics/registry.py`, `metrics/catalog.py` | `test_metrics.py` | OK |
| 36 | Availability statuses COMPUTED/NOT_AVAILABLE/NOT_APPLICABLE/INVALID/ERROR distinct | RES §3, ARCH §10 | `metrics/outcome.py`, DB CHECK in `db/models/results.py` | `test_metrics.py`, `test_metric_value.py`, `test_results.py` | OK |
| 37 | Missing evidence never converted to zero | RES §3 | `metrics/engine.py::evaluate_one`, `aggregation/engine.py::_result_value` | `test_metrics.py`, `test_results.py` | OK |
| 38 | Strict judge schema; malformed → judge INVALID + metric ERROR (never coerced) | RES §6, SM §18 | `judges/schema.py`, `judges/structured.py` | `test_judges.py` | OK |
| 39 | Prompt-injection fencing of untrusted target content | ARCH §22, SM §19 | `judges/prompt.py` | `test_judges.py` | OK |
| 40 | Motive as weighted assertions; oracle precedence; conflicts visible | RES §9–10 | `judges/motive.py`, `judges/schema.py::ORACLE_PRECEDENCE` | `test_judges.py` | HARDENED (state machine + conversation tier added) |
| 41 | Evidence objects point at turn/event/tool_call/audio/state_transition with offsets | RES §11 | `db/models/results.py::Evidence`, `metrics/outcome.py` | `test_results.py`, `test_metrics.py` | OK |
| 42 | Aggregation stats per value type + coverage | RES §12–14 | `aggregation/stats.py` | `test_aggregation.py` | OK |
| 43 | Small-sample rule: p95 = null + `insufficient_sample` | RES §12, SM §23 | `aggregation/stats.py` | `test_aggregation.py`, `test_results.py` | OK |
| 44 | Composite coverage policy; critical-missing → INCOMPLETE; no weight redistribution | RES §15–17, SM §24 | `aggregation/composite.py` | `test_aggregation.py` | OK |
| 45 | Result + forensics APIs reconstruct truth without leaking models | RES §20 | `api/routes/results.py`, `services/results.py` | `test_results.py`, `test_evaluation_pipeline.py` | OK |
| 46 | Signed short-lived media URLs behind `ObjectStore` | RES § | `storage/local.py::LocalObjectStore`, `storage/s3.py` | `test_storage.py` | OK |

## Cross-cutting

| # | Requirement | Source | Implementation | Test | Status |
|---|---|---|---|---|---|
| 47 | Control-plane API requires authentication; runner token scoping; attempt isolation | ARCH §28, API §5 | `auth/dependencies.py`, router-level `require_user_dep` | `test_api_auth.py`, `test_jwt.py` | HARDENED |
| 48 | Consistent error envelope + global handlers | API | `core/errors.py`, `main.py` | `test_errors.py`, `test_api_auth.py` | OK |
| 49 | Structured JSON logs carry request_id/trace_id/plan_id/run_id/attempt_id | ARCH §31 | `core/logging.py`, `main.py` middleware, orchestrator/jobs/runner | `test_observability.py` | HARDENED |
| 50 | OTel spans around API request / ARQ job / dispatch / target / caller / metric / judge / aggregation | ARCH §31 | `observability/tracing.py` + call sites | `test_observability.py` | HARDENED |
| 51 | Immutability enforced beyond application convention | DOM, SM §22 | `db/guards.py` + `alembic/versions/0004` triggers | `test_guards.py`, live trigger check | HARDENED |
| 52 | No secret committed; `.env` ignored | ARCH §28 | `.gitignore`, `.env.example` | manual review | OK |
| 53 | Docker v1 environment (postgres/redis/minio/api/worker + disposable runner) | API | `docker-compose.yml`, `Dockerfile` | `docker compose config` | OK |
| 54 | uv-managed Python 3.13 project, async SQLAlchemy/Alembic | GLOBAL | `pyproject.toml`, `alembic/` | `uv sync`, `uv run pytest`, `alembic check` | OK |

## Known limitations (unchanged by Prompt 8)

- **WebRTC is not executed.** Only the config-validation contract exists; v1 does
  not claim generic WebRTC compatibility (ARCH §6, API §6).
- **Deterministic model behaviour is not claimed.** The judge/caller are
  deterministic in tests via fake providers; real provider output is not bitwise
  reproducible (ARCH §13).
- **Async materialization** is synchronous in v1 (recorded in `0004`/`0005`
  decisions); derived objects remain rebuildable.
- **Endpoint secret references** are validated but not resolved to a secret store
  at dispatch time (documented in the runtime decisions).
