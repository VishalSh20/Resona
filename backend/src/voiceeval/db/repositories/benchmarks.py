"""Benchmark, benchmark-version and benchmark-case persistence."""

from __future__ import annotations

from sqlalchemy import select

from voiceeval.core.clocks import utc_now
from voiceeval.core.errors import ImmutableResourceError
from voiceeval.core.ids import EntityKind, new_id, new_plain_ulid
from voiceeval.db.guards import ensure_benchmark_version_mutable
from voiceeval.db.models import domain
from voiceeval.db.repositories.base import Repository
from voiceeval.domain.enums import BenchmarkStatus


class BenchmarkRepository(Repository):
    async def create_benchmark(
        self, benchmark_key: str, name: str
    ) -> domain.Benchmark:
        benchmark = domain.Benchmark(
            id=new_id(EntityKind.BENCHMARK), benchmark_key=benchmark_key, name=name
        )
        self._session.add(benchmark)
        await self._session.flush()
        return benchmark

    async def get_benchmark(self, benchmark_id: str) -> domain.Benchmark:
        return await self._get(domain.Benchmark, benchmark_id, name="benchmark")

    async def list_benchmarks(self) -> list[domain.Benchmark]:
        result = await self._session.execute(select(domain.Benchmark))
        return list(result.scalars().all())

    async def create_version(
        self,
        benchmark_id: str,
        version: str,
        *,
        manifest: dict | None = None,
        manifest_hash: str | None = None,
    ) -> domain.BenchmarkVersion:
        await self.get_benchmark(benchmark_id)
        bv = domain.BenchmarkVersion(
            id=new_id(EntityKind.BENCHMARK_VERSION),
            benchmark_id=benchmark_id,
            version=version,
            status=BenchmarkStatus.DRAFT.value,
            manifest=manifest,
            manifest_hash=manifest_hash,
        )
        self._session.add(bv)
        await self._session.flush()
        return bv

    async def get_version(self, version_id: str) -> domain.BenchmarkVersion:
        return await self._get(
            domain.BenchmarkVersion, version_id, name="benchmark version"
        )

    async def list_versions(self, benchmark_id: str) -> list[domain.BenchmarkVersion]:
        result = await self._session.execute(
            select(domain.BenchmarkVersion).where(
                domain.BenchmarkVersion.benchmark_id == benchmark_id
            )
        )
        return list(result.scalars().all())

    async def freeze_version(self, version: domain.BenchmarkVersion) -> domain.BenchmarkVersion:
        """Freeze a draft benchmark version; frozen versions become immutable."""
        if version.status != BenchmarkStatus.DRAFT.value:
            raise ImmutableResourceError(
                f"only a draft benchmark version can be frozen (was {version.status})"
            )
        version.status = BenchmarkStatus.FROZEN.value
        version.frozen_at = utc_now()
        await self._session.flush()
        return version

    async def add_case(
        self,
        benchmark_version_id: str,
        *,
        case_key: str,
        case_definition: dict,
        sequence_no: int,
    ) -> domain.BenchmarkCase:
        version = await self.get_version(benchmark_version_id)
        ensure_benchmark_version_mutable(version)
        case = domain.BenchmarkCase(
            id=new_plain_ulid(),
            benchmark_version_id=benchmark_version_id,
            case_key=case_key,
            case_definition=case_definition,
            sequence_no=sequence_no,
        )
        self._session.add(case)
        await self._session.flush()
        return case

    async def list_cases(self, benchmark_version_id: str) -> list[domain.BenchmarkCase]:
        result = await self._session.execute(
            select(domain.BenchmarkCase)
            .where(domain.BenchmarkCase.benchmark_version_id == benchmark_version_id)
            .order_by(domain.BenchmarkCase.sequence_no)
        )
        return list(result.scalars().all())
