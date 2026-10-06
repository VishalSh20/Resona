"""Execution-manifest persistence.

The manifest is content-addressed by ``manifest_hash`` and immutable once
written, so get-or-create by hash is the only write path.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from voiceeval.core.ids import EntityKind, new_id
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository


class ManifestRepository(Repository):
    async def get(self, manifest_id: str) -> domain.ExecutionManifest:
        return await self._get(
            domain.ExecutionManifest, manifest_id, name="execution manifest"
        )

    async def find_by_hash(self, manifest_hash: str) -> domain.ExecutionManifest | None:
        result = await self._session.execute(
            select(domain.ExecutionManifest)
            .where(domain.ExecutionManifest.manifest_hash == manifest_hash)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        schema_version: str,
        target_snapshot: dict[str, Any],
        simulation_snapshot: dict[str, Any],
        run_snapshot: dict[str, Any],
        evaluator_snapshot: dict[str, Any],
        caller_snapshot: dict[str, Any],
        metric_snapshot: dict[str, Any],
        judge_snapshot: dict[str, Any],
        aggregation_snapshot: dict[str, Any],
        composite_snapshot: dict[str, Any],
        manifest_hash: str,
        benchmark_snapshot: dict[str, Any] | None = None,
    ) -> domain.ExecutionManifest:
        manifest = domain.ExecutionManifest(
            id=new_id(EntityKind.MANIFEST),
            schema_version=schema_version,
            target_snapshot=target_snapshot,
            simulation_snapshot=simulation_snapshot,
            run_snapshot=run_snapshot,
            evaluator_snapshot=evaluator_snapshot,
            benchmark_snapshot=benchmark_snapshot,
            caller_snapshot=caller_snapshot,
            metric_snapshot=metric_snapshot,
            judge_snapshot=judge_snapshot,
            aggregation_snapshot=aggregation_snapshot,
            composite_snapshot=composite_snapshot,
            manifest_hash=manifest_hash,
        )
        self._session.add(manifest)
        await self._session.flush()
        return manifest


__all__ = ["ManifestRepository"]
