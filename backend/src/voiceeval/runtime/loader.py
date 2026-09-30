"""Resolve a prepared attempt into its runtime inputs (v0.4 domain).

Everything the runner/caller needs is resolved from the immutable execution
manifest plus the referenced ``RunEvaluator``. The manifest is the execution
truth, so the runner never re-reads mutable configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from voiceeval.core.errors import ResourceNotFoundError, ValidationError
from voiceeval.db.models import domain
from voiceeval.db.models import runtime as runtime_models
from voiceeval.db.repositories import CallAttemptRepository, RunEvaluatorRepository
from voiceeval.db.repositories.media import MediaArtifactRepository
from voiceeval.runtime.adapters.registry import get_adapter_registry
from voiceeval.runtime.caller.actions import DEFAULT_ACTIONS
from voiceeval.runtime.caller.persona import PersonaProfile, PersonaResolver
from voiceeval.runtime.languages import normalize_bcp47
from voiceeval.runtime.media.recorder import MediaArtifactRecord
from voiceeval.runtime.runner import CallRunner, RunOutcome
from voiceeval.runtime.scenario import Scenario, parse_scenario
from voiceeval.runtime.telemetry import TelemetrySink
from voiceeval.storage import get_object_store


@dataclass(frozen=True)
class AttemptBundle:
    """Everything resolved for one attempt, independent of the runner backend."""

    attempt_id: str
    manifest: domain.ExecutionManifest
    run_evaluator: domain.RunEvaluator
    call_run: runtime_models.CallRun
    target_revision: domain.AgentTargetRevision | None
    scenario: Scenario
    persona: PersonaProfile
    seed: str | None
    target_link: dict[str, Any]


def build_scenario_from_run_evaluator(evaluator: domain.RunEvaluator) -> Scenario:
    """Construct the caller ``Scenario`` from a v0.4 ``RunEvaluator``.

    When the evaluator carries a structured ``scenario_config`` (canonical
    ``evaluator.v1`` shape) it is used directly so the caller knows the
    objective, the facts it may reveal and the allowed actions. Otherwise it
    falls back to the rendered scenario text with the language/personality
    selection and the default action set.
    """
    config = evaluator.scenario_config or {}
    if config:
        scenario = parse_scenario(config)
        # Fill language/persona from the evaluator selection when the structured
        # config did not specify them.
        languages = evaluator.languages or {}
        if not scenario.language:
            scenario = Scenario(
                objective=scenario.objective,
                facts=scenario.facts,
                initial_state=scenario.initial_state,
                assertions=scenario.assertions,
                allowed_actions=scenario.allowed_actions,
                max_recovery_attempts=scenario.max_recovery_attempts,
                stop_conditions=scenario.stop_conditions,
                language={
                    "primary": normalize_bcp47(languages.get("major")),
                    "secondary": (
                        normalize_bcp47(languages.get("minor"))
                        if languages.get("minor")
                        else None
                    ),
                    "code_switch": bool(languages.get("minor")),
                },
                persona=scenario.persona
                or {"traits": list(evaluator.personality or [])},
            )
        return scenario

    languages = evaluator.languages or {}
    primary = normalize_bcp47(languages.get("major"))
    secondary = (
        normalize_bcp47(languages.get("minor")) if languages.get("minor") else None
    )
    return Scenario(
        objective=evaluator.scenario,
        facts={},
        initial_state={},
        assertions=[],
        allowed_actions=list(DEFAULT_ACTIONS),
        max_recovery_attempts=2,
        stop_conditions={},
        language={
            "primary": primary,
            "secondary": secondary,
            "code_switch": bool(secondary),
        },
        persona={"traits": list(evaluator.personality or [])},
    )


def resolve_persona(
    evaluator: domain.RunEvaluator,
    *,
    manifest_profile: dict[str, Any] | None = None,
    seed: str | None = None,
) -> PersonaProfile:
    """Resolve the persona, preferring the manifest snapshot for reproducibility."""
    if manifest_profile:
        return PersonaProfile.from_dict(manifest_profile)
    languages = evaluator.languages or {}
    return PersonaResolver().resolve(
        list(evaluator.personality or []),
        language={
            "primary": normalize_bcp47(languages.get("major")),
            "secondary": (
                normalize_bcp47(languages.get("minor"))
                if languages.get("minor")
                else None
            ),
        },
    )


async def load_attempt_context(session: AsyncSession, attempt_id: str) -> AttemptBundle:
    attempt = await CallAttemptRepository(session).get_attempt(attempt_id)
    manifest = await session.get(domain.ExecutionManifest, attempt.execution_manifest_id)
    if manifest is None:
        raise ResourceNotFoundError(
            f"execution manifest '{attempt.execution_manifest_id}' not found"
        )

    call_run = await session.get(runtime_models.CallRun, attempt.call_run_id)
    if call_run is None:
        raise ResourceNotFoundError(f"call run '{attempt.call_run_id}' not found")

    evaluator = await RunEvaluatorRepository(session).get_evaluator(
        call_run.run_evaluator_id
    )

    target_revision = None
    run = await session.get(domain.Run, call_run.run_id)
    if run is not None and run.target_revision_id:
        target_revision = await session.get(
            domain.AgentTargetRevision, run.target_revision_id
        )

    caller_snapshot: dict[str, Any] = manifest.caller_snapshot or {}
    target_snapshot: dict[str, Any] = manifest.target_snapshot or {}
    target_link = dict(target_snapshot.get("target_link") or {})
    scenario = build_scenario_from_run_evaluator(evaluator)
    persona = resolve_persona(
        evaluator,
        manifest_profile=caller_snapshot.get("persona_profile"),
        seed=caller_snapshot.get("seed"),
    )

    return AttemptBundle(
        attempt_id=attempt_id,
        manifest=manifest,
        run_evaluator=evaluator,
        call_run=call_run,
        target_revision=target_revision,
        scenario=scenario,
        persona=persona,
        seed=caller_snapshot.get("seed") or call_run.run_seed,
        target_link=target_link,
    )


def _resolve_adapter_path(target_link: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Return ``(adapter_name, adapter_version, endpoint_config)`` for legacy runners.

    LiveKit transports (room/sip/bridge) are served by the LiveKit dispatcher, not
    the adapter registry.
    """
    transport = target_link.get("transport")
    if transport in ("room", "sip", "bridge") and not target_link.get("adapter_name"):
        raise ValidationError(
            f"target link '{transport}' is served by the LiveKit dispatcher; "
            "use runner_dispatch_mode='livekit'"
        )
    return (
        str(target_link.get("adapter_name") or "fake"),
        str(target_link.get("adapter_version") or "1.0.0"),
        dict(target_link.get("endpoint_config") or {}),
    )


async def build_runner_for_attempt(
    session: AsyncSession,
    attempt_id: str,
    *,
    telemetry: TelemetrySink,
    runner_id: str | None = None,
) -> CallRunner:
    """Resolve a prepared attempt into a runnable (legacy adapter) CallRunner."""
    bundle = await load_attempt_context(session, attempt_id)

    adapter_name, adapter_version, endpoint_config = _resolve_adapter_path(
        bundle.target_link
    )
    adapter = get_adapter_registry().create(adapter_name, adapter_version)
    scenario = bundle.scenario

    media_repo = MediaArtifactRepository(session)

    async def media_sink(record: MediaArtifactRecord) -> None:
        object_uri = None
        if record.data:
            key = (
                f"media/{attempt_id}/{record.track}-{record.representation}-"
                f"{record.sha256[:12]}.pcm"
            )
            object_uri = get_object_store().put(
                key, record.data, content_type="audio/L16"
            )
        await media_repo.record_artifact(attempt_id, record, object_uri=object_uri)
        await session.commit()

    return CallRunner(
        attempt_id=attempt_id,
        adapter=adapter,
        endpoint_config=endpoint_config,
        scenario=scenario,
        telemetry=telemetry,
        runner_id=runner_id or f"runner-{attempt_id}",
        media_sink=media_sink,
    )


__all__ = [
    "AttemptBundle",
    "RunOutcome",
    "build_runner_for_attempt",
    "build_scenario_from_run_evaluator",
    "load_attempt_context",
    "resolve_persona",
]
