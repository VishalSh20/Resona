"""Immutable execution-manifest construction (v0.4 domain).

The manifest is the execution truth: a self-contained snapshot of everything a
CallAttempt needs to reproduce a call (target/link, simulation, run, run
evaluators, caller persona + seed, metric/judge/aggregation definitions and
runtime versions), plus a deterministic ``manifest_hash``. Once written it is
never mutated.

This mirrors the v0.4 schema: ``RunEvaluator`` replaces the removed
``EvaluatorRevision`` chain, and the target endpoint/link is carried explicitly
so the runtime no longer has to re-derive it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from voiceeval.core.config import Settings
from voiceeval.db.models import domain

MANIFEST_SCHEMA_VERSION = "manifest.v1"

# v1 runtime identifiers. These become configuration-driven in the prompts that
# implement the caller (TTS/ASR/LLM) and the runner/adapter runtimes.
RUNNER_VERSION = "runner.v1"
CALLER_POLICY_VERSION = "controlled_variation.v1"
AGGREGATION_VERSION = "aggregation.v1"
COMPOSITE_VERSION = "composite.v1"


@dataclass(frozen=True)
class ManifestContent:
    schema_version: str
    target_snapshot: dict[str, Any]
    simulation_snapshot: dict[str, Any]
    run_snapshot: dict[str, Any]
    evaluator_snapshot: dict[str, Any]
    benchmark_snapshot: dict[str, Any] | None
    caller_snapshot: dict[str, Any]
    metric_snapshot: dict[str, Any]
    judge_snapshot: dict[str, Any]
    aggregation_snapshot: dict[str, Any]
    composite_snapshot: dict[str, Any]
    manifest_hash: str


def compute_manifest_hash(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _target_snapshot(
    revision: domain.AgentTargetRevision,
    target_link: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": revision.id,
        "agent_target_id": revision.agent_target_id,
        "revision_no": revision.revision_no,
        "provider_revision_id": revision.provider_revision_id,
        "canonical_config": revision.canonical_config,
        "source_config": revision.source_config,
        "config_hash": revision.config_hash,
        "source_kind": revision.source_kind,
        # Resolved transport for the caller migration (§4.2). Defaults to a
        # LiveKit room when not otherwise specified.
        "target_link": target_link
        or {"transport": "room", "endpoint_config": {}},
    }


def _simulation_snapshot(simulation: domain.Simulation | None) -> dict[str, Any]:
    if simulation is None:
        return {}
    return {
        "id": simulation.id,
        "name": simulation.name,
        "agent_target_id": simulation.agent_target_id,
        "languages": list(simulation.languages or []),
        "call_ambience": list(simulation.call_ambience or []),
        "metric_set": list(simulation.metric_set or []),
        "personalities": list(simulation.personalities or []),
        "evaluator_count": simulation.evaluator_count,
    }


def _run_snapshot(run: domain.Run | None) -> dict[str, Any]:
    if run is None:
        return {}
    return {
        "id": run.id,
        "simulation_id": run.simulation_id,
        "target_revision_id": run.target_revision_id,
        "evaluator_count": run.evaluator_count,
        "status": run.status,
    }


def _evaluator_snapshot(run_evaluators: list[domain.RunEvaluator]) -> dict[str, Any]:
    return {
        evaluator.id: {
            "id": evaluator.id,
            "sequence_no": evaluator.sequence_no,
            "scenario": evaluator.scenario,
            "expected_output_prompt": evaluator.expected_output_prompt,
            "metrics": list(evaluator.metrics or []),
            "languages": evaluator.languages,
            "personality": list(evaluator.personality or []),
        }
        for evaluator in run_evaluators
    }


def _benchmark_snapshot(
    version: domain.BenchmarkVersion | None,
) -> dict[str, Any] | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "benchmark_id": version.benchmark_id,
        "version": version.version,
        "status": version.status,
        "manifest_hash": version.manifest_hash,
        "frozen_at": version.frozen_at.isoformat() if version.frozen_at else None,
    }


def _caller_snapshot(
    settings: Settings,
    *,
    persona_profile: dict[str, Any] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    return {
        "policy_version": CALLER_POLICY_VERSION,
        "runtime_versions": {
            "runner_version": RUNNER_VERSION,
            "caller_policy_version": CALLER_POLICY_VERSION,
            "tts_model": None,
            "asr_model": None,
            "llm_model": settings.openrouter_model,
        },
        # The resolved persona profile and per-attempt seed are snapshotted so a
        # call is reproducible and explainable (§7, §8.7).
        "persona_profile": dict(persona_profile or {}),
        "seed": seed,
        "timeouts": {
            "conversation_stall_ms": settings.conversation_stall_ms,
            "wall_clock_timeout_ms": settings.wall_clock_timeout_ms,
            "max_wall_clock_timeout_ms": settings.max_wall_clock_timeout_ms,
        },
    }


def _metric_snapshot(negotiation: dict[str, Any]) -> dict[str, Any]:
    return {
        "metrics": negotiation.get("metrics", {}),
        "unavailable_metrics": negotiation.get("unavailable_metrics", []),
        "warnings": negotiation.get("warnings", []),
    }


def _judge_snapshot(judge_definitions: list[Any]) -> dict[str, Any]:
    return {
        "judges": {
            definition.judge_key: {
                "id": definition.id,
                "version": definition.version,
                "kind": definition.kind,
                "provider": definition.provider,
                "model": definition.model,
            }
            for definition in judge_definitions
        }
    }


def build_manifest_content(
    *,
    target_revision: domain.AgentTargetRevision,
    run_evaluators: list[domain.RunEvaluator],
    simulation: domain.Simulation | None = None,
    run: domain.Run | None = None,
    target_link: dict[str, Any] | None = None,
    caller_persona: dict[str, Any] | None = None,
    seed: str | None = None,
    negotiation: dict[str, Any] | None = None,
    benchmark_version: domain.BenchmarkVersion | None = None,
    judge_definitions: list[Any] | None = None,
    settings: Settings,
) -> ManifestContent:
    """Serialize the execution truth into an immutable manifest content."""
    target_snapshot = _target_snapshot(target_revision, target_link)
    simulation_snapshot = _simulation_snapshot(simulation)
    run_snapshot = _run_snapshot(run)
    evaluator_snapshot = _evaluator_snapshot(run_evaluators)
    benchmark_snapshot = _benchmark_snapshot(benchmark_version)
    caller_snapshot = _caller_snapshot(settings, persona_profile=caller_persona, seed=seed)
    metric_snapshot = _metric_snapshot(negotiation or {})
    judge_snapshot = _judge_snapshot(judge_definitions or [])
    aggregation_snapshot = {"version": AGGREGATION_VERSION}
    composite_snapshot = {"version": COMPOSITE_VERSION}

    manifest_hash = compute_manifest_hash(
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "target_snapshot": target_snapshot,
            "simulation_snapshot": simulation_snapshot,
            "run_snapshot": run_snapshot,
            "evaluator_snapshot": evaluator_snapshot,
            "benchmark_snapshot": benchmark_snapshot,
            "caller_snapshot": caller_snapshot,
            "metric_snapshot": metric_snapshot,
            "judge_snapshot": judge_snapshot,
            "aggregation_snapshot": aggregation_snapshot,
            "composite_snapshot": composite_snapshot,
        }
    )

    return ManifestContent(
        schema_version=MANIFEST_SCHEMA_VERSION,
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


__all__ = [
    "CALLER_POLICY_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "ManifestContent",
    "build_manifest_content",
    "compute_manifest_hash",
]
