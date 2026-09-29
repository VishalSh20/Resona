"""Domain enum values.

Every enum-like relational column uses one of these StrEnum values, encoded in
the database as a string with a CHECK constraint. Values are lowercase for
postgres and camel-free for simplicity; the API layer may map them to a more
human-friendly casing when needed.
"""

from __future__ import annotations

from enum import StrEnum


class Transport(StrEnum):
    WEBSOCKET = "websocket"
    WEBRTC = "webrtc"


# Personality and CallAmbience are stored inside JSONB (``simulation.personalities``,
# ``simulation.call_ambience``, ``run_evaluator.personality``) rather than a
# CHECK-constrained relational column, so they keep the canonical UPPERCASE
# spelling from the v0.4 domain schema instead of the lowercase DB convention above.
class Personality(StrEnum):
    SUPPORTIVE = "SUPPORTIVE"
    CONCISE = "CONCISE"
    VERBOSE = "VERBOSE"
    ABUSIVE = "ABUSIVE"
    INTERRUPTOR = "INTERRUPTOR"
    IMPATIENT = "IMPATIENT"
    CONFUSED = "CONFUSED"
    SKEPTICAL = "SKEPTICAL"
    COOPERATIVE = "COOPERATIVE"
    UNCOOPERATIVE = "UNCOOPERATIVE"
    HESITANT = "HESITANT"
    REPETITIVE = "REPETITIVE"
    EMOTIONAL = "EMOTIONAL"
    DEMANDING = "DEMANDING"


class CallAmbience(StrEnum):
    """Environmental conditions mixed into the caller's line during a call."""

    QUIET = "QUIET"
    NOISY = "NOISY"
    PEOPLE_TALKING = "PEOPLE_TALKING"
    MUSIC = "MUSIC"
    TRAFFIC = "TRAFFIC"
    OFFICE = "OFFICE"
    CALL_CENTRE = "CALL_CENTRE"
    CAR = "CAR"


class MetricKey(StrEnum):
    """Canonical metric identity keys (lowercase, matching the metric registry).

    Metrics are a versioned registry rather than a fixed enum of values, but the
    set of *keys* the system understands is stable and belongs here as the single
    source of truth (mirrored by ``metrics/catalog.py`` and the generation
    reasoning registry).
    """

    TTFA = "ttfa"
    TTFT = "ttft"
    BARGE_IN_LATENCY = "barge_in_latency"
    BARGE_IN_SUCCESS_RATE = "barge_in_success_rate"
    LANGUAGE_DETECTION_ACCURACY = "language_detection_accuracy"
    RELEVANCY = "relevancy"
    CONTEXT_RETENTION = "context_retention"
    INSTRUCTION_FOLLOWING = "instruction_following"
    EMPATHY = "empathy"
    HALLUCINATION = "hallucination"
    SEMANTIC_PRESERVATION = "semantic_preservation"
    LANGUAGE_CONSISTENCY = "language_consistency"
    REPETITION = "repetition"
    TASK_COMPLETION = "task_completion"
    KB_GROUNDEDNESS = "kb_groundedness"
    CODE_SWITCHING_ACCURACY = "code_switching_accuracy"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class BenchmarkStatus(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"
    RETIRED = "retired"


class RunStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CallRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"
    CANCELLED = "cancelled"


class AttemptStatus(StrEnum):
    QUEUED = "queued"
    STARTING = "starting"
    CONNECTING = "connecting"
    RUNNING = "running"
    TERMINATING = "terminating"
    TERMINAL = "terminal"


class AttemptTerminalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class AttemptFailureClass(StrEnum):
    INFRASTRUCTURE = "infrastructure"
    PROVIDER = "provider"
    TRANSPORT = "transport"
    MEDIA = "media"
    TIMEOUT = "timeout"
    MALFORMED_STREAM = "malformed_stream"
    RUNNER_CRASH = "runner_crash"
    CANCELLED = "cancelled"


class Speaker(StrEnum):
    CALLER = "caller"
    AGENT = "agent"


class EventSource(StrEnum):
    PROVIDER_RAW = "provider_raw"
    PROVIDER_NORMALIZED = "provider_normalized"
    RUNTIME = "runtime"
    DERIVED = "derived"
    CALLER = "caller"
    METRIC = "metric"


class TranscriptSource(StrEnum):
    CALLER_REFERENCE = "caller_reference"
    PROVIDER_TARGET_INPUT = "provider_target_input"
    PROVIDER_TARGET_OUTPUT = "provider_target_output"
    INDEPENDENT_ASR = "independent_asr"
    HUMAN = "human"
    UNKNOWN = "unknown"


class MediaTrack(StrEnum):
    CALLER = "caller"
    AGENT = "agent"
    MIXED = "mixed"
    PROVIDER_CAPTURE = "provider_capture"


class MediaRepresentation(StrEnum):
    ORIGINAL = "original"
    ANALYSIS = "analysis"
    CLIP = "clip"
    MIXED = "mixed"


class MetricValueType(StrEnum):
    NUMERIC = "numeric"
    BOOLEAN = "boolean"
    TEXT = "text"
    CATEGORY = "category"


class MetricStatus(StrEnum):
    COMPUTED = "computed"
    NOT_AVAILABLE = "not_available"
    NOT_APPLICABLE = "not_applicable"
    INVALID = "invalid"
    ERROR = "error"


class JudgeKind(StrEnum):
    STRUCTURED_JUDGE = "structured_judge"
    LLM_JUDGE = "llm_judge"
    PROBE_JUDGE = "probe_judge"


class JudgeExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    INVALID = "invalid"
    ERROR = "error"


class EvidenceSourceType(StrEnum):
    TURN = "turn"
    EVENT = "event"
    TOOL_CALL = "tool_call"
    AUDIO = "audio"
    STATE_TRANSITION = "state_transition"


class AggregateScope(StrEnum):
    EVALUATOR = "evaluator"
    RUN = "run"
    BENCHMARK = "benchmark"


class PercentileStatus(StrEnum):
    COMPUTED = "computed"
    INSUFFICIENT_SAMPLE = "insufficient_sample"
    NOT_APPLICABLE = "not_applicable"


class CompositeStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"


class ToolCallStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LedgerType(StrEnum):
    """Stage 1 evidence ledgers (judge spec §3.2)."""

    CLAIM = "claim"
    FACT = "fact"
    INTENT = "intent"
    INSTRUCTION = "instruction"
    GOAL = "goal"
    EMOTION = "emotion"
    PRESERVATION = "preservation"


class LedgerStatus(StrEnum):
    OK = "ok"
    UNSTABLE = "unstable"
    INVALID = "invalid"


class ProbeType(StrEnum):
    """Bounded decision primitives (judge spec §4.1/§4.3)."""

    NOUL = "noul"
    CHOICE = "choice"
    SCORE = "score"
    CODE = "code"


class ProbeResolver(StrEnum):
    """Which layer produced the value used for aggregation (§8 precedence)."""

    CODE = "code"
    JEV = "jev"
    LLM_ADJUDICATED = "llm_adjudicated"
    LLM_FALLBACK = "llm_fallback"


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


class JudgingStatus(StrEnum):
    """Outcome of one metric evaluation within a judge run."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    NOT_MEASURABLE = "not_measurable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID = "invalid"
