"""v0.4 manifest builder and RunEvaluator→Scenario mapping (Blocker B)."""

from __future__ import annotations

from types import SimpleNamespace

from voiceeval.core.config import get_settings
from voiceeval.runtime.caller.actions import DEFAULT_ACTIONS
from voiceeval.runtime.loader import build_scenario_from_run_evaluator
from voiceeval.runtime.scenario import Scenario


def _revision():
    return SimpleNamespace(
        id="rev_1",
        agent_target_id="tgt_1",
        revision_no=1,
        provider_revision_id="prov_rev_1",
        canonical_config={"first_message": "Hi"},
        source_config={"raw": True},
        config_hash="hash123",
        source_kind="IMPORTED",
    )


def _evaluator(scenario_config=None):
    return SimpleNamespace(
        id="ev_1",
        sequence_no=1,
        scenario="Caller needs help resetting a password.",
        scenario_config=scenario_config or {},
        expected_output_prompt="Agent resolves the reset.",
        metrics=["relevancy"],
        languages={"major": "hi-IN", "minor": "en-IN"},
        personality=["CONFUSED", "HESITANT"],
    )


def test_manifest_content_v04_shape():
    from voiceeval.orchestration.manifest import (
        MANIFEST_SCHEMA_VERSION,
        build_manifest_content,
        compute_manifest_hash,
    )

    content = build_manifest_content(
        target_revision=_revision(),
        run_evaluators=[_evaluator()],
        simulation=SimpleNamespace(
            id="sim_1",
            name="Support",
            agent_target_id="tgt_1",
            languages=["hi-IN", "en-IN"],
            call_ambience=["QUIET"],
            metric_set=["relevancy"],
            personalities=["CONFUSED", "HESITANT"],
            evaluator_count=1,
        ),
        run=SimpleNamespace(
            id="run_1",
            simulation_id="sim_1",
            target_revision_id="rev_1",
            evaluator_count=1,
            status="ready",
        ),
        target_link={
            "transport": "sip",
            "endpoint_config": {"to_number": "+15551234567"},
        },
        caller_persona={"version": "persona.v1", "traits": ["CONFUSED"]},
        seed="seed-42",
        settings=get_settings(),
    )

    assert content.schema_version == MANIFEST_SCHEMA_VERSION
    assert content.target_snapshot["target_link"]["transport"] == "sip"
    assert content.caller_snapshot["seed"] == "seed-42"
    assert content.caller_snapshot["persona_profile"]["version"] == "persona.v1"
    assert content.evaluator_snapshot["ev_1"]["personality"] == ["CONFUSED", "HESITANT"]
    assert content.simulation_snapshot["id"] == "sim_1"
    assert content.run_snapshot["id"] == "run_1"

    # Deterministic: recomputing the hash over the same content matches.
    recomputed = compute_manifest_hash(
        {
            "schema_version": content.schema_version,
            "target_snapshot": content.target_snapshot,
            "simulation_snapshot": content.simulation_snapshot,
            "run_snapshot": content.run_snapshot,
            "evaluator_snapshot": content.evaluator_snapshot,
            "benchmark_snapshot": content.benchmark_snapshot,
            "caller_snapshot": content.caller_snapshot,
            "metric_snapshot": content.metric_snapshot,
            "judge_snapshot": content.judge_snapshot,
            "aggregation_snapshot": content.aggregation_snapshot,
            "composite_snapshot": content.composite_snapshot,
        }
    )
    assert recomputed == content.manifest_hash


def test_manifest_defaults_target_link_to_room():
    from voiceeval.orchestration.manifest import build_manifest_content

    content = build_manifest_content(
        target_revision=_revision(),
        run_evaluators=[_evaluator()],
        settings=get_settings(),
    )
    assert content.target_snapshot["target_link"]["transport"] == "room"


def test_scenario_is_built_from_run_evaluator():
    scenario = build_scenario_from_run_evaluator(_evaluator())
    assert isinstance(scenario, Scenario)
    assert scenario.objective.startswith("Caller needs help")
    assert scenario.language["primary"] == "hi-IN"
    assert scenario.language["secondary"] == "en-IN"
    assert scenario.language["code_switch"] is True
    assert scenario.persona["traits"] == ["CONFUSED", "HESITANT"]
    assert scenario.allowed_actions == list(DEFAULT_ACTIONS)


def test_scenario_uses_structured_config_facts_when_present():
    config = {
        "motive": {
            "objective": "Reset my password",
            "assertions": [{"id": "auth", "type": "state", "required": True}],
        },
        "facts": [{"id": "account_id", "value": "AC-9"}],
        "behaviour": {"allowed_actions": ["present_problem", "provide_information"]},
        "language": {"primary": "en-IN"},
    }
    scenario = build_scenario_from_run_evaluator(_evaluator(config))
    assert scenario.objective == "Reset my password"
    assert scenario.facts == {"account_id": "AC-9"}
    assert scenario.allowed_actions == ["present_problem", "provide_information"]
    assert [a.id for a in scenario.required_assertions] == ["auth"]
