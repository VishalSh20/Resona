"""API router aggregation.

Mounts the v0.4 configuration surface (targets, simulations, runs, run
evaluators, benchmarks) and the AI generation endpoints under ``/api/v1``.
Every control-plane route requires a user JWT except the signed media-blob
endpoint, which is mounted separately.

The previous v0.3 evaluator/plan/test-descriptor/result routes were removed with
the v0.4 domain migration (the ``evaluator``/``evaluator_revision``/
``evaluation_plan`` chain no longer exists).
"""

from __future__ import annotations

from fastapi import APIRouter

from voiceeval.api.routes import (
    auth,
    benchmarks,
    generation,
    integrations,
    results,
    run_evaluators,
    simulations,
    targets,
)

api_router = APIRouter(prefix="/api/v1")

# Unauthenticated: register/login mint a user JWT; me requires one.
api_router.include_router(auth.router)
api_router.include_router(integrations.router)
api_router.include_router(targets.router)
api_router.include_router(simulations.router)
api_router.include_router(run_evaluators.router)
api_router.include_router(benchmarks.router)
api_router.include_router(benchmarks.version_router)
api_router.include_router(generation.router)
# Read-only results/forensics surfaces + the signed media-blob endpoint. The
# blob router is deliberately unauthenticated (its authorisation is the
# signature + expiry); it must not inherit the results router's user JWT.
api_router.include_router(results.router)
api_router.include_router(results.blob_router)
