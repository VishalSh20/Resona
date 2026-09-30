"""Benchmark and benchmark-version domain operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.db.models import domain
from voiceeval.db.repositories import BenchmarkRepository


# RunEvaluator-compatible case fields persisted on ``benchmark_case.case_definition``.
_CASE_DEFINITION_FIELDS = (
    "scenario",
    "expected_output_prompt",
    "metrics",
    "languages",
    "personality",
)

_CASE_DEFINITION_CAMEL = {
    "expectedOutputPrompt": "expected_output_prompt",
}


def _coerce_case_definition(item: dict[str, Any]) -> dict[str, Any] | None:
    """Return the immutable case definition for one manifest case entry.

    Accepts either an explicit ``case_definition``/``caseDefinition`` object or
    the RunEvaluator-compatible fields inline. Returns ``None`` when the entry
    carries no usable definition.
    """
    raw = item.get("case_definition") or item.get("caseDefinition")
    if isinstance(raw, dict) and raw:
        return raw
    definition: dict[str, Any] = {
        field: item[field] for field in _CASE_DEFINITION_FIELDS if field in item
    }
    for camel, snake in _CASE_DEFINITION_CAMEL.items():
        if camel in item and snake not in definition:
            definition[snake] = item[camel]
    return definition or None


def parse_manifest_cases(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract benchmark cases from a version manifest's ``cases`` array.

    A version's manifest is the client-supplied definition of its case list; the
    cases are materialized as rows so preparation can resolve concrete
    RunEvaluator-compatible case definitions in sequence order.
    """
    if not isinstance(manifest, dict):
        return []
    raw = manifest.get("cases")
    if not isinstance(raw, list):
        return []
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        case_definition = _coerce_case_definition(item)
        if not case_definition:
            continue
        sequence_no = item.get("sequence_no") or item.get("sequenceNo")
        cases.append(
            {
                "case_key": str(
                    item.get("case_key") or item.get("caseKey") or f"case_{index + 1}"
                ),
                "case_definition": case_definition,
                "sequence_no": int(sequence_no) if sequence_no else index + 1,
            }
        )
    return cases


class BenchmarkService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._benchmarks = BenchmarkRepository(session)

    async def create_benchmark(
        self, benchmark_key: str, name: str
    ) -> domain.Benchmark:
        return await self._benchmarks.create_benchmark(benchmark_key, name)

    async def get_benchmark(self, benchmark_id: str) -> domain.Benchmark:
        return await self._benchmarks.get_benchmark(benchmark_id)

    async def list_benchmarks(self) -> list[domain.Benchmark]:
        return await self._benchmarks.list_benchmarks()

    async def create_version(
        self,
        benchmark_id: str,
        version: str,
        *,
        manifest: dict[str, Any] | None = None,
        manifest_hash: str | None = None,
    ) -> domain.BenchmarkVersion:
        version_row = await self._benchmarks.create_version(
            benchmark_id,
            version,
            manifest=manifest,
            manifest_hash=manifest_hash,
        )
        # Materialize the manifest's cases so a benchmark plan can resolve its
        # evaluator revisions at preparation time.
        for case in parse_manifest_cases(manifest):
            await self._benchmarks.add_case(version_row.id, **case)
        return version_row

    async def get_version(self, version_id: str) -> domain.BenchmarkVersion:
        return await self._benchmarks.get_version(version_id)

    async def list_versions(
        self, benchmark_id: str
    ) -> list[domain.BenchmarkVersion]:
        return await self._benchmarks.list_versions(benchmark_id)

    async def list_cases(self, version_id: str) -> list[domain.BenchmarkCase]:
        return await self._benchmarks.list_cases(version_id)

    async def freeze_version(self, version_id: str) -> domain.BenchmarkVersion:
        version = await self._benchmarks.get_version(version_id)
        return await self._benchmarks.freeze_version(version)
