"""Build and persist the immutable execution manifest for a logical call run.

The manifest is per ``CallRun``: it snapshots the target/link, the Simulation,
the Run, the exact RunEvaluator being executed, and the caller persona + seed,
then is content-addressed by ``manifest_hash``. Attempts reference it, so every
physical attempt of a call run shares one frozen execution truth.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.config import Settings, get_settings
from voiceeval.core.errors import ResourceNotFoundError
from voiceeval.db.models import domain, runtime
from voiceeval.db.repositories import ManifestRepository
from voiceeval.orchestration.manifest import build_manifest_content
from voiceeval.orchestration.target_link import resolve_target_link
from voiceeval.runtime.loader import resolve_persona


async def get_or_create_manifest_for_call_run(
    session: AsyncSession,
    *,
    call_run: runtime.CallRun,
    run: domain.Run,
    evaluator: domain.RunEvaluator,
    settings: Settings | None = None,
    judge_definitions: list | None = None,
) -> domain.ExecutionManifest:
    settings = settings or get_settings()

    target_revision = await session.get(
        domain.AgentTargetRevision, run.target_revision_id
    )
    if target_revision is None:
        raise ResourceNotFoundError(
            f"target revision '{run.target_revision_id}' not found"
        )
    simulation = await session.get(domain.Simulation, run.simulation_id)
    target_link = await resolve_target_link(session, run.target_revision_id)
    persona = resolve_persona(evaluator, seed=call_run.run_seed)

    content = build_manifest_content(
        target_revision=target_revision,
        run_evaluators=[evaluator],
        simulation=simulation,
        run=run,
        target_link=target_link,
        caller_persona=persona.to_dict(),
        seed=call_run.run_seed,
        judge_definitions=judge_definitions,
        settings=settings,
    )

    repo = ManifestRepository(session)
    existing = await repo.find_by_hash(content.manifest_hash)
    if existing is not None:
        return existing

    return await repo.create(
        schema_version=content.schema_version,
        target_snapshot=content.target_snapshot,
        simulation_snapshot=content.simulation_snapshot,
        run_snapshot=content.run_snapshot,
        evaluator_snapshot=content.evaluator_snapshot,
        benchmark_snapshot=content.benchmark_snapshot,
        caller_snapshot=content.caller_snapshot,
        metric_snapshot=content.metric_snapshot,
        judge_snapshot=content.judge_snapshot,
        aggregation_snapshot=content.aggregation_snapshot,
        composite_snapshot=content.composite_snapshot,
        manifest_hash=content.manifest_hash,
    )


__all__ = ["get_or_create_manifest_for_call_run"]
