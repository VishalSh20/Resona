# Evaluation pipeline decisions (Prompt 7)

## 1. Metrics are a versioned registry, not scattered functions

`MetricRegistry` maps `(metric_key, version)` to a `MetricSpec` carrying the
value type, required capabilities, required evidence, implementation version and
versioned aggregation/normalization configuration. `MetricDefinition` rows are
created lazily and cached per write, so a metric's definition is part of the
persisted record and old results are never regenerated with new logic. The
default catalogue lives in `metrics/catalog.py` and registers both deterministic
and judge-backed metrics, so aggregation and composite normalization treat every
metric uniformly.

## 2. Availability semantics are enforced in three places, never collapsed to zero

The five statuses (`COMPUTED`, `NOT_AVAILABLE`, `NOT_APPLICABLE`, `INVALID`,
`ERROR`) are distinct at the database check constraint, at the repository
(`_validate_value_representation`), and at `MetricOutcome.validate()` before
persistence. Missing required capabilities are checked *before* a metric runs and
produce `NOT_AVAILABLE` with the missing capabilities recorded in the
measurement basis. A metric that raises becomes `ERROR`; a scenario that does not
exercise a metric is `NOT_APPLICABLE`.

## 3. Derived audibility boundaries are explicit and flagged

The runner does not currently emit `agent.audible.*` events, and provider messages
may carry no monotonic timestamp. `AttemptSignals` therefore (a) stamps arrival
time when a provider omits a timestamp (in `TargetAdapter.to_canonical`, via the
event builder) so latency keeps a runner-monotonic basis, and (b) derives
audibility windows — explicit audible events first, then declared agent speech
boundaries, then media activity grouped by turn. Every derived boundary is
flagged (`*_derived` in the measurement basis) so provenance stays explicit.

## 4. Latency metrics pair their boundary events

TTFT is not "first agent text minus last caller utterance". It is the first
`agent.text.first` that has a preceding `caller.audible.end`, paired with that
end. TTFA pairs the first agent audible onset with the preceding caller audible
end. Interruption latency looks for a caller speech onset strictly inside an
agent audibility window. A separate `interruption_detected` flag and the clock
domain are always recorded.

## 5. WER provenance is preserved by keeping two metrics

`agent_input_wer` compares caller reference text against the target's *own*
exposed input transcript (`provider_target_input`) and is `NOT_AVAILABLE` when
that does not exist. `independent_asr_wer` compares against our own ASR
(`independent_asr`). They share a WER implementation but never the same name or
provenance.

## 6. Judge output is strict; malformed output is never coerced

`StructuredJudgeOutput` is `extra="forbid"` with bounded scores and a closed
`ReasonCode` enum. Malformed JSON, unknown fields, out-of-range values or unknown
reason codes raise `JudgeOutputInvalid`, which sets `judge_execution = INVALID`
and the judge metrics to `ERROR` (`metric_result = ERROR`). A provider/transport
failure is `ERROR`, kept distinct from a schema failure.

## 7. Untrusted observed text is fenced away from scoring instructions

`judges/prompt.py` puts the evaluator rubric, objective and deterministic summary
in the trusted section and wraps the transcript and tool payloads in
`<untrusted_observed_data>` tags, with system instructions that forbid obeying
anything inside them and forbid changing the rubric, ranges or output fields.
This is the prompt-injection defense the design calls for.

## 8. Motive is weighted assertions with visible conflicts

`resolve_motive` evaluates the documented oracle precedence (external/state,
verified tool result, provider structured event, conversation evidence, LLM
inference). Disagreeing oracles produce `CONFLICT`, which is retained instead of
being collapsed. The final status is one of `FULFILLED / PARTIALLY_FULFILLED /
NOT_FULFILLED / UNKNOWN / CONFLICT`.

## 9. Aggregation exposes coverage; percentiles respect sample size

`aggregate` shapes statistics by value type (continuous/boolean/category/ordinal)
and always reports `sample_count`, `coverage_count` and `availability_ratio`. With
the MVP's three repetitions, `p95` is `null` and `percentile_status` is
`insufficient_sample`; P95 is only computed once the sample crosses a configured
threshold (default 20).

## 10. Composite never redistributes missing weight

`compute_composite` normalizes each metric to 0-100 using its versioned
normalization config, weights within a category, then weights categories
(motive 40 / conversation 35 / voice 15 / language 10). A category with no
available metric still carries its weight into `unavailable_weight`. The result is
`COMPLETE` only when no critical metric is missing and coverage meets the policy;
otherwise `INCOMPLETE`. A required metric that was never supplied counts as
missing.

## 11. Evaluation is a chained, idempotent worker pipeline

`attempt.terminal` (eligible) -> `compute_attempt_metrics` -> `compute_run_judges`
-> `compute_plan_aggregation`, each enqueued with a deterministic ARQ job id so
redispatch cannot duplicate work. Runs without an eligible attempt still pass
through the judge stage and no-op. Plan completion is detected by
`PlanCompletionService` and aggregation is enqueued only once
`AggregationEngine.is_plan_evaluation_complete` is true — i.e. every run is
terminal and either has no eligible attempt or already has a judge execution.
This avoids aggregating before the last run's judges finish.

## 12. The evaluation trigger is a best-effort seam

`orchestration/trigger.py` is the boundary between orchestration and evaluation
workers. `ArqEvaluationTrigger` (default) enqueues; failures are logged, never
raised, so losing an enqueue cannot fail the state change that produced it. Tests
can install `NoOpEvaluationTrigger`.

## 13. Media is served by short-lived URLs, never through PostgreSQL

`ObjectStore` has `LocalObjectStore` (filesystem + HMAC-signed internal URLs) and
`S3ObjectStore` (presigned URLs, `boto3` imported lazily so the local backend
needs no extra dependency). `GET /api/v1/media/{id}/url` returns the short-lived
URL; `GET /api/v1/media/blob` verifies the signature and expiry before serving a
local object. Media bytes never pass through the API otherwise.

## 14. Result APIs project models into dedicated schemas

`services/results.py` reconstructs runs, attempts, conversation materialization,
metric results with evidence, aggregates, the composite and forensic bundles as
plain dictionaries; the route layer validates them against `schemas/results.py`.
No SQLAlchemy model crosses the API boundary. Event collections are paginated.
Following the existing route convention (Prompts 1-6), result routes are not yet
behind the user-scope dependency; wiring global auth is a Prompt 8 concern.
