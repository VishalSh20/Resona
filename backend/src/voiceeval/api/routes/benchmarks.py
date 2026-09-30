"""Benchmark configuration API."""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.dependencies import (
    IdempotencyKeyDep,
    SessionDep,
    require_user_dep,
)
from voiceeval.schemas.benchmarks import (
    BenchmarkCreate,
    BenchmarkRead,
    BenchmarkVersionCreate,
    BenchmarkVersionRead,
)
from voiceeval.services.benchmarks import BenchmarkService
from voiceeval.services.idempotency import IdempotencyService, hash_request

router = APIRouter(
    prefix="/benchmarks", tags=["benchmarks"], dependencies=[require_user_dep]
)
version_router = APIRouter(
    prefix="/benchmark-versions",
    tags=["benchmarks"],
    dependencies=[require_user_dep],
)


@router.post("", response_model=BenchmarkRead, status_code=201)
async def create_benchmark(
    payload: BenchmarkCreate, session: SessionDep
) -> BenchmarkRead:
    service = BenchmarkService(session)
    benchmark = await service.create_benchmark(payload.benchmark_key, payload.name)
    await session.commit()
    return BenchmarkRead.model_validate(benchmark)


@router.get("", response_model=list[BenchmarkRead])
async def list_benchmarks(session: SessionDep) -> list[BenchmarkRead]:
    service = BenchmarkService(session)
    return [BenchmarkRead.model_validate(b) for b in await service.list_benchmarks()]


@router.get("/{benchmark_id}", response_model=BenchmarkRead)
async def get_benchmark(benchmark_id: str, session: SessionDep) -> BenchmarkRead:
    service = BenchmarkService(session)
    return BenchmarkRead.model_validate(await service.get_benchmark(benchmark_id))


@router.post(
    "/{benchmark_id}/versions", response_model=BenchmarkVersionRead, status_code=201
)
async def create_version(
    benchmark_id: str,
    payload: BenchmarkVersionCreate,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> BenchmarkVersionRead:
    await IdempotencyService(session).reserve(
        idempotency_key,
        "benchmark:version",
        request_hash=hash_request(payload.model_dump(mode="json")),
    )
    service = BenchmarkService(session)
    version = await service.create_version(
        benchmark_id,
        payload.version,
        manifest=payload.manifest,
        manifest_hash=payload.manifest_hash,
    )
    await session.commit()
    return BenchmarkVersionRead.model_validate(version)


@router.get("/{benchmark_id}/versions", response_model=list[BenchmarkVersionRead])
async def list_versions(
    benchmark_id: str, session: SessionDep
) -> list[BenchmarkVersionRead]:
    service = BenchmarkService(session)
    return [
        BenchmarkVersionRead.model_validate(v)
        for v in await service.list_versions(benchmark_id)
    ]


@version_router.get("/{version_id}", response_model=BenchmarkVersionRead)
async def get_version(version_id: str, session: SessionDep) -> BenchmarkVersionRead:
    service = BenchmarkService(session)
    return BenchmarkVersionRead.model_validate(await service.get_version(version_id))


@version_router.post("/{version_id}/freeze", response_model=BenchmarkVersionRead)
async def freeze_version(
    version_id: str,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep,
) -> BenchmarkVersionRead:
    await IdempotencyService(session).reserve(idempotency_key, "benchmark:freeze")
    service = BenchmarkService(session)
    version = await service.freeze_version(version_id)
    await session.commit()
    return BenchmarkVersionRead.model_validate(version)
