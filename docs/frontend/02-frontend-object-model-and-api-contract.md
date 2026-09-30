# VoiceEval — Frontend Object Model & API Contract v0.1

## 1. Purpose

This document defines the TypeScript-facing view models used to represent every backend object that materially contributes to the VoiceEval workflow.

The frontend should use API response DTOs as transport objects and map them into UI view models.

Do not build components directly against raw JSONB blobs everywhere.

---

# 2. Common primitives

```ts
export type EntityId = string;
export type ISODateTime = string;

export type AsyncStatus =
  | 'loading'
  | 'success'
  | 'error';

export type MetricStatus =
  | 'computed'
  | 'not_available'
  | 'not_applicable'
  | 'invalid'
  | 'error';
```

---

# 3. Agent Target

Backend source fields:

```text
id
name
provider
description
created_at
updated_at
```

Frontend view model:

```ts
export interface AgentTargetVM {
  id: string;
  name: string;
  provider?: string | null;
  description?: string | null;
  createdAt: string;
  updatedAt: string;

  revisionCount?: number;
  latestRevision?: AgentTargetRevisionSummaryVM;
}
```

### Target revision

```ts
export type Transport = 'websocket' | 'webrtc';

export interface AgentTargetRevisionVM {
  id: string;
  agentTargetId: string;
  revisionNo: number;

  transport: Transport;
  adapterName: string;
  adapterVersion: string;

  endpointConfig: Record<string, unknown>;
  capabilitySnapshot: CapabilitySnapshotVM;

  configHash: string;
  createdBy?: string | null;
  createdAt: string;
}
```

Never include secrets in the regular view model.

---

# 4. Capability snapshot

Canonical shape:

```ts
export interface CapabilitySnapshotVM {
  audio?: {
    callerIngress?: boolean;
    agentEgress?: boolean;
  };

  transcript?: {
    targetInput?: boolean;
    targetOutput?: boolean;
    independentAsrPossible?: boolean;
  };

  events?: {
    turnBoundaries?: boolean;
    textStream?: boolean;
    interruptions?: boolean;
    connectionEvents?: boolean;
  };

  tools?: {
    calls?: boolean;
    results?: boolean;
  };

  timing?: {
    mediaTimestamps?: boolean;
    textTimestamps?: boolean;
  };
}
```

Use a reusable capability cell:

```text
AVAILABLE
UNAVAILABLE
UNKNOWN
```

Do not infer capability from metric success.

---

# 5. Test Descriptor

```ts
export interface TestDescriptorVM {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
}

export interface TestDescriptorRevisionVM {
  id: string;
  testDescriptorId: string;
  revisionNo: number;
  sourceText: string;
  normalizedConstraints: Record<string, unknown>;
  generatorModel?: string | null;
  generatorPromptHash?: string | null;
  createdAt: string;
  createdBy?: string | null;
}
```

The source text should be available in an inspector, with normalized constraints presented separately.

---

# 6. Evaluator

```ts
export type EvaluatorSuiteKind = 'custom' | 'benchmark';

export interface EvaluatorVM {
  id: string;
  evaluatorKey: string;
  name: string;
  suiteKind: EvaluatorSuiteKind;
  createdAt: string;
}
```

Revision:

```ts
export type EvaluatorRevisionStatus =
  | 'generated'
  | 'draft'
  | 'validating'
  | 'validated'
  | 'approved'
  | 'rejected'
  | 'executed';

export interface EvaluatorRevisionVM {
  id: string;
  evaluatorId: string;
  revisionNo: number;
  status: EvaluatorRevisionStatus;
  parentRevisionId?: string | null;

  schemaVersion: string;
  content: EvaluatorContentVM;
  contentHash: string;

  validatorVersion?: string | null;
  createdAt: string;
  createdBy?: string | null;
}
```

---

# 7. Evaluator content

```ts
export interface EvaluatorContentVM {
  schemaVersion: string;

  persona: {
    age?: number;
    personality?: string;
    traits?: string[];
  };

  language: {
    primary?: string;
    allowed?: string[];
    adaptationRule?: string;
  };

  environment?: {
    noiseProfile?: string;
  };

  facts: EvaluatorFactVM[];

  initialState: Record<string, unknown>;

  motive: {
    objective?: string;
    assertions: MotiveAssertionVM[];
  };

  behaviour: {
    allowedActions: string[];
    recovery?: {
      maxAttempts: number;
    };
  };

  stopConditions: {
    naturalSuccess?: boolean;
    recoveryExhausted?: boolean;
    irrecoverableObjectiveFailure?: boolean;
    conversationStallMs?: number;
    wallClockTimeoutMs?: number;
  };

  evaluationCriteria: EvaluationCriterionVM[];

  randomization?: {
    policyVersion?: string;
  };
}
```

Fact:

```ts
export interface EvaluatorFactVM {
  id: string;
  type: string;
  value: unknown;
}
```

Assertion:

```ts
export interface MotiveAssertionVM {
  id: string;
  type: string;
  required: boolean;
  weight?: number;
  expectation?: Record<string, unknown>;
}
```

Criterion:

```ts
export interface EvaluationCriterionVM {
  metric: string;
  required: boolean;
}
```

---

# 8. Validation Report

```ts
export type ValidationStatus =
  | 'pass'
  | 'warning'
  | 'error';

export interface ValidationCheckVM {
  key: string;
  status: ValidationStatus;
  severity?: string;
  details?: string;
}

export interface ValidationReportVM {
  id: string;
  evaluatorRevisionId: string;
  validatorVersion: string;
  status: string;
  blockingErrorCount: number;
  warningCount: number;
  checks: ValidationCheckVM[];
  createdAt: string;
}
```

UI summary:

```text
0 blocking errors
2 warnings
```

The report is a decision gate, not just a log.

---

# 9. Benchmark

```ts
export type BenchmarkVersionStatus =
  | 'draft'
  | 'frozen'
  | 'retired';

export interface BenchmarkVM {
  id: string;
  benchmarkKey: string;
  name: string;
  createdAt: string;
}

export interface BenchmarkVersionVM {
  id: string;
  benchmarkId: string;
  version: number;
  status: BenchmarkVersionStatus;
  manifest: Record<string, unknown>;
  manifestHash: string;
  createdAt: string;
  frozenAt?: string | null;
}

export interface BenchmarkCaseVM {
  id: string;
  benchmarkVersionId: string;
  caseKey: string;
  evaluatorRevisionId: string;
  sequenceNo: number;
}
```

Frozen badge:

```text
FROZEN
```

must be visually obvious.

---

# 10. Evaluation Plan

```ts
export type EvaluationPlanKind =
  | 'custom'
  | 'benchmark';

export type EvaluationPlanStatus =
  | 'draft'
  | 'ready'
  | 'queued'
  | 'running'
  | 'partial'
  | 'completed'
  | 'cancelled';

export interface EvaluationPlanVM {
  id: string;
  kind: EvaluationPlanKind;

  testDescriptorRevisionId?: string | null;
  benchmarkVersionId?: string | null;

  agentTargetRevisionId: string;

  repeatCount: number;
  planStatus: EvaluationPlanStatus;

  executionManifestId?: string | null;

  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;

  progress?: PlanProgressVM;
}
```

Plan progress:

```ts
export interface PlanProgressVM {
  logicalRunsTotal: number;
  logicalRunsCompleted: number;
  queued: number;
  running: number;
  failed: number;
  cancelled: number;
}
```

---

# 11. Evaluation Plan Item

```ts
export interface EvaluationPlanItemVM {
  id: string;
  evaluationPlanId: string;
  evaluatorRevisionId: string;
  sequenceNo: number;
  enabled: boolean;
}
```

The evaluation live matrix should derive its rows from plan items.

---

# 12. Execution Manifest

```ts
export interface ExecutionManifestVM {
  id: string;
  schemaVersion: string;

  targetSnapshot: Record<string, unknown>;
  evaluatorSnapshot: Record<string, unknown>;
  benchmarkSnapshot?: Record<string, unknown> | null;
  callerSnapshot: Record<string, unknown>;

  metricSnapshot: unknown;
  judgeSnapshot: unknown;
  aggregationSnapshot: unknown;
  compositeSnapshot: unknown;

  manifestHash: string;
  createdAt: string;
}
```

The UI must treat this as sealed.

Useful object presentation:

```text
Target snapshot
Evaluator snapshot
Benchmark snapshot
Caller snapshot
Metrics
Judges
Aggregation
Composite
Runtime
```

---

# 13. CallRun

```ts
export type CallRunStatus =
  | 'queued'
  | 'running'
  | 'completed'
  | 'infrastructure_failed'
  | 'cancelled';

export interface CallRunVM {
  id: string;
  evaluationPlanId: string;
  planItemId: string;
  evaluatorRevisionId: string;

  repetitionNo: number;
  runSeed: number;

  status: CallRunStatus;

  selectedAttemptId?: string | null;

  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;

  attempts?: CallAttemptSummaryVM[];
}
```

UI invariant:

```text
repetitionNo identifies the statistical sample.
attempt_no identifies infrastructure history.
```

---

# 14. CallAttempt

```ts
export type CallAttemptStatus =
  | 'queued'
  | 'starting'
  | 'connecting'
  | 'running'
  | 'terminating'
  | 'terminal';

export type AttemptTerminalStatus =
  | 'completed'
  | 'failed'
  | 'timed_out'
  | 'cancelled';

export type FailureClass =
  | 'infrastructure'
  | 'provider'
  | 'transport'
  | 'media'
  | 'timeout'
  | 'malformed_stream'
  | 'runner_crash'
  | 'cancelled';

export interface CallAttemptVM {
  id: string;
  callRunId: string;
  attemptNo: number;

  executionManifestId: string;

  status: CallAttemptStatus;
  terminationReason?: string | null;

  runnerVersion: string;
  adapterVersion: string;
  transportVersion: string;

  traceId: string;

  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;

  eligibleForEvaluation: boolean;
  failureClass?: FailureClass | null;

  createdAt: string;
}
```

---

# 15. CallTurn

```ts
export type Speaker = 'caller' | 'agent';

export type TranscriptSource =
  | 'caller_reference'
  | 'provider_target_input'
  | 'provider_target_output'
  | 'independent_asr'
  | 'human'
  | 'unknown';

export interface CallTurnVM {
  id: string;
  callAttemptId: string;
  sequenceNo: number;

  speaker: Speaker;

  startMs: number;
  endMs: number;

  referenceText?: string | null;
  observedText?: string | null;

  referenceLanguageProfile?: LanguageProfileVM | null;
  observedLanguageProfile?: LanguageProfileVM | null;

  referenceAudioArtifactId?: string | null;
  observedAudioArtifactId?: string | null;

  transcriptSource: TranscriptSource;
  transcriptConfidence?: number | null;

  createdAt?: string;
}

export interface LanguageProfileVM {
  dominant?: string;
  languages?: string[];
}
```

UI rule:

```text
caller reference ≠ target observation
```

---

# 16. RuntimeEvent

```ts
export type RuntimeEventSource =
  | 'provider_raw'
  | 'provider_normalized'
  | 'runtime'
  | 'derived'
  | 'caller'
  | 'metric';

export interface RuntimeEventVM {
  id: string;
  callAttemptId: string;

  sequenceNo: number;
  eventType: string;
  source: RuntimeEventSource;

  monotonicMs: number;
  wallClockAt: string;

  mediaTimestamp?: number | null;
  turnId?: string | null;
  providerEventId?: string | null;

  payload: Record<string, unknown>;

  createdAt: string;
}
```

---

# 17. ToolCall

```ts
export interface ToolCallVM {
  id: string;
  callAttemptId: string;
  turnId?: string | null;

  ordinal: number;
  toolName: string;

  arguments: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  status: string;

  startMs: number;
  endMs: number;

  source: string;
  createdAt: string;
}
```

---

# 18. StateTransition

```ts
export interface StateTransitionVM {
  id: string;
  callAttemptId: string;
  sequenceNo: number;

  statePath: string;
  previousValue: unknown;
  newValue: unknown;

  triggerType: string;
  triggerEventId?: string | null;

  createdAt: string;
}
```

---

# 19. MediaArtifact

```ts
export type MediaTrack =
  | 'caller'
  | 'agent'
  | 'mixed'
  | 'provider_capture';

export type MediaRepresentation =
  | 'original'
  | 'analysis'
  | 'clip';

export interface MediaArtifactVM {
  id: string;
  callAttemptId: string;

  track: MediaTrack;
  representation: MediaRepresentation;

  format: string;
  codec: string;

  sampleRate: number;
  channels: number;
  durationMs: number;

  clockDomain: string;
  objectUri: string;
  sha256: string;
  sizeBytes: number;

  createdAt: string;
}
```

The UI should fetch a signed URL only when playback is requested.

---

# 20. Metric Definition

```ts
export interface MetricDefinitionVM {
  id: string;
  metricKey: string;
  version: string;

  family: string;
  valueType: string;
  unit?: string | null;

  scaleMin?: number | null;
  scaleMax?: number | null;

  requiredCapabilities: unknown;
  requiredEvidence: unknown;

  implementationVersion: string;
  aggregationConfig: unknown;
  normalizationConfig: unknown;

  createdAt: string;
}
```

---

# 21. Metric Result

```ts
export interface MetricResultVM {
  id: string;
  callRunId: string;
  callAttemptId: string;

  metricDefinitionId: string;

  status: MetricStatus;

  valueNumeric?: number | null;
  valueBoolean?: boolean | null;
  valueText?: string | null;
  valueCategory?: string | null;

  unit?: string | null;

  scaleMin?: number | null;
  scaleMax?: number | null;

  method: string;
  measurementBasis: Record<string, unknown>;

  confidence?: number | null;

  judgeExecutionId?: string | null;

  computedAt: string;
}
```

Rendering helper:

```ts
function metricDisplayValue(result: MetricResultVM): string {
  switch (result.status) {
    case 'not_available':
      return 'Not available';
    case 'not_applicable':
      return 'Not applicable';
    case 'invalid':
      return 'Invalid';
    case 'error':
      return 'Error';
    case 'computed':
      return formatMetricValue(result);
  }
}
```

Never coerce unavailable to zero.

---

# 22. Judge Definition

```ts
export type JudgeKind =
  | 'structured_judge'
  | 'llm_judge';

export interface JudgeDefinitionVM {
  id: string;
  judgeKey: string;
  version: string;

  kind: JudgeKind;
  provider?: string | null;
  model?: string | null;

  promptHash?: string | null;
  rubricVersion?: string | null;
  outputSchemaVersion?: string | null;

  config: Record<string, unknown>;
  createdAt: string;
}
```

---

# 23. Judge Execution

```ts
export interface JudgeExecutionVM {
  id: string;
  callRunId: string;
  judgeDefinitionId: string;

  inputHash: string;
  status: string;

  rawOutput?: string | null;
  parsedOutput?: Record<string, unknown> | null;

  latencyMs?: number | null;
  createdAt: string;
}
```

Raw output should be collapsible and visually marked as model output.

---

# 24. Evidence

```ts
export type EvidenceSourceType =
  | 'turn'
  | 'event'
  | 'tool_call'
  | 'audio'
  | 'state_transition';

export interface EvidenceVM {
  id: string;
  metricResultId: string;

  sourceType: EvidenceSourceType;
  sourceId: string;

  startMs?: number | null;
  endMs?: number | null;

  quote?: string | null;
  rationale: string;

  createdAt: string;
}
```

If an audio evidence item has offsets, the UI must render:

```text
[Seek to 11.720s]
```

---

# 25. Aggregate Result

```ts
export interface AggregateResultVM {
  id: string;

  evaluationPlanId: string;

  scope: 'evaluator' | 'suite' | 'benchmark';

  evaluatorRevisionId?: string | null;

  metricDefinitionId: string;

  sampleCount: number;
  coverageCount: number;
  availabilityRatio: number;

  mean?: number | null;
  median?: number | null;
  minValue?: number | null;
  maxValue?: number | null;
  stddev?: number | null;

  p95?: number | null;
  percentileStatus:
    | 'computed'
    | 'insufficient_sample'
    | 'not_applicable';

  categoryCounts?: Record<string, number>;
  aggregationVersion: string;

  createdAt: string;
}
```

For three repetitions, the primary visual should be:

```text
values
mean
median
range
stddev
```

not P95.

---

# 26. Composite Score

```ts
export interface CompositeScoreDefinitionVM {
  id: string;
  version: string;

  weights: Record<string, number>;
  normalization: Record<string, unknown>;
  coveragePolicy: Record<string, unknown>;
  criticalMetrics: unknown;

  createdAt: string;
}

export type CompositeStatus =
  | 'complete'
  | 'incomplete'
  | 'unavailable';

export interface CompositeScoreResultVM {
  id: string;
  evaluationPlanId: string;
  definitionId: string;

  score0100?: number | null;
  status: CompositeStatus;

  coverageRatio: number;
  unavailableWeight: number;

  categoryScores: Record<string, number>;

  createdAt: string;
}
```

---

# 27. Failure object

The frontend should normalize backend failure metadata into:

```ts
export interface FailureSummaryVM {
  failureClass:
    | 'infrastructure'
    | 'provider'
    | 'transport'
    | 'media'
    | 'timeout'
    | 'malformed_stream'
    | 'runner_crash'
    | 'cancelled';

  terminationReason?: string | null;

  count: number;

  affectedRuns: string[];
}
```

Never reduce all failures to one generic "failed" label.

---

# 28. Live UI events

```ts
export type PlanLiveEventType =
  | 'plan.status.changed'
  | 'run.status.changed'
  | 'attempt.status.changed'
  | 'metric.computed'
  | 'judge.completed'
  | 'aggregate.updated'
  | 'composite.updated';

export interface PlanLiveEvent<TPayload = unknown> {
  type: PlanLiveEventType;
  data: TPayload;
}
```

Payload adapters should exist per event type.

---

# 29. API service map

```ts
targetsApi
  list()
  get(targetId)
  listRevisions(targetId)
  getRevision(targetId, revisionId)
  createTarget(input)
  createRevision(targetId, input)

evaluatorsApi
  list()
  get(evaluatorId)
  create(input)
  createRevision(evaluatorId, input)
  getRevision(revisionId)
  validate(revisionId)
  approve(revisionId)

benchmarksApi
  list()
  get(benchmarkId)
  create(input)
  createVersion(benchmarkId, input)
  freeze(versionId)
  getVersion(versionId)

plansApi
  list()
  get(planId)
  create(input)
  prepare(planId)
  execute(planId, idempotencyKey)
  cancel(planId)
  resume(planId)
  getResults(planId)
  getAggregates(planId)
  getComposite(planId)

runsApi
  get(runId)
  retry(runId)
  getForensics(runId)

attemptsApi
  get(attemptId)
  getEvents(attemptId, filters)
  getConversation(attemptId)
  getMedia(attemptId)

resultsApi
  getMetric(metricResultId)
  getEvidence(metricResultId)

mediaApi
  getSignedUrl(mediaId)
```

---

# 30. API to view mapping

| Endpoint | Main consuming view |
|---|---|
| GET targets | Target library |
| GET target | Target overview |
| GET revision | Target revision |
| POST evaluator revision | Evaluator editor |
| validate revision | Validation view |
| approve revision | Revision header actions |
| GET benchmark version | Benchmark version |
| prepare plan | Plan preparation step |
| execute plan | Live console |
| plan results | Results dashboard |
| run | Run detail |
| attempt | Forensic header |
| conversation | Conversation inspector |
| events | Event stream / timeline |
| evidence | Evidence drawer |
| media URL | Audio inspector |
| forensics | Full forensic page |

---

# 31. Client-side selectors

Useful derived selectors:

```ts
selectPlanProgress(plan)
selectPlanCompletionState(plan)
selectRunSelectedAttempt(run)
selectAttemptTerminalState(attempt)
selectAttemptFailure(attempt)
selectMetricDisplay(result)
selectMetricCoverage(aggregate)
selectCompositeHealth(composite)
selectEvaluatorValidationSummary(report)
selectCapabilityMismatches(target, metrics)
selectEvidenceSource(evidence)
```

These selectors keep domain logic out of presentational components.
