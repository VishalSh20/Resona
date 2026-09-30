"""Result and forensics services (v0.4).

Reconstructs evaluation truth for the API from persisted rows, projecting
SQLAlchemy models into plain dictionaries so the route layer can validate them
against response schemas. Media bytes are never streamed through here: only
short-lived object-store URLs are returned.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.aggregation.composite import (
    DEFAULT_COMPOSITE_VERSION,
    DEFAULT_COVERAGE_POLICY,
)
from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.db.models import domain, results, runtime
from voiceeval.db.repositories import (
    CallAttemptRepository,
    CallRunRepository,
    JudgeRepository,
    ManifestRepository,
    MaterializationRepository,
    MediaArtifactRepository,
    MetricRepository,
    ResultRepository,
    RunEvaluatorRepository,
    RuntimeEventRepository,
)
from voiceeval.domain.enums import AttemptStatus, MetricStatus
from voiceeval.storage import get_object_store
from voiceeval.storage.local import LOCAL_URI_SCHEME

DEFAULT_MEDIA_URL_EXPIRES = 300


# -- serializers --------------------------------------------------------------


def _metric_value(result: results.MetricResult) -> Any:
    if result.status != MetricStatus.COMPUTED.value:
        return None
    value_type = result.value_type
    if value_type == "numeric":
        return float(result.value_numeric) if result.value_numeric is not None else None
    if value_type == "boolean":
        return result.value_boolean
    if value_type == "text":
        return result.value_text
    if value_type == "category":
        return result.value_category
    return None


def metric_result_to_dict(
    result: results.MetricResult, definition: results.MetricDefinition | None
) -> dict[str, Any]:
    return {
        "id": result.id,
        "call_run_id": result.call_run_id,
        "call_attempt_id": result.call_attempt_id,
        "metric_key": definition.metric_key if definition else result.metric_definition_id,
        "metric_version": definition.version if definition else "",
        "status": result.status,
        "value_type": result.value_type,
        "value": _metric_value(result),
        "unit": result.unit,
        "scale_min": float(result.scale_min) if result.scale_min is not None else None,
        "scale_max": float(result.scale_max) if result.scale_max is not None else None,
        "method": result.method,
        "measurement_basis": result.measurement_basis,
        "confidence": float(result.confidence) if result.confidence is not None else None,
        "judge_execution_id": result.judge_execution_id,
        "computed_at": result.computed_at,
    }


def evidence_to_dict(evidence: results.Evidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "metric_result_id": evidence.metric_result_id,
        "source_type": evidence.source_type,
        "source_id": evidence.source_id,
        "start_ms": evidence.start_ms,
        "end_ms": evidence.end_ms,
        "quote": evidence.quote,
        "rationale": evidence.rationale,
    }


def aggregate_to_dict(
    aggregate: results.AggregateResult, definition: results.MetricDefinition | None
) -> dict[str, Any]:
    return {
        "id": aggregate.id,
        "run_id": aggregate.run_id,
        "scope": aggregate.scope,
        "run_evaluator_id": aggregate.run_evaluator_id,
        "metric_key": definition.metric_key if definition else aggregate.metric_definition_id,
        "metric_version": definition.version if definition else "",
        "sample_count": aggregate.sample_count,
        "coverage_count": aggregate.coverage_count,
        "availability_ratio": (
            float(aggregate.availability_ratio)
            if aggregate.availability_ratio is not None
            else None
        ),
        "mean": float(aggregate.mean) if aggregate.mean is not None else None,
        "median": float(aggregate.median) if aggregate.median is not None else None,
        "min": float(aggregate.min_value) if aggregate.min_value is not None else None,
        "max": float(aggregate.max_value) if aggregate.max_value is not None else None,
        "stddev": float(aggregate.stddev) if aggregate.stddev is not None else None,
        "p95": float(aggregate.p95) if aggregate.p95 is not None else None,
        "percentile_status": aggregate.percentile_status,
        "category_counts": aggregate.category_counts,
        "aggregation_version": aggregate.aggregation_version,
    }


def _run_dict(run: runtime.CallRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_id": run.run_id,
        "run_evaluator_id": run.run_evaluator_id,
        "repetition_no": run.repetition_no,
        "status": run.status,
        "run_seed": run.run_seed,
        "selected_attempt_id": run.selected_attempt_id,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
    }


def _attempt_dict(attempt: runtime.CallAttempt) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "call_run_id": attempt.call_run_id,
        "attempt_no": attempt.attempt_no,
        "execution_manifest_id": attempt.execution_manifest_id,
        "status": attempt.status,
        "terminal_status": attempt.terminal_status,
        "failure_class": attempt.failure_class,
        "termination_reason": attempt.termination_reason,
        "eligible_for_evaluation": attempt.eligible_for_evaluation,
        "runner_version": attempt.runner_version,
        "adapter_version": attempt.adapter_version,
        "transport_version": attempt.transport_version,
        "trace_id": attempt.trace_id,
        "created_at": attempt.created_at,
        "started_at": attempt.started_at,
        "finished_at": attempt.finished_at,
        "duration_ms": attempt.duration_ms,
    }


def _turn_dict(turn: runtime.CallTurn) -> dict[str, Any]:
    return {
        "id": turn.id,
        "call_attempt_id": turn.call_attempt_id,
        "sequence_no": turn.sequence_no,
        "speaker": turn.speaker,
        "start_ms": turn.start_ms,
        "end_ms": turn.end_ms,
        "reference_text": turn.reference_text,
        "observed_text": turn.observed_text,
        "reference_language_profile": turn.reference_language_profile,
        "observed_language_profile": turn.observed_language_profile,
        "reference_audio_artifact_id": turn.reference_audio_artifact_id,
        "observed_audio_artifact_id": turn.observed_audio_artifact_id,
        "transcript_source": turn.transcript_source,
        "transcript_confidence": (
            float(turn.transcript_confidence)
            if turn.transcript_confidence is not None
            else None
        ),
    }


def _tool_dict(tool: runtime.ToolCall) -> dict[str, Any]:
    return {
        "id": tool.id,
        "call_attempt_id": tool.call_attempt_id,
        "turn_id": tool.turn_id,
        "ordinal": tool.ordinal,
        "tool_name": tool.tool_name,
        "arguments": tool.arguments,
        "result": tool.result,
        "status": tool.status,
        "start_ms": tool.start_ms,
        "end_ms": tool.end_ms,
    }


def _state_dict(state: runtime.StateTransition) -> dict[str, Any]:
    return {
        "id": state.id,
        "call_attempt_id": state.call_attempt_id,
        "sequence_no": state.sequence_no,
        "state_path": state.state_path,
        "previous_value": state.previous_value,
        "new_value": state.new_value,
        "trigger_type": state.trigger_type,
        "trigger_event_id": state.trigger_event_id,
    }


def _event_dict(event: runtime.RuntimeEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "call_attempt_id": event.call_attempt_id,
        "sequence_no": event.sequence_no,
        "type": event.event_type,
        "source": event.source,
        "monotonic_ms": event.monotonic_ms,
        "wall_clock_at": event.wall_clock_at,
        "media_timestamp": event.media_timestamp,
        "turn_id": event.turn_id,
        "provider_event_id": event.provider_event_id,
        "payload": event.payload,
    }


def _media_dict(media: runtime.MediaArtifact) -> dict[str, Any]:
    return {
        "id": media.id,
        "call_attempt_id": media.call_attempt_id,
        "track": media.track,
        "representation": media.representation,
        "format": media.format,
        "codec": media.codec,
        "sample_rate": media.sample_rate,
        "channels": media.channels,
        "duration_ms": media.duration_ms,
        "clock_domain": media.clock_domain,
        "object_uri": media.object_uri,
        "sha256": media.sha256,
        "size_bytes": media.size_bytes,
    }


def _object_key(uri: str) -> str:
    if uri.startswith(LOCAL_URI_SCHEME):
        return uri[len(LOCAL_URI_SCHEME):]
    if uri.startswith("s3://"):
        parts = uri.split("/", 3)
        return parts[3] if len(parts) > 3 else ""
    return uri


# -- services -----------------------------------------------------------------


class ResultService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._runs = CallRunRepository(session)
        self._run_evaluators = RunEvaluatorRepository(session)
        self._attempts = CallAttemptRepository(session)
        self._manifests = ManifestRepository(session)
        self._events = RuntimeEventRepository(session)
        self._materialization = MaterializationRepository(session)
        self._media = MediaArtifactRepository(session)
        self._metrics = MetricRepository(session)
        self._results = ResultRepository(session)
        self._judges = JudgeRepository(session)

    async def _definitions(self) -> dict[str, results.MetricDefinition]:
        return {d.id: d for d in await self._metrics.list_definitions()}

    async def get_metric_result(self, result_id: str) -> dict[str, Any]:
        result = await self._metrics.get_result(result_id)
        definition = await self._session.get(
            results.MetricDefinition, result.metric_definition_id
        )
        return metric_result_to_dict(result, definition)

    async def list_evidence(self, result_id: str) -> list[dict[str, Any]]:
        await self._metrics.get_result(result_id)
        return [
            evidence_to_dict(e)
            for e in await self._results.list_evidence(result_id)
        ]

    async def get_judge_execution(self, execution_id: str) -> dict[str, Any]:
        execution = await self._judges.get_execution(execution_id)
        return {
            "id": execution.id,
            "call_run_id": execution.call_run_id,
            "call_attempt_id": execution.call_attempt_id,
            "status": execution.status,
            "rubric_version": execution.rubric_version,
            "evidence_coverage": (
                float(execution.evidence_coverage)
                if execution.evidence_coverage is not None
                else None
            ),
            "needs_human_review": execution.needs_human_review,
            "alignment_conflict": execution.alignment_conflict,
            "latency_ms": execution.latency_ms,
            "parsed_output": execution.parsed_output,
        }

    async def get_run(self, call_run_id: str) -> dict[str, Any]:
        return _run_dict(await self._runs.get_run(call_run_id))

    async def list_runs(self, run_id: str) -> list[dict[str, Any]]:
        return [_run_dict(run) for run in await self._runs.list_runs(run_id)]

    async def list_attempts(self, call_run_id: str) -> list[dict[str, Any]]:
        await self._runs.get_run(call_run_id)
        return [
            _attempt_dict(attempt)
            for attempt in await self._attempts.list_attempts(call_run_id)
        ]

    async def _manifest_for_run(self, run_id: str) -> domain.ExecutionManifest:
        for call_run in await self._runs.list_runs(run_id):
            for attempt in await self._attempts.list_attempts(call_run.id):
                if attempt.execution_manifest_id:
                    return await self._manifests.get(attempt.execution_manifest_id)
        raise ResourceNotFoundError(
            f"run '{run_id}' has no execution manifest; start it first"
        )

    async def get_manifest(self, run_id: str) -> dict[str, Any]:
        manifest = await self._manifest_for_run(run_id)
        return {
            "id": manifest.id,
            "schema_version": manifest.schema_version,
            "target_snapshot": manifest.target_snapshot,
            "simulation_snapshot": manifest.simulation_snapshot,
            "run_snapshot": manifest.run_snapshot,
            "evaluator_snapshot": manifest.evaluator_snapshot,
            "benchmark_snapshot": manifest.benchmark_snapshot,
            "caller_snapshot": manifest.caller_snapshot,
            "metric_snapshot": manifest.metric_snapshot,
            "judge_snapshot": manifest.judge_snapshot,
            "aggregation_snapshot": manifest.aggregation_snapshot,
            "composite_snapshot": manifest.composite_snapshot,
            "manifest_hash": manifest.manifest_hash,
            "created_at": manifest.created_at,
        }

    async def get_attempt(self, attempt_id: str) -> dict[str, Any]:
        return _attempt_dict(await self._attempts.get_attempt(attempt_id))

    async def list_events(
        self,
        attempt_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
        source: str | None = None,
        event_type: str | None = None,
        from_ms: int | None = None,
        to_ms: int | None = None,
    ) -> dict[str, Any]:
        await self._attempts.get_attempt(attempt_id)
        events = await self._events.list_events(
            attempt_id,
            limit=limit,
            offset=offset,
            source=source,
            event_type=event_type,
            from_ms=from_ms,
            to_ms=to_ms,
        )
        total = await self._events.count_events(
            attempt_id,
            source=source,
            event_type=event_type,
            from_ms=from_ms,
            to_ms=to_ms,
        )
        return {
            "items": [_event_dict(e) for e in events],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_conversation(self, attempt_id: str) -> dict[str, Any]:
        await self._attempts.get_attempt(attempt_id)
        turns = await self._materialization.list_turns(attempt_id)
        tools = await self._materialization.list_tool_calls(attempt_id)
        states = await self._materialization.list_state_transitions(attempt_id)
        return {
            "attempt_id": attempt_id,
            "turns": [_turn_dict(t) for t in turns],
            "tool_calls": [_tool_dict(t) for t in tools],
            "state_transitions": [_state_dict(s) for s in states],
        }

    async def list_media(self, attempt_id: str) -> list[dict[str, Any]]:
        await self._attempts.get_attempt(attempt_id)
        return [_media_dict(m) for m in await self._media.list_artifacts(attempt_id)]

    async def media_url(
        self, artifact_id: str, *, expires_in_seconds: int = DEFAULT_MEDIA_URL_EXPIRES
    ) -> dict[str, Any]:
        artifact = await self._media.get_artifact(artifact_id)
        if not artifact.object_uri:
            raise ResourceNotFoundError(
                f"media artifact '{artifact_id}' has no stored object"
            )
        url = get_object_store().url(
            _object_key(artifact.object_uri), expires_in_seconds=expires_in_seconds
        )
        return {
            "media_artifact_id": artifact_id,
            "url": url,
            "expires_in_seconds": expires_in_seconds,
        }

    async def list_aggregates(self, run_id: str) -> list[dict[str, Any]]:
        definitions = await self._definitions()
        return [
            aggregate_to_dict(a, definitions.get(a.metric_definition_id))
            for a in await self._results.list_aggregates(run_id)
        ]

    async def get_composite(self, run_id: str) -> dict[str, Any] | None:
        return await self._composite_dict(run_id)

    async def run_results(self, run_id: str) -> dict[str, Any]:
        evaluators = await self._run_evaluators.list_evaluators(run_id)
        call_runs = await self._runs.list_runs(run_id)
        aggregates = await self._results.list_aggregates(run_id)
        definitions = await self._definitions()

        evaluator_blocks: list[dict[str, Any]] = []
        for evaluator in evaluators:
            evaluator_call_runs = [
                run for run in call_runs if run.run_evaluator_id == evaluator.id
            ]
            metric_results: list[dict[str, Any]] = []
            for run in evaluator_call_runs:
                for result in await self._metrics.list_results(run.id):
                    metric_results.append(
                        metric_result_to_dict(
                            result, definitions.get(result.metric_definition_id)
                        )
                    )
            evaluator_blocks.append(
                {
                    "run_evaluator_id": evaluator.id,
                    "runs": [_run_dict(run) for run in evaluator_call_runs],
                    "metrics": [
                        aggregate_to_dict(a, definitions.get(a.metric_definition_id))
                        for a in aggregates
                        if a.run_evaluator_id == evaluator.id
                    ],
                    "metric_results": metric_results,
                }
            )

        return {
            "run_id": run_id,
            "status": "ok",
            "evaluators": evaluator_blocks,
            "composite": await self._composite_dict(run_id),
        }

    async def evaluator_results(
        self, run_id: str, run_evaluator_id: str
    ) -> dict[str, Any]:
        call_runs = [
            run
            for run in await self._runs.list_runs(run_id)
            if run.run_evaluator_id == run_evaluator_id
        ]
        aggregates = await self._results.list_aggregates(
            run_id, run_evaluator_id=run_evaluator_id
        )
        definitions = await self._definitions()
        metric_results: list[dict[str, Any]] = []
        for run in call_runs:
            for result in await self._metrics.list_results(run.id):
                metric_results.append(
                    metric_result_to_dict(
                        result, definitions.get(result.metric_definition_id)
                    )
                )
        return {
            "run_id": run_id,
            "status": "ok",
            "evaluators": [
                {
                    "run_evaluator_id": run_evaluator_id,
                    "runs": [_run_dict(run) for run in call_runs],
                    "metrics": [
                        aggregate_to_dict(a, definitions.get(a.metric_definition_id))
                        for a in aggregates
                    ],
                    "metric_results": metric_results,
                }
            ],
            "composite": None,
        }

    async def _composite_dict(self, run_id: str) -> dict[str, Any] | None:
        composite = await self._results.get_composite_result_for_run(run_id)
        if composite is None:
            return None
        definitions = await self._definitions()
        required = set(DEFAULT_COVERAGE_POLICY.get("required_metrics") or [])
        available = {
            definitions[a.metric_definition_id].metric_key
            for a in await self._results.list_aggregates(run_id)
            if a.metric_definition_id in definitions and a.coverage_count > 0
        }
        return {
            "run_id": run_id,
            "status": composite.status,
            "score_0_100": (
                float(composite.score_0_100)
                if composite.score_0_100 is not None
                else None
            ),
            "coverage_ratio": (
                float(composite.coverage_ratio)
                if composite.coverage_ratio is not None
                else None
            ),
            "unavailable_weight": (
                float(composite.unavailable_weight)
                if composite.unavailable_weight is not None
                else None
            ),
            "category_scores": composite.category_scores,
            "missing_metrics": sorted(required - available),
        }


class ForensicsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._runs = CallRunRepository(session)
        self._run_evaluators = RunEvaluatorRepository(session)
        self._attempts = CallAttemptRepository(session)
        self._events = RuntimeEventRepository(session)
        self._materialization = MaterializationRepository(session)
        self._media = MediaArtifactRepository(session)
        self._metrics = MetricRepository(session)
        self._results = ResultRepository(session)

    async def reconstruct(self, call_run_id: str) -> dict[str, Any]:
        run = await self._runs.get_run(call_run_id)
        evaluator = await self._run_evaluators.get_evaluator(run.run_evaluator_id)
        attempt = await self._select_attempt(run)

        definitions = {d.id: d for d in await self._metrics.list_definitions()}
        metric_results = await self._metrics.list_results(run.id)
        metric_result_dicts = [
            metric_result_to_dict(r, definitions.get(r.metric_definition_id))
            for r in metric_results
        ]
        evidence = [
            evidence_to_dict(e)
            for e in await self._results.list_evidence_for_results(
                [r.id for r in metric_results]
            )
        ]
        aggregates = await self._results.list_aggregates(
            run.run_id, run_evaluator_id=run.run_evaluator_id
        )

        events: list[dict[str, Any]] = []
        turns: list[dict[str, Any]] = []
        tools: list[dict[str, Any]] = []
        media: list[dict[str, Any]] = []
        if attempt is not None:
            events = [_event_dict(e) for e in await self._events.list_events(attempt.id)]
            turns = [
                _turn_dict(t) for t in await self._materialization.list_turns(attempt.id)
            ]
            tools = [
                _tool_dict(t)
                for t in await self._materialization.list_tool_calls(attempt.id)
            ]
            media = [
                _media_dict(m) for m in await self._media.list_artifacts(attempt.id)
            ]

        composite = await ResultService(self._session)._composite_dict(run.run_id)

        return {
            "run": _run_dict(run),
            "evaluator": {
                "id": evaluator.id,
                "run_id": evaluator.run_id,
                "sequence_no": evaluator.sequence_no,
                "scenario": evaluator.scenario,
                "personality": list(evaluator.personality or []),
            },
            "selection": {
                "run_id": evaluator.run_id,
                "run_evaluator_id": evaluator.id,
            },
            "attempt": _attempt_dict(attempt) if attempt is not None else {},
            "summary": {
                "metrics": metric_result_dicts,
                "scores": [
                    aggregate_to_dict(a, definitions.get(a.metric_definition_id))
                    for a in aggregates
                ],
                "composite": composite,
            },
            "conversation": {"turns": turns, "events": events, "tool_calls": tools},
            "evidence": evidence,
            "media": media,
        }

    async def _select_attempt(self, run: runtime.CallRun) -> runtime.CallAttempt | None:
        attempts = await self._attempts.list_attempts(run.id)
        if not attempts:
            return None
        if run.selected_attempt_id:
            for attempt in attempts:
                if attempt.id == run.selected_attempt_id:
                    return attempt
        terminal = [
            attempt for attempt in attempts if attempt.status == AttemptStatus.TERMINAL.value
        ]
        return terminal[-1] if terminal else attempts[-1]


__all__ = [
    "DEFAULT_COMPOSITE_VERSION",
    "ForensicsService",
    "ResultService",
    "aggregate_to_dict",
    "evidence_to_dict",
    "metric_result_to_dict",
]
