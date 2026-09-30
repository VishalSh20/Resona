export type EntityId = string;
export type ISODateTime = string;

export type AsyncStatus = "loading" | "success" | "error";

export type MetricStatus =
  | "computed"
  | "not_available"
  | "not_applicable"
  | "invalid"
  | "error";

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id?: string | null;
}

export interface ApiErrorEnvelope {
  error: ApiErrorBody;
}

// --- Auth ---

export interface AuthUserDto {
  id: string;
  email?: string | null;
  username?: string | null;
  roles: string[];
}

export interface TokenResponseDto {
  access_token: string;
  token_type: string;
  user: AuthUserDto;
}

// --- Integrations ---

export interface CredentialFieldDto {
  key: string;
  label: string;
  secret: boolean;
  required: boolean;
}

export interface IntegrationProviderDto {
  id: string;
  slug: string;
  display_name: string;
  credentials: CredentialFieldDto[];
}

export interface IntegrationAccountDto {
  id: string;
  provider_id: string;
  name: string;
  config: Record<string, unknown>;
  status: string;
}

// --- Agents ---

export interface AgentDto {
  id: string;
  provider_id: string;
  integration_account_id: string;
  external_agent_id: string | null;
  name: string;
  agent_url: string | null;
}

export type ProviderRevisionType = "AGENT_CONFIGURATION" | "DEPLOYMENT";

export interface AgentRevisionDto {
  id: string;
  agent_target_id: string;
  revision_no: number;
  provider_revision_id: string | null;
  provider_revision_type: ProviderRevisionType | null;
  revision_label: string | null;
  source_branch_id: string | null;
  description: string | null;
  first_message: string | null;
  llm_config: Record<string, unknown> | null;
  stt_config: Record<string, unknown> | null;
  tts_config: Record<string, unknown> | null;
  turn_config: Record<string, unknown> | null;
  conversation_config: Record<string, unknown> | null;
  tools_config: Record<string, unknown> | null;
  variables_config: Record<string, unknown> | null;
  knowledge_config: Record<string, unknown> | null;
  workflow_config: Record<string, unknown> | null;
  handoffs_config: Record<string, unknown> | null;
  guardrails_config: Record<string, unknown> | null;
  canonical_config: Record<string, unknown>;
  source_config: Record<string, unknown>;
  source_updated_at: string | null;
  config_hash: string;
  source_kind: string;
  created_at: string | null;
}

export interface AgentCreatedDto {
  target: AgentDto;
  revision: AgentRevisionDto;
}

// Client-supplied connection: how to reach the agent under test. For a custom
// WebSocket agent this is kind=websocket, transport=bridge, config.url (+
// optional config.headers/provider) and an optional authorization secret.
export interface TargetConnectionUpsertDto {
  kind: "websocket" | "webrtc" | "sip";
  transport?: string | null;
  revision_id?: string | null;
  config: Record<string, unknown>;
  secrets?: Record<string, string>;
}

export interface RevisionImportRequestDto {
  provider_revision_id: string;
  branch_id: string | null;
}

export interface RevisionDiscoveryCandidateDto {
  provider_revision_id: string | null;
  branch_id: string | null;
  label: string | null;
  description: string | null;
  already_imported: boolean;
}

export interface RevisionDiscoveryResponseDto {
  agent_target_id: string;
  candidates: RevisionDiscoveryCandidateDto[];
}

export interface AgentPreviewRequestDto {
  provider_id: string;
  external_agent_id: string;
  config: Record<string, unknown>;
  secrets: Record<string, string>;
}

export interface PreviewAgentIdentityDto {
  external_agent_id: string;
  name: string;
  agent_url: string | null;
}

export interface PreviewRevisionDto {
  provider_revision_id: string | null;
  provider_revision_type: ProviderRevisionType | null;
  revision_label: string | null;
  description: string | null;
  first_message: string | null;
  canonical_config: Record<string, unknown>;
  source_updated_at: string | null;
}

export interface AgentPreviewResponseDto {
  identity: PreviewAgentIdentityDto;
  revision: PreviewRevisionDto;
}

// --- Simulation / Run / RunEvaluator (v0.4) ---

export interface SimulationDto {
  id: string;
  name: string;
  description?: string | null;
  agent_target_id: string;
  languages: string[];
  call_ambience: string[];
  metric_set: string[];
  personalities: string[];
  knowledge_base: Record<string, unknown>;
  evaluator_count: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SimulationCreatedDto {
  simulation: SimulationDto;
  run: RunDto;
}

export type RunStatus =
  | "draft"
  | "ready"
  | "queued"
  | "running"
  | "partial"
  | "completed"
  | "cancelled";

export interface RunDto {
  id: string;
  simulation_id: string;
  target_revision_id: string;
  evaluator_count: number;
  status: RunStatus;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface RunEvaluatorLanguages {
  major?: string | null;
  minor?: string | null;
}

export interface RunEvaluatorDto {
  id: string;
  run_id: string;
  sequence_no: number;
  scenario: string;
  scenario_config: Record<string, unknown>;
  expected_output_prompt: string;
  metrics: string[];
  languages: RunEvaluatorLanguages;
  personality: string[];
  result?: Record<string, unknown> | null;
}

export type CallRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "infrastructure_failed"
  | "cancelled";

// One logical call = one repetition of one evaluator within a run.
export interface CallRunDto {
  id: string;
  run_id: string;
  run_evaluator_id: string;
  repetition_no: number;
  status: CallRunStatus;
  run_seed?: string | null;
  selected_attempt_id?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface RunProgressDto {
  run_id: string;
  total: number;
  queued: number;
  running: number;
  completed: number;
  infrastructure_failed: number;
  cancelled: number;
}

// --- Generation workflows ---

export interface WorkflowStepDto {
  step: string;
  description?: string;
}

export interface SimulationWorkflowSpecDto {
  objective: string;
  task_flow?: WorkflowStepDto[];
  success_conditions?: string[];
  constraints?: string[];
  failure_modes?: string[];
  knowledge_usage?: string[];
  interaction_requirements?: string[];
}

export interface GenerateEvaluationsRequestDto {
  workflow_spec: SimulationWorkflowSpecDto;
}

export interface GenerateEvaluationsResponseDto {
  run_id: string;
  count: number;
  evaluators: RunEvaluatorDto[];
}

export interface SimulationPreferencesRequestDto {
  description: string;
  available_metrics: string[];
  available_personalities: string[];
}

export interface SimulationPreferencesResponseDto {
  metrics: string[];
  personalities: string[];
}

// --- Benchmarks ---

export interface BenchmarkDto {
  id: string;
  benchmark_key: string;
  name: string;
}

export interface BenchmarkVersionDto {
  id: string;
  benchmark_id: string;
  version: string;
  status: string;
  manifest?: Record<string, unknown> | null;
  manifest_hash?: string | null;
  frozen_at?: string | null;
}

// --- Leaf runtime / forensic transport DTOs (retained for the results pass) ---

export interface CallAttemptDto {
  id: string;
  call_run_id: string;
  attempt_no: number;
  execution_manifest_id?: string | null;
  status: string;
  terminal_status?: string | null;
  failure_class?: string | null;
  termination_reason?: string | null;
  eligible_for_evaluation: boolean;
  runner_version?: string | null;
  adapter_version?: string | null;
  transport_version?: string | null;
  trace_id?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
}

export interface TurnDto {
  id: string;
  call_attempt_id: string;
  sequence_no: number;
  speaker: string;
  start_ms?: number | null;
  end_ms?: number | null;
  reference_text?: string | null;
  observed_text?: string | null;
  reference_language_profile?: Record<string, unknown> | null;
  observed_language_profile?: Record<string, unknown> | null;
  reference_audio_artifact_id?: string | null;
  observed_audio_artifact_id?: string | null;
  transcript_source?: string | null;
  transcript_confidence?: number | null;
}

export interface ToolCallDto {
  id: string;
  call_attempt_id: string;
  turn_id?: string | null;
  ordinal: number;
  tool_name: string;
  arguments?: Record<string, unknown> | null;
  result?: Record<string, unknown> | null;
  status?: string | null;
  start_ms?: number | null;
  end_ms?: number | null;
}

export interface StateTransitionDto {
  id: string;
  call_attempt_id: string;
  sequence_no: number;
  state_path: string;
  previous_value?: unknown;
  new_value?: unknown;
  trigger_type?: string | null;
  trigger_event_id?: string | null;
}

export interface EventDto {
  id: string;
  call_attempt_id: string;
  sequence_no: number;
  type: string;
  source: string;
  monotonic_ms: number;
  wall_clock_at: string;
  media_timestamp?: number | null;
  turn_id?: string | null;
  provider_event_id?: string | null;
  payload: Record<string, unknown>;
}

export interface PaginatedEventsDto {
  items: EventDto[];
  total: number;
  limit: number;
  offset: number;
}

export interface MediaArtifactDto {
  id: string;
  call_attempt_id: string;
  track: string;
  representation: string;
  format?: string | null;
  codec?: string | null;
  sample_rate?: number | null;
  channels?: number | null;
  duration_ms?: number | null;
  clock_domain?: string | null;
  object_uri?: string | null;
  sha256?: string | null;
  size_bytes?: number | null;
}

export interface MediaUrlDto {
  media_artifact_id: string;
  url: string;
  expires_in_seconds: number;
}

export interface MetricResultDto {
  id: string;
  call_run_id: string;
  call_attempt_id: string;
  metric_key: string;
  metric_version: string;
  status: string;
  value_type?: string | null;
  value?: number | boolean | string | null;
  unit?: string | null;
  scale_min?: number | null;
  scale_max?: number | null;
  method?: string | null;
  measurement_basis?: Record<string, unknown> | null;
  confidence?: number | null;
  judge_execution_id?: string | null;
  computed_at?: string | null;
}

export interface EvidenceDto {
  id: string;
  metric_result_id: string;
  source_type: string;
  source_id: string;
  start_ms?: number | null;
  end_ms?: number | null;
  quote?: string | null;
  rationale?: string | null;
}

export interface CompositeDto {
  run_id: string;
  status: string;
  score_0_100?: number | null;
  coverage_ratio?: number | null;
  unavailable_weight?: number | null;
  category_scores?: Record<string, number | null> | null;
  missing_metrics: string[];
}

export interface ConversationDto {
  attempt_id: string;
  turns: TurnDto[];
  tool_calls: ToolCallDto[];
  state_transitions: StateTransitionDto[];
}

// --- Aggregate / run results (read surfaces over evaluation truth) ---

export interface AggregateDto {
  id: string;
  run_id: string;
  scope: string;
  run_evaluator_id?: string | null;
  metric_key: string;
  metric_version: string;
  sample_count: number;
  coverage_count: number;
  availability_ratio?: number | null;
  mean?: number | null;
  median?: number | null;
  min?: number | null;
  max?: number | null;
  stddev?: number | null;
  p95?: number | null;
  percentile_status: string;
  category_counts?: Record<string, unknown> | null;
  aggregation_version?: string | null;
}

export interface EvaluatorRunResultsDto {
  run_evaluator_id: string;
  runs: CallRunDto[];
  metrics: AggregateDto[];
  metric_results: MetricResultDto[];
}

export interface RunResultsReadDto {
  run_id: string;
  status: string;
  evaluators: EvaluatorRunResultsDto[];
  composite?: CompositeDto | null;
}

// --- Judge run result (spec §9 document on judge_execution.parsed_output) ---

export type JudgeRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "invalid"
  | "error";

export type JudgeMetricStatus =
  | "ok"
  | "not_applicable"
  | "not_measurable"
  | "insufficient_evidence"
  | "invalid";

export type JudgeProbeType = "choice" | "noul" | "score";

export type JudgeProbeResolver = "jev" | "llm_adjudicated" | "llm_fallback";

export type JudgeFindingSeverity = "critical" | "major" | "minor";

export type JudgeMetricDirection = "higher_is_better" | "lower_is_better";

export interface JudgeProbeDto {
  probe_id: string;
  type: JudgeProbeType;
  turn_ids?: (number | string)[] | null;
  probabilities?: Record<string, number> | null;
  confidence?: number | null;
  value?: number | null;
  weight?: number | null;
  resolver: JudgeProbeResolver;
  escalated: boolean;
  variants_agree?: boolean | null;
  jev_model?: string | null;
}

export interface JudgeFindingDto {
  severity: JudgeFindingSeverity;
  type: string;
  turn_ids?: (number | string)[] | null;
  t_start_ms?: number | null;
  t_end_ms?: number | null;
  quote?: string | null;
  explanation?: string | null;
  probe_id?: string | null;
}

export interface JudgeSanityDto {
  holistic_llm_score?: number | null;
  gap?: number | null;
}

export interface JudgeMetricProvenanceDto {
  prompt_hashes: string[];
  jev_response_models: string[];
  llm_samples: number;
  media_sources: string[];
}

export interface JudgeMetricDto {
  metric_key: string;
  status: JudgeMetricStatus;
  value?: number | string | boolean | null;
  scale?: number[] | null;
  direction?: JudgeMetricDirection | null;
  normalized?: number | null;
  confidence?: number | null;
  method?: string | null;
  summary?: string | null;
  breakdown: Record<string, unknown>;
  sanity?: JudgeSanityDto | null;
  probes: JudgeProbeDto[];
  findings: JudgeFindingDto[];
  provenance: JudgeMetricProvenanceDto;
  caveats: string[];
}

export interface JudgeMediaArtifactDto {
  media_artifact_id?: string | null;
  object_uri?: string | null;
  sha256?: string | null;
  size_bytes?: number | null;
  sample_rate?: number | null;
  channels?: number | null;
  duration_ms?: number | null;
  format?: string | null;
}

export interface JudgeMediaValidationDto {
  integrity_ok: boolean;
  alignment_ok: boolean;
  caller_offset_ms?: number | null;
  agent_offset_ms?: number | null;
  drift_ms?: number | null;
  bleed_detected: boolean;
  caveats: string[];
}

export interface JudgeMediaBundleDto {
  artifacts: Record<string, JudgeMediaArtifactDto>;
  validation: JudgeMediaValidationDto;
}

export interface JudgeDecisionModelsDto {
  jev: string[];
  adjudicator?: string | null;
  verifier?: string | null;
  audio?: string | null;
}

export interface JudgeTimelineFlagDto {
  turn_id: number | string;
  flags: string[];
}

export interface JudgeRunResultDto {
  run_id: string;
  rubric_version: string;
  judge_version: string;
  status: JudgeRunStatus;
  decision_models: JudgeDecisionModelsDto;
  media: JudgeMediaBundleDto;
  evidence_coverage?: number | null;
  needs_human_review: boolean;
  alignment_conflict: boolean;
  flags: string[];
  latency_ms?: number | null;
  input_hash?: string | null;
  metrics: JudgeMetricDto[];
  timeline: JudgeTimelineFlagDto[];
}

export interface JudgeExecutionDto {
  id: string;
  call_run_id: string;
  call_attempt_id?: string | null;
  status: string;
  rubric_version?: string | null;
  evidence_coverage?: number | null;
  needs_human_review: boolean;
  alignment_conflict: boolean;
  latency_ms?: number | null;
  parsed_output?: JudgeRunResultDto | null;
}
