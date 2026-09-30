"""The deterministic metric engine.

For one eligible attempt it loads the observed truth (events, turns, tool calls,
media) plus the evaluator's expectations, evaluates every registered
deterministic metric, and persists a :class:`MetricResult` — plus the evidence
pointers that support it — for each outcome.

Capability gating happens *here* before a metric runs: a metric whose required
capabilities are absent becomes ``NOT_AVAILABLE`` with the missing capabilities
recorded, never a zero. A metric that raises becomes ``ERROR``; the availability
classes stay distinct.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.core.logging import bind_execution_context
from voiceeval.db.models import domain, results, runtime
from voiceeval.db.repositories import (
    CallAttemptRepository,
    MaterializationRepository,
    MediaArtifactRepository,
    MetricRepository,
    ResultRepository,
    RunEvaluatorRepository,
    RuntimeEventRepository,
)
from voiceeval.metrics.catalog import DETERMINISTIC_METRIC_KEYS
from voiceeval.metrics.deterministic import DETERMINISTIC_METRICS, MetricContext
from voiceeval.metrics.outcome import MetricOutcome, not_available
from voiceeval.metrics.registry import MetricRegistry, MetricSpec, get_metric_registry
from voiceeval.metrics.signals import AttemptSignals
from voiceeval.observability.tracing import span
from voiceeval.realtime.pubsub import METRIC_COMPUTED, publish_plan_event
from voiceeval.services.capabilities import extract_capabilities

logger = logging.getLogger("voiceeval.metrics")


@dataclass
class AttemptEvaluationInputs:
    attempt: runtime.CallAttempt
    run: runtime.CallRun
    manifest: domain.ExecutionManifest
    evaluator: domain.RunEvaluator
    context: MetricContext

    @property
    def run_id(self) -> str:
        """The domain ``Run`` id (the batch correlation id for this attempt)."""
        return self.run.run_id


def evaluator_content(evaluator: domain.RunEvaluator) -> dict[str, Any]:
    """Synthesize the evaluator-content view the metric/judge engines consume.

    The v0.4 ``RunEvaluator`` persists a rendered scenario plus the
    language/personality selection, so metrics that look for declared
    ``tools`` or ``motive.assertions`` find empty lists rather than failing.
    """
    personality = list(evaluator.personality or [])
    return {
        "scenario": evaluator.scenario,
        "expected_output_prompt": evaluator.expected_output_prompt,
        "metrics": list(evaluator.metrics or []),
        "languages": evaluator.languages or {},
        "personality": personality,
        # Persona traits drive the caller; surface them where expected.
        "persona": {"traits": personality},
        "motive": {"objective": evaluator.expected_output_prompt, "assertions": []},
    }


def expected_tools(evaluator_content: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve the evaluator's expected tool calls, if any are declared.

    Evaluators may declare expectations either through an explicit ``tools``
    list or through a motive assertion ``expectation`` that names a tool.
    """
    declared = evaluator_content.get("tools") or evaluator_content.get("expected_tools")
    if isinstance(declared, list):
        return [item for item in declared if isinstance(item, dict)]

    resolved: list[dict[str, Any]] = []
    for assertion in (evaluator_content.get("motive") or {}).get("assertions") or []:
        expectation = assertion.get("expectation") or {}
        tool = expectation.get("tool") or expectation.get("tool_name")
        if tool:
            resolved.append(
                {
                    "name": tool,
                    "arguments": expectation.get("arguments") or {},
                }
            )
    return resolved


async def build_attempt_inputs(
    session: AsyncSession, attempt: runtime.CallAttempt
) -> AttemptEvaluationInputs:
    manifest = await session.get(domain.ExecutionManifest, attempt.execution_manifest_id)
    if manifest is None:
        raise ResourceNotFoundError(
            f"execution manifest '{attempt.execution_manifest_id}' not found"
        )
    run = await session.get(runtime.CallRun, attempt.call_run_id)
    if run is None:
        raise ResourceNotFoundError(f"call run '{attempt.call_run_id}' not found")
    evaluator = await RunEvaluatorRepository(session).get_evaluator(
        run.run_evaluator_id
    )

    events = await RuntimeEventRepository(session).list_events(attempt.id)
    turns = await MaterializationRepository(session).list_turns(attempt.id)
    tool_calls = await MaterializationRepository(session).list_tool_calls(attempt.id)
    media = await MediaArtifactRepository(session).list_artifacts(attempt.id)

    signals = AttemptSignals.from_records(
        events=events, turns=turns, tool_calls=tool_calls, media=media
    )
    capability_snapshot = dict(manifest.target_snapshot.get("capability_snapshot") or {})
    capabilities = frozenset(extract_capabilities(capability_snapshot))
    content = evaluator_content(evaluator)
    context = MetricContext(
        signals=signals,
        capabilities=capabilities,
        expected_tools=expected_tools(content),
        evaluator_content=content,
    )
    return AttemptEvaluationInputs(
        attempt=attempt,
        run=run,
        manifest=manifest,
        evaluator=evaluator,
        context=context,
    )


def evaluate_deterministic(
    context: MetricContext, *, registry: MetricRegistry | None = None
) -> list[MetricOutcome]:
    """Evaluate every deterministic metric against one attempt's signals."""
    registry = registry or get_metric_registry()
    outcomes: list[MetricOutcome] = []
    for metric_key in sorted(DETERMINISTIC_METRIC_KEYS):
        spec = registry.get(metric_key)
        outcomes.append(evaluate_one(spec, context))
    return outcomes


def evaluate_one(spec: MetricSpec, context: MetricContext) -> MetricOutcome:
    missing = spec.required_capabilities - context.capabilities
    if missing:
        outcome = not_available(
            spec,
            f"required capabilities not exposed: {sorted(missing)}",
            measurement_basis={"missing_capabilities": sorted(missing)},
        )
        outcome.validate()
        return outcome

    compute = DETERMINISTIC_METRICS.get(spec.metric_key)
    if compute is None:  # pragma: no cover - catalog/registry stay in sync
        from voiceeval.metrics.outcome import error as error_outcome

        return error_outcome(spec, f"no deterministic implementation for '{spec.metric_key}'")
    try:
        outcome = compute(spec, context)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("metric %s failed", spec.metric_key)
        from voiceeval.metrics.outcome import error as error_outcome

        outcome = error_outcome(spec, f"metric computation failed: {exc}")
    outcome.validate()
    return outcome


class MetricResultWriter:
    """Persists metric outcomes, their evidence and definition rows.

    Shared by the deterministic metric engine and the judge engine so both write
    results (and evidence pointers) identically.
    """

    def __init__(self, session: AsyncSession, registry: MetricRegistry) -> None:
        self._metrics = MetricRepository(session)
        self._results = ResultRepository(session)
        self._registry = registry
        self._definition_ids: dict[tuple[str, str], str] = {}

    async def definition_id(self, spec: MetricSpec) -> str:
        key = (spec.metric_key, spec.version)
        cached = self._definition_ids.get(key)
        if cached is not None:
            return cached
        existing = await self._metrics.find_definition(spec.metric_key, spec.version)
        if existing is None:
            existing = await self._metrics.create_definition(
                **spec.as_definition_kwargs()
            )
        self._definition_ids[key] = existing.id
        return existing.id

    async def write(
        self,
        *,
        run_id: str,
        attempt_id: str,
        plan_id: str,
        outcomes: list[MetricOutcome],
        judge_execution_id: str | None = None,
        computed_at: datetime | None = None,
    ) -> list[results.MetricResult]:
        moment = computed_at or datetime.now(timezone.utc)
        written: list[results.MetricResult] = []
        for outcome in outcomes:
            spec = self._registry.get(outcome.metric_key, outcome.version)
            definition_id = await self.definition_id(spec)
            result = await self._metrics.create_result(
                call_run_id=run_id,
                call_attempt_id=attempt_id,
                metric_definition_id=definition_id,
                status=outcome.status.value,
                value_type=(
                    outcome.value_type.value if outcome.value_type is not None else None
                ),
                unit=outcome.unit,
                scale_min=outcome.scale_min,
                scale_max=outcome.scale_max,
                method=outcome.method,
                measurement_basis=outcome.measurement_basis,
                confidence=outcome.confidence,
                judge_execution_id=judge_execution_id,
                computed_at=moment if outcome.is_computed else None,
                **typed_value_kwargs(outcome),
            )
            for evidence in outcome.evidence:
                await self._results.add_evidence(
                    metric_result_id=result.id,
                    source_type=evidence.source_type,
                    source_id=evidence.source_id,
                    start_ms=evidence.start_ms,
                    end_ms=evidence.end_ms,
                    quote=evidence.quote,
                    rationale=evidence.rationale,
                )
            await publish_plan_event(
                plan_id,
                METRIC_COMPUTED,
                {
                    "metric_key": outcome.metric_key,
                    "status": outcome.status.value,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                },
            )
            written.append(result)
        return written


def typed_value_kwargs(outcome: MetricOutcome) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "value_numeric": None,
        "value_boolean": None,
        "value_text": None,
        "value_category": None,
    }
    if outcome.is_computed and outcome.value is not None:
        kwargs[outcome.value_column()] = outcome.value
    return kwargs


class MetricEngine:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: MetricRegistry | None = None,
    ) -> None:
        self._session = session
        self._registry = registry or get_metric_registry()
        self._writer = MetricResultWriter(session, self._registry)

    async def compute_for_attempt(
        self, attempt_id: str, *, persist: bool = True
    ) -> list[MetricOutcome]:
        attempt = await CallAttemptRepository(self._session).get_attempt(attempt_id)
        inputs = await build_attempt_inputs(self._session, attempt)
        with bind_execution_context(
            plan_id=inputs.run_id,
            run_id=inputs.run.id,
            attempt_id=inputs.attempt.id,
        ):
            with span(
                "metrics.compute",
                plan_id=inputs.run_id,
                run_id=inputs.run.id,
                attempt_id=inputs.attempt.id,
            ):
                outcomes = evaluate_deterministic(
                    inputs.context, registry=self._registry
                )
                if persist:
                    await self._writer.write(
                        run_id=inputs.run.id,
                        attempt_id=inputs.attempt.id,
                        plan_id=inputs.run_id,
                        outcomes=outcomes,
                    )
        return outcomes


__all__ = [
    "AttemptEvaluationInputs",
    "MetricEngine",
    "MetricResultWriter",
    "build_attempt_inputs",
    "evaluate_deterministic",
    "evaluator_content",
    "expected_tools",
    "typed_value_kwargs",
]
