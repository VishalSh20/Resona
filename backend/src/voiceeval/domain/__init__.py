"""Domain vocabulary: statuses, kinds and state-machine transitions.

These enums are the single source of truth for the values stored in the
enum-like relational columns, and for the explicit transition functions that
prevent arbitrary status mutation.
"""

from voiceeval.domain.enums import (  # noqa: F401
    AggregateScope,
    AttemptFailureClass,
    AttemptStatus,
    AttemptTerminalStatus,
    BenchmarkStatus,
    CallAmbience,
    CallRunStatus,
    CompositeStatus,
    EventSource,
    EvidenceSourceType,
    JudgeExecutionStatus,
    JudgeKind,
    MediaRepresentation,
    MediaTrack,
    MetricKey,
    MetricStatus,
    MetricValueType,
    PercentileStatus,
    Personality,
    RunStatus,
    Speaker,
    ToolCallStatus,
    TranscriptSource,
    Transport,
    ValidationStatus,
)
