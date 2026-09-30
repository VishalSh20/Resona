# Plan preparation, manifest & orchestration decisions (Prompt 4)

## 1. Custom plans carry `evaluator_revision_ids` on the plan

The design documents define the `custom` plan's "custom source" as its
`test_descriptor_revision_id`, but a test descriptor does not reference evaluator
revisions. The `benchmark` kind resolves evaluator revisions from the frozen
benchmark version's cases; the `custom` kind has no equivalent persisted source.

To preserve the documented two-step flow (create → prepare, where prepare
"expands EvaluationPlanItem"), custom plans store their evaluator revisions in a
new nullable JSONB column `evaluation_plan.evaluator_revision_ids` at creation.
Benchmark plans leave it NULL and resolve evaluator revisions from
`benchmark_case` rows during preparation.

## 2. Plan items are materialized at prepare time

The plan-creation endpoint does not write `evaluation_plan_item` rows; prepare
does, in deterministic `sequence_no` order (custom: the supplied revision order;
benchmark: case `sequence_no` order). This matches the documented prepare step
"expand EvaluationPlanItem".

## 3. Capability negotiation blocks prepare

For each evaluator revision, `negotiate()` runs the documented metric/capability
matrix against the target's capability snapshot. Any blocking error (a required
metric missing a required target capability) fails preparation with
`VALIDATION_ERROR`; optional missing capabilities are recorded as warnings and
`NOT_AVAILABLE` in the manifest, never zero.

## 4. Manifest is content-addressed and built once

`manifest_hash` is a SHA-256 over the canonical JSON of all eight snapshot
sections plus the schema version. v1 snapshots evaluator identity by
`content_hash` (not the full content, which remains addressable by revision id)
and records caller/runtime versions and timeout configuration from settings.
Metric/judge *definition registries* are resolved in Prompt 7; v1 snapshots the
negotiated metric keys plus any judge definitions already present in the
database.

## 5. Retry is driven by failure class, not a generic failure flag

`resolve_attempt_termination` maps a terminal attempt to one of four actions.
`infrastructure`, `provider`, `transport` and `runner_crash` are retryable (a new
attempt on the same `CallRun`); `media`, `timeout`, `malformed_stream` and
`cancelled` are terminal; a semantic failure (no infrastructure failure class)
and `timed_out` are recorded as a valid `COMPLETED` sample. Retry budget comes
from `max_attempts_per_run` (default 3), a configuration value, not a constant.

## 6. Resume retries infrastructure-failed runs but never re-samples

`POST /evaluation-plans/{id}/resume` moves `PARTIAL -> RUNNING`, re-dispatches
queued runs, and — for `infrastructure_failed` runs only — creates a new attempt
on the *existing* run. It never creates a second `CallRun` for an existing
`repetition_no`; the `UNIQUE(evaluation_plan_id, plan_item_id, repetition_no)`
constraint is the final guard.
