import type {
  AuthUserDto,
  CallAttemptDto,
  ConversationDto,
  EventDto,
  EvidenceDto,
  MediaArtifactDto,
  MetricResultDto,
  MetricStatus,
  PaginatedEventsDto,
  StateTransitionDto,
  ToolCallDto,
  TurnDto,
} from "@/types/api";
import type {
  AttemptTerminalStatus,
  CallAttemptStatus,
  CallAttemptVM,
  CallTurnVM,
  ConversationVM,
  EvidenceSourceType,
  EvidenceVM,
  FailureClass,
  MediaArtifactVM,
  MediaRepresentation,
  MediaTrack,
  MetricResultVM,
  PaginatedEventsVM,
  RuntimeEventSource,
  RuntimeEventVM,
  Speaker,
  StateTransitionVM,
  ToolCallVM,
  TranscriptSource,
} from "@/types/domain";

export interface AuthUserVM {
  id: string;
  email?: string | null;
  username?: string | null;
  roles: string[];
  displayName: string;
}

const SPEAKERS: Speaker[] = ["caller", "agent"];

const TRANSCRIPT_SOURCES: TranscriptSource[] = [
  "caller_reference",
  "provider_target_input",
  "provider_target_output",
  "independent_asr",
  "human",
  "unknown",
];

const EVENT_SOURCES: RuntimeEventSource[] = [
  "provider_raw",
  "provider_normalized",
  "runtime",
  "derived",
  "caller",
  "metric",
];

const EVIDENCE_SOURCES: EvidenceSourceType[] = [
  "turn",
  "event",
  "tool_call",
  "audio",
  "state_transition",
];

function asMember<T extends string>(allowed: readonly T[], value: string, fallback: T): T {
  return (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export function toAuthUserVM(dto: AuthUserDto): AuthUserVM {
  return {
    id: dto.id,
    email: dto.email ?? null,
    username: dto.username ?? null,
    roles: dto.roles ?? [],
    displayName: dto.username || dto.email || dto.id,
  };
}

export function toCallAttemptVM(dto: CallAttemptDto): CallAttemptVM {
  return {
    id: dto.id,
    callRunId: dto.call_run_id,
    attemptNo: dto.attempt_no,
    executionManifestId: dto.execution_manifest_id ?? null,
    status: dto.status as CallAttemptStatus,
    terminalStatus: (dto.terminal_status ?? null) as AttemptTerminalStatus | null,
    terminationReason: dto.termination_reason ?? null,
    runnerVersion: dto.runner_version ?? null,
    adapterVersion: dto.adapter_version ?? null,
    transportVersion: dto.transport_version ?? null,
    traceId: dto.trace_id ?? null,
    createdAt: dto.created_at ?? undefined,
    startedAt: dto.started_at ?? null,
    finishedAt: dto.finished_at ?? null,
    durationMs: dto.duration_ms ?? null,
    eligibleForEvaluation: dto.eligible_for_evaluation,
    failureClass: (dto.failure_class ?? null) as FailureClass | null,
  };
}

export function toCallTurnVM(dto: TurnDto): CallTurnVM {
  return {
    id: dto.id,
    callAttemptId: dto.call_attempt_id,
    sequenceNo: dto.sequence_no,
    speaker: asMember(SPEAKERS, dto.speaker, "caller"),
    startMs: dto.start_ms ?? 0,
    endMs: dto.end_ms ?? dto.start_ms ?? 0,
    referenceText: dto.reference_text ?? null,
    observedText: dto.observed_text ?? null,
    referenceLanguageProfile: dto.reference_language_profile ?? null,
    observedLanguageProfile: dto.observed_language_profile ?? null,
    referenceAudioArtifactId: dto.reference_audio_artifact_id ?? null,
    observedAudioArtifactId: dto.observed_audio_artifact_id ?? null,
    transcriptSource: asMember(TRANSCRIPT_SOURCES, dto.transcript_source ?? "", "unknown"),
    transcriptConfidence: dto.transcript_confidence ?? null,
  };
}

export function toToolCallVM(dto: ToolCallDto): ToolCallVM {
  return {
    id: dto.id,
    callAttemptId: dto.call_attempt_id,
    turnId: dto.turn_id ?? null,
    ordinal: dto.ordinal,
    toolName: dto.tool_name,
    arguments: dto.arguments ?? {},
    result: dto.result ?? null,
    status: dto.status ?? "unknown",
    startMs: dto.start_ms ?? 0,
    endMs: dto.end_ms ?? dto.start_ms ?? 0,
    source: undefined,
  };
}

export function toStateTransitionVM(dto: StateTransitionDto): StateTransitionVM {
  return {
    id: dto.id,
    callAttemptId: dto.call_attempt_id,
    sequenceNo: dto.sequence_no,
    statePath: dto.state_path,
    previousValue: dto.previous_value ?? null,
    newValue: dto.new_value ?? null,
    triggerType: dto.trigger_type ?? "",
    triggerEventId: dto.trigger_event_id ?? null,
  };
}

export function toRuntimeEventVM(dto: EventDto): RuntimeEventVM {
  return {
    id: dto.id,
    callAttemptId: dto.call_attempt_id,
    sequenceNo: dto.sequence_no,
    eventType: dto.type,
    source: asMember(EVENT_SOURCES, dto.source, "runtime"),
    monotonicMs: dto.monotonic_ms,
    wallClockAt: dto.wall_clock_at,
    mediaTimestamp: dto.media_timestamp ?? null,
    turnId: dto.turn_id ?? null,
    providerEventId: dto.provider_event_id ?? null,
    payload: dto.payload ?? {},
    createdAt: dto.wall_clock_at,
  };
}

export function toPaginatedEventsVM(dto: PaginatedEventsDto): PaginatedEventsVM {
  return {
    items: (dto.items ?? []).map(toRuntimeEventVM),
    total: dto.total,
    limit: dto.limit,
    offset: dto.offset,
  };
}

export function toMediaArtifactVM(dto: MediaArtifactDto): MediaArtifactVM {
  return {
    id: dto.id,
    callAttemptId: dto.call_attempt_id,
    track: dto.track as MediaTrack,
    representation: dto.representation as MediaRepresentation,
    format: dto.format ?? null,
    codec: dto.codec ?? null,
    sampleRate: dto.sample_rate ?? null,
    channels: dto.channels ?? null,
    durationMs: dto.duration_ms ?? null,
    clockDomain: dto.clock_domain ?? null,
    objectUri: dto.object_uri ?? null,
    sha256: dto.sha256 ?? null,
    sizeBytes: dto.size_bytes ?? null,
  };
}

export function toMetricResultVM(dto: MetricResultDto): MetricResultVM {
  return {
    id: dto.id,
    callRunId: dto.call_run_id,
    callAttemptId: dto.call_attempt_id,
    metricKey: dto.metric_key,
    metricVersion: dto.metric_version,
    status: dto.status as MetricStatus,
    valueType: dto.value_type ?? null,
    value: dto.value ?? null,
    unit: dto.unit ?? null,
    scaleMin: dto.scale_min ?? null,
    scaleMax: dto.scale_max ?? null,
    method: dto.method ?? null,
    measurementBasis: dto.measurement_basis ?? null,
    confidence: dto.confidence ?? null,
    judgeExecutionId: dto.judge_execution_id ?? null,
    computedAt: dto.computed_at ?? null,
  };
}

export function toEvidenceVM(dto: EvidenceDto): EvidenceVM {
  return {
    id: dto.id,
    metricResultId: dto.metric_result_id,
    sourceType: asMember(EVIDENCE_SOURCES, dto.source_type, "event"),
    sourceId: dto.source_id,
    startMs: dto.start_ms ?? null,
    endMs: dto.end_ms ?? null,
    quote: dto.quote ?? null,
    rationale: dto.rationale ?? null,
  };
}

export function toConversationVM(dto: ConversationDto): ConversationVM {
  return {
    attemptId: dto.attempt_id,
    turns: (dto.turns ?? []).map(toCallTurnVM),
    toolCalls: (dto.tool_calls ?? []).map(toToolCallVM),
    stateTransitions: (dto.state_transitions ?? []).map(toStateTransitionVM),
  };
}
