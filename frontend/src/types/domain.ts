import type { EntityId, ISODateTime } from "./api";

// --- CallAttempt ---

export type CallAttemptStatus =
  | "queued"
  | "starting"
  | "connecting"
  | "running"
  | "terminating"
  | "terminal";

export type AttemptTerminalStatus =
  | "completed"
  | "failed"
  | "timed_out"
  | "cancelled";

export type FailureClass =
  | "infrastructure"
  | "provider"
  | "transport"
  | "media"
  | "timeout"
  | "malformed_stream"
  | "runner_crash"
  | "cancelled";

export interface CallAttemptVM {
  id: EntityId;
  callRunId: EntityId;
  attemptNo: number;

  executionManifestId?: EntityId | null;

  status: CallAttemptStatus;
  terminalStatus?: AttemptTerminalStatus | null;
  terminationReason?: string | null;

  runnerVersion?: string | null;
  adapterVersion?: string | null;
  transportVersion?: string | null;

  traceId?: string | null;

  createdAt?: ISODateTime;
  startedAt?: string | null;
  finishedAt?: string | null;
  durationMs?: number | null;

  eligibleForEvaluation: boolean;
  failureClass?: FailureClass | null;
}

// --- CallTurn ---

export type Speaker = "caller" | "agent";

export type TranscriptSource =
  | "caller_reference"
  | "provider_target_input"
  | "provider_target_output"
  | "independent_asr"
  | "human"
  | "unknown";

export interface LanguageProfileVM {
  dominant?: string;
  languages?: string[];
}

export interface CallTurnVM {
  id: EntityId;
  callAttemptId: EntityId;
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

// --- Runtime event ---

export type RuntimeEventSource =
  | "provider_raw"
  | "provider_normalized"
  | "runtime"
  | "derived"
  | "caller"
  | "metric";

export interface RuntimeEventVM {
  id: EntityId;
  callAttemptId: EntityId;

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

// --- ToolCall ---

export interface ToolCallVM {
  id: EntityId;
  callAttemptId: EntityId;
  turnId?: string | null;

  ordinal: number;
  toolName: string;

  arguments: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  status: string;

  startMs: number;
  endMs: number;

  source?: string | null;
  createdAt?: string;
}

// --- StateTransition ---

export interface StateTransitionVM {
  id: EntityId;
  callAttemptId: EntityId;
  sequenceNo: number;

  statePath: string;
  previousValue: unknown;
  newValue: unknown;

  triggerType: string;
  triggerEventId?: string | null;

  createdAt?: string;
}

// --- MediaArtifact ---

export type MediaTrack = "caller" | "agent" | "mixed" | "provider_capture";

export type MediaRepresentation = "original" | "analysis" | "clip" | "mixed";

export interface MediaArtifactVM {
  id: EntityId;
  callAttemptId: EntityId;

  track: MediaTrack;
  representation: MediaRepresentation;

  format?: string | null;
  codec?: string | null;

  sampleRate?: number | null;
  channels?: number | null;
  durationMs?: number | null;

  clockDomain?: string | null;
  objectUri?: string | null;
  sha256?: string | null;
  sizeBytes?: number | null;

  createdAt?: string;
}

// --- Metric / evidence (leaf results objects) ---

export interface MetricResultVM {
  id: EntityId;
  callRunId: EntityId;
  callAttemptId: EntityId;

  metricKey: string;
  metricVersion: string;

  status: string;

  valueType?: string | null;
  value?: number | boolean | string | null;

  unit?: string | null;

  scaleMin?: number | null;
  scaleMax?: number | null;

  method?: string | null;
  measurementBasis?: Record<string, unknown> | null;

  confidence?: number | null;

  judgeExecutionId?: string | null;

  computedAt?: string | null;
}

export type EvidenceSourceType =
  | "turn"
  | "event"
  | "tool_call"
  | "audio"
  | "state_transition";

export interface EvidenceVM {
  id: EntityId;
  metricResultId: EntityId;

  sourceType: EvidenceSourceType;
  sourceId: EntityId;

  startMs?: number | null;
  endMs?: number | null;

  quote?: string | null;
  rationale?: string | null;

  createdAt?: string;
}

// --- Conversation / pagination ---

export interface ConversationVM {
  attemptId: EntityId;
  turns: CallTurnVM[];
  toolCalls: ToolCallVM[];
  stateTransitions: StateTransitionVM[];
}

export interface PaginatedEventsVM {
  items: RuntimeEventVM[];
  total: number;
  limit: number;
  offset: number;
}
