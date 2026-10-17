# Prompt 7 — Metrics, Judges, Aggregation, Results, Forensics: Progress

## Status: Complete

The evaluation pipeline is implemented. An eligible attempt is turned into
EVALUATION TRUTH: deterministic metric results (with evidence), a strictly
validated judge execution and judge-backed metrics, per-evaluator aggregates with
coverage, and a versioned composite score — all exposed through read-only result
and forensic APIs that never leak SQLAlchemy models.

## What was built

### Metrics (`metrics/`)
- `registry.MetricRegistry` / `MetricSpec` — versioned catalogue (key, version,
  value type, capabilities, evidence, implementation version, aggregation and
  normalization config). `catalog.build_default_registry()` registers every
  metric.
- `signals.AttemptSignals` — a queryable timeline over events, turns, tool calls
  and media. Derives caller/agent audibility boundaries (explicit events first,
  then speech boundaries, then media grouped by turn) and flags every derived
  value.
- `wer` — dependency-free word error rate (`agent_input_wer` /
  `independent_asr_wer` share the implementation but never the provenance).
- `deterministic` — TTFT, TTFA, interruption latency, turn/call duration,
  agent input WER, independent ASR WER, tool argument exactness, tool order
  correctness, duplicate tool calls.
- `outcome.MetricOutcome` / `EvidenceSpec` — availability contract enforced
  in-process before persistence.
- `engine.MetricEngine` + `MetricResultWriter` — capability gating, evaluation,
  result/evidence/definition persistence, `metric.computed` publication.

### Judges (`judges/`)
- `schema` — strict `StructuredJudgeOutput` (`extra="forbid"`, bounded scores,
  closed `ReasonCode` set), `parse_structured_output`, `MotiveVerdict`,
  `OracleType` and the documented precedence.
- `llm` — `LLMProvider` protocol, `OpenAIProvider` (httpx, JSON mode, fails
  fast without a key) and `StaticLLMProvider` for tests/offline runs.
- `prompt` — trusted/untrusted separation with `<untrusted_observed_data>`
  fencing (prompt-injection defense).
- `motive` — weighted assertions resolved by oracle precedence with visible
  `CONFLICT`.
- `structured` — `StructuredJudge` (malformed output → `INVALID`; provider
  failure → `ERROR`) and projection of judge output onto the judge metrics.
- `engine.JudgeEngine` — resolves the evaluable attempt, runs the judge, resolves
  motive, persists `JudgeExecution` + judge metrics with evidence, publishes
  `judge.completed`.

### Aggregation (`aggregation/`)
- `stats.aggregate` — continuous/boolean/category/ordinal statistics with
  coverage and the small-sample percentile rule (`p95 = null`,
  `insufficient_sample`).
- `composite.normalize_value` / `compute_composite` — 0-100 normalization,
  category weighting, versioned coverage policy; missing weight is reported, not
  redistributed; `COMPLETE` only when critical metrics and coverage policy hold.
- `engine.AggregationEngine` — per-evaluator aggregates (rebuilt idempotently),
  composite score, and `is_plan_evaluation_complete`.

### Storage (`storage/`)
- `ObjectStore` protocol with `LocalObjectStore` (filesystem + HMAC-signed
  short-lived URLs) and `S3ObjectStore` (presigned URLs, lazy `boto3`);
  `factory.get_object_store()` selects by `OBJECT_STORAGE_MODE`;
  `signing` implements the local signed-URL contract.

### API (`api/routes/results.py`, `schemas/results.py`, `services/results.py`)
- Plan results, per-evaluator results, run/attempt detail, paginated events,
  conversation materialization, media list, metric result + evidence, aggregates,
  composite, media URL, and the forensic bundle
  (`GET /api/v1/call-runs/{run_id}/forensics`).

### Workers (`workers/`)
- `compute_attempt_metrics`, `compute_run_judges`, `compute_plan_aggregation`
  with deterministic ARQ job identities; `enqueue_metrics/judges/aggregation`.
- `orchestration/completion.PlanCompletionService` and
  `orchestration/trigger.EvaluationTrigger` (ARQ default, best-effort) wired into
  `record_terminal_event`; runs without an eligible attempt still pass through the
  judge stage so plan completion is detected uniformly.

## Verification (all passing)
```bash
uv run pytest          # 278 passed (202 prior + 76 new)
```
New test modules:
- `test_metrics.py` — registry, WER, signals, every deterministic metric, the
  availability contract (NOT_AVAILABLE / NOT_APPLICABLE / INVALID / ERROR),
  capability gating, expected-tool extraction.
- `test_judges.py` — strict schema (unknown field / out-of-range / unknown reason
  code / malformed JSON), provider error, injection fencing, motive precedence
  and conflict, metric projection.
- `test_aggregation.py` — per-type statistics, coverage, small-sample percentile,
  normalization, composite coverage policy.
- `test_evaluation_pipeline.py` — deterministic fake target through the real
  `CallRunner`, materialized observed truth, then metrics → judge → motive →
  aggregates → composite.
- `test_storage.py`, `test_results.py`, `test_evaluation_wiring.py`.

No migration is needed: the result tables (`metric_definition`, `judge_definition`,
`judge_execution`, `metric_result`, `evidence`, `aggregate_result`,
`composite_score_definition`, `composite_score_result`) already existed from
Prompt 2.

## Decisions
`docs/decisions/0006-evaluation-pipeline-decisions.md` — versioned registry,
triple-enforced availability semantics, derived/flaggable audibility boundaries,
boundary pairing for latency, WER provenance, strict judge schema, injection
fencing, weighted-assertion motive with conflicts, coverage + percentile policy,
no weight redistribution, idempotent chained workers, completion gating,
best-effort trigger, signed media URLs, schema-only result APIs.

## What changed outside Prompt 7
- `TargetAdapter.to_canonical` now stamps arrival time (via the event builder)
  when a provider observation carries no monotonic timestamp, so latency metrics
  keep a runner-monotonic basis. Previously such events were all stamped `0`.
- `httpx` added to runtime dependencies for `OpenAIProvider`.

## Deferred to later prompts
- Prompt 8: full requirements matrix, security/observability review, global auth
  on result routes, and the end-to-end smoke test against live Postgres/Redis.
- Async materialization and secret-reference resolution at dispatch time remain
  as noted in Prompt 6.
- Real OpenAI judge calls require `OPENAI_API_KEY`; the deterministic provider
  backs local/test runs.
