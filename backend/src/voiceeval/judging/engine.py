"""The Voice-Agent Judge engine.

For one completed ``CallRun`` it resolves the evaluable attempt, resolves and
validates the media bundle, runs Stage 0, builds the evidence ledgers, evaluates
every requested metric in parallel (Jev probes + LLM investigation + code),
verifies/escalates, assembles the §9 result document and persists it.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import ValidationError
from voiceeval.core.logging import bind_execution_context
from voiceeval.db.models import results, runtime
from voiceeval.db.repositories import (
    CallAttemptRepository,
    CallRunRepository,
    JudgeRepository,
)
from voiceeval.domain.enums import AttemptStatus, JudgeExecutionStatus
from voiceeval.judging import config as judge_config
from voiceeval.judging.evidence.builder import EvidenceBuilder, EvidenceContext, Ledgers
from voiceeval.judging.evidence.injection import InjectionScreen
from voiceeval.judging.llm import (
    adjudicator_model_id,
    audio_model_id,
    get_judge_decision_model,
    get_judge_llm,
    judge_model_id,
    verifier_model_id,
)
from voiceeval.judging.metrics.base import (
    MetricContext,
    MetricEvaluation,
    all_evaluators,
    evaluate_metric,
    not_measurable,
)
from voiceeval.judging.probes.jev import JevRunner
from voiceeval.judging.resolver import MediaResolver
from voiceeval.judging.retrieval.factory import get_retrieval
from voiceeval.judging.schemas import (
    DecisionModelsBlock,
    JudgeRunResult,
    MediaArtifactRef,
    MediaBundleBlock,
    MediaValidation,
    MetricBlock,
    MetricProvenance,
)
from voiceeval.judging.stage0.runner import Stage0Runner
from voiceeval.judging.storage import JudgeStorage
from voiceeval.judging.verify.pipeline import VerificationPipeline
from voiceeval.llm.base import BaseGenerationModel, DecisionModel
from voiceeval.metrics.engine import build_attempt_inputs
from voiceeval.metrics.registry import MetricRegistry, get_metric_registry
from voiceeval.observability.tracing import span
from voiceeval.realtime.pubsub import JUDGE_COMPLETED, publish_plan_event

logger = logging.getLogger("voiceeval.judging")


@dataclass
class JudgeRun:
    run_id: str
    attempt_id: str
    result: JudgeRunResult
    evaluations: list[MetricEvaluation]
    ledgers: Ledgers
    status: str = JudgeExecutionStatus.COMPLETED.value
    needs_human_review: bool = False
    alignment_conflict: bool = False
    evidence_coverage: float = 0.0
    flags: list[str] = field(default_factory=list)
    latency_ms: int | None = None
    input_hash: str | None = None


class JudgeEngine:
    def __init__(
        self,
        session: AsyncSession,
        *,
        registry: MetricRegistry | None = None,
        decision_model: DecisionModel | None = None,
        llm: BaseGenerationModel | None = None,
        settings: Settings | None = None,
        stage0: Stage0Runner | None = None,
        retrieval=None,
    ) -> None:
        self._session = session
        self._registry = registry or get_metric_registry()
        self._decision_model = decision_model
        self._llm = llm
        self._settings = settings or get_settings()
        self._stage0 = stage0
        self._retrieval = retrieval or get_retrieval()
        self._runs = CallRunRepository(session)
        self._attempts = CallAttemptRepository(session)
        self._judges = JudgeRepository(session)
        self._storage = JudgeStorage(session, self._registry)

    async def evaluate_run(self, call_run_id: str) -> list[results.MetricResult]:
        run = await self._runs.get_run(call_run_id)
        attempt = await self._select_attempt(run)

        definition = await self._judges.get_or_create_definition(
            judge_key=judge_config.JUDGE_KEY,
            version=judge_config.JUDGE_VERSION,
            kind=judge_config.JUDGE_KIND,
            provider="openrouter",
            model=judge_model_id(),
            rubric_version=judge_config.rubric_version(),
            output_schema_version=judge_config.OUTPUT_SCHEMA_VERSION,
            config={
                "adjudicator": adjudicator_model_id(),
                "verifier": verifier_model_id(),
                "audio": audio_model_id(),
                "jev": self._settings.jev_model,
            },
        )
        execution = await self._judges.create_execution(
            call_run_id=run.id,
            judge_definition_id=definition.id,
            call_attempt_id=attempt.id,
            rubric_version=judge_config.rubric_version(),
        )

        with bind_execution_context(plan_id=run.run_id, run_id=run.id, attempt_id=attempt.id):
            with span(
                "judge.evaluate",
                plan_id=run.run_id,
                run_id=run.id,
                attempt_id=attempt.id,
                judge_key=judge_config.JUDGE_KEY,
            ):
                judge_run = await self.judge_attempt(attempt)
                judge_run.run_id = run.run_id

                await self._judges.update_execution(
                    execution,
                    status=judge_run.status,
                    parsed_output=judge_run.result.model_dump(mode="json"),
                    latency_ms=judge_run.latency_ms,
                    input_hash=judge_run.input_hash,
                    evidence_coverage=judge_run.evidence_coverage,
                    needs_human_review=judge_run.needs_human_review,
                    alignment_conflict=judge_run.alignment_conflict,
                    media_validation=judge_run.result.media.validation.model_dump(mode="json"),
                )
                await self._storage.write_ledgers(execution.id, judge_run.ledgers)
                written = await self._storage.write_metrics(
                    execution_id=execution.id,
                    run_id=run.id,
                    attempt_id=attempt.id,
                    plan_id=run.run_id,
                    evaluations=judge_run.evaluations,
                )
        await publish_plan_event(
            run.run_id,
            JUDGE_COMPLETED,
            {
                "run_id": run.id,
                "attempt_id": attempt.id,
                "judge_execution_id": execution.id,
                "status": judge_run.status,
                "needs_human_review": judge_run.needs_human_review,
            },
        )
        return written

    async def judge_attempt(self, attempt: runtime.CallAttempt) -> JudgeRun:
        import time

        started = time.monotonic()
        inputs = await build_attempt_inputs(self._session, attempt)
        evaluator = inputs.evaluator
        content = inputs.context.evaluator_content

        judge_prompt = content.get("expected_output_prompt") or ""
        scenario = content.get("scenario") or ""
        language_policy = evaluator.language_policy or {"mode": "mirror_caller"}
        kb_collection_id = evaluator.kb_collection_id
        evaluator_content = {**content, "kb_collection_id": kb_collection_id}

        requested = self._requested_metrics(evaluator.metrics)
        validation = MediaValidation()
        bundle = await MediaResolver(self._session).resolve(attempt.id)
        runner = self._make_stage0()
        stage0 = runner.run(bundle, inputs.context.signals)
        validation = stage0.validation

        decision_model = self._decision_model or get_judge_decision_model()
        llm = self._llm if self._llm is not None else get_judge_llm()
        jev = JevRunner(decision_model)
        inbox = InjectionScreen(jev)
        verify = VerificationPipeline(
            llm,
            adjudicator_model=adjudicator_model_id(),
            verifier_model=verifier_model_id(),
        )

        ledgers = await EvidenceBuilder(injection=inbox).build(
            EvidenceContext(
                llm=llm,
                runner=jev,
                stage0=stage0,
                signals=inputs.context.signals,
                evaluator_content=evaluator_content,
                judge_prompt=judge_prompt,
                scenario=scenario,
                language_policy=language_policy,
                requested_metrics=requested,
            )
        )

        evaluations = await self._evaluate_metrics(
            requested=requested,
            stage0=stage0,
            signals=inputs.context.signals,
            ledgers=ledgers,
            evaluator_content=evaluator_content,
            judge_prompt=judge_prompt,
            scenario=scenario,
            language_policy=language_policy,
            capabilities=inputs.context.capabilities,
            jev=jev,
            llm=llm,
            verify=verify,
        )

        flags = _consistency_flags(evaluations)
        needs_human_review = verify.needs_human_review or any(
            (e.sanity.gap or 0) > 1 for e in evaluations if e.sanity is not None
        )
        artifacts = _artifact_refs(bundle)
        media_sources = sorted(artifacts.keys())
        latency_ms = int((time.monotonic() - started) * 1000)
        input_hash = _hash_input(evaluator_content, judge_prompt)
        status = JudgeExecutionStatus.COMPLETED.value
        result = JudgeRunResult(
            run_id=inputs.run.run_id,
            rubric_version=judge_config.rubric_version(),
            judge_version=judge_config.JUDGE_VERSION,
            status=status,
            decision_models=DecisionModelsBlock(
                jev=_jev_models(evaluations),
                adjudicator=adjudicator_model_id(),
                verifier=verifier_model_id(),
                audio=audio_model_id(),
            ),
            media=MediaBundleBlock(
                artifacts=artifacts,
                validation=validation,
            ),
            evidence_coverage=ledgers.coverage,
            needs_human_review=needs_human_review,
            alignment_conflict=stage0.alignment_conflict,
            flags=flags,
            latency_ms=latency_ms,
            input_hash=input_hash,
            metrics=[_metric_block(e, stage0, media_sources=media_sources) for e in evaluations],
            timeline=_timeline(evaluations),
        )
        return JudgeRun(
            run_id=inputs.run.run_id,
            attempt_id=attempt.id,
            result=result,
            evaluations=evaluations,
            ledgers=ledgers,
            status=status,
            needs_human_review=needs_human_review,
            alignment_conflict=stage0.alignment_conflict,
            evidence_coverage=ledgers.coverage,
            flags=flags,
            latency_ms=latency_ms,
            input_hash=input_hash,
        )

    async def _evaluate_metrics(
        self,
        *,
        requested: set[str],
        stage0,
        signals,
        ledgers,
        evaluator_content,
        judge_prompt,
        scenario,
        language_policy,
        capabilities,
        jev,
        llm,
        verify,
    ) -> list[MetricEvaluation]:
        evaluators = all_evaluators()
        semaphore = asyncio.Semaphore(max(1, self._settings.llm_max_concurrent_requests))

        async def run_one(metric_key: str) -> MetricEvaluation:
            try:
                spec = self._registry.get(metric_key)
            except ValidationError:
                return MetricEvaluation(metric_key=metric_key, status="invalid",
                                        breakdown={"detail": "unregistered_metric"})
            missing = spec.required_capabilities - capabilities
            if missing:
                return not_measurable(metric_key, f"capability_missing: {sorted(missing)}")
            ctx = MetricContext(
                spec=spec,
                stage0=stage0,
                signals=signals,
                ledgers=ledgers,
                evaluator_content=evaluator_content,
                judge_prompt=judge_prompt,
                scenario=scenario,
                language_policy=language_policy,
                capabilities=capabilities,
                runner=jev,
                llm=llm,
                retrieval=self._retrieval,
                settings=self._settings,
                verify=verify,
            )
            async with semaphore:
                try:
                    return await evaluate_metric(ctx)
                except Exception as exc:  # noqa: BLE001 - never fail the whole run
                    logger.exception("metric %s failed", metric_key)
                    return MetricEvaluation(metric_key=metric_key, status="invalid",
                                            breakdown={"detail": f"metric_failed: {exc}"})

        ordered = [key for key in _ORDERED_METRICS if key in requested and key in evaluators]
        results_list = await asyncio.gather(*(run_one(key) for key in ordered))
        return list(results_list)

    def _requested_metrics(self, metrics: list | None) -> set[str]:
        known = set(all_evaluators())
        requested = {m for m in (metrics or []) if m in known}
        return requested or known

    def _make_stage0(self) -> Stage0Runner:
        if self._stage0 is not None:
            return self._stage0
        return Stage0Runner(settings=self._settings)

    async def _select_attempt(self, run: runtime.CallRun) -> runtime.CallAttempt:
        attempts = await self._attempts.list_attempts(run.id)
        if run.selected_attempt_id:
            for attempt in attempts:
                if attempt.id == run.selected_attempt_id:
                    return attempt
        eligible = [
            attempt
            for attempt in attempts
            if attempt.status == AttemptStatus.TERMINAL.value and attempt.eligible_for_evaluation
        ]
        if eligible:
            return eligible[-1]
        terminal = [
            attempt for attempt in attempts if attempt.status == AttemptStatus.TERMINAL.value
        ]
        if terminal:
            return terminal[-1]
        raise ValidationError(f"run '{run.id}' has no terminal attempt to judge")


_ORDERED_METRICS = (
    "ttfa",
    "ttft",
    "barge_in_latency",
    "barge_in_success_rate",
    "language_detection_accuracy",
    "relevancy",
    "context_retention",
    "instruction_following",
    "empathy",
    "hallucination",
    "semantic_preservation",
    "language_consistency",
    "repetition",
    "task_completion",
    "kb_groundedness",
    "code_switching_accuracy",
)


def _consistency_flags(evaluations: list[MetricEvaluation]) -> list[str]:
    from voiceeval.judging.verify.consistency import evaluate_consistency

    metrics = {
        e.metric_key: {"value": e.value, "breakdown": e.breakdown} for e in evaluations
    }
    return evaluate_consistency(metrics)


def _jev_models(evaluations: list[MetricEvaluation]) -> list[str]:
    models = {
        probe.jev_model
        for evaluation in evaluations
        for probe in evaluation.probes
        if probe.jev_model
    }
    return sorted(models)


def _artifact_refs(bundle) -> dict[str, MediaArtifactRef]:
    refs: dict[str, MediaArtifactRef] = {}
    for role, media in bundle.media.items():
        refs[role] = MediaArtifactRef(
            media_artifact_id=getattr(media.row, "id", None),
            object_uri=media.object_uri,
            sha256=media.sha256,
            size_bytes=media.size_bytes,
            sample_rate=media.sample_rate,
            channels=media.channels,
            duration_ms=media.duration_ms,
            format=media.format,
        )
    return refs


def _metric_block(
    evaluation: MetricEvaluation, stage0, *, media_sources: list[str]
) -> MetricBlock:
    return MetricBlock(
        metric_key=evaluation.metric_key,
        status=evaluation.status,
        value=evaluation.value,
        scale=list(judge_config.METRIC_SCALE) if isinstance(evaluation.value, (int, float)) and not isinstance(evaluation.value, bool) and evaluation.metric_key in {
            "relevancy", "context_retention", "instruction_following", "empathy",
            "hallucination", "semantic_preservation", "language_consistency",
        } else None,
        direction=evaluation.direction,
        normalized=evaluation.normalized,
        confidence=evaluation.confidence,
        method=evaluation.method,
        summary=evaluation.summary,
        breakdown=evaluation.breakdown,
        sanity=evaluation.sanity,
        probes=evaluation.probes,
        findings=evaluation.findings,
        provenance=MetricProvenance(
            jev_response_models=sorted({p.jev_model for p in evaluation.probes if p.jev_model}),
            media_sources=media_sources,
        ),
        caveats=evaluation.caveats,
    )


def _timeline(evaluations: list[MetricEvaluation]) -> list:
    from voiceeval.judging.schemas import TimelineFlag

    flags: dict[Any, list[str]] = {}
    for evaluation in evaluations:
        for finding in evaluation.findings:
            for turn_id in finding.turn_ids or []:
                flags.setdefault(turn_id, []).append(finding.type)
    return [TimelineFlag(turn_id=turn_id, flags=sorted(set(values))) for turn_id, values in flags.items()]


def _hash_input(evaluator_content: dict, judge_prompt: str) -> str:
    digest = hashlib.sha256()
    digest.update(judge_prompt.encode("utf-8"))
    digest.update(judge_config.rubric_version().encode("utf-8"))
    for key in sorted(evaluator_content):
        digest.update(str(evaluator_content[key]).encode("utf-8"))
    return digest.hexdigest()


__all__ = ["JudgeEngine", "JudgeRun"]
