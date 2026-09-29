"""Domain model registration and constraint tests (pure metadata, no DB)."""

from __future__ import annotations

from voiceeval.db.base import Base


def _table(name: str):
    return Base.metadata.tables[name]


def _constraint_names(table):
    return {c.name for c in table.constraints if c.name is not None}


DOMAIN_TABLES = {
    "integration_provider",
    "integration_account",
    "integration_secret",
    "transport_type",
    "agent_target",
    "agent_target_revision",
    "agent_endpoint",
    "connection_session",
    "simulation",
    "run",
    "run_evaluator",
    "validation_report",
    "benchmark",
    "benchmark_version",
    "benchmark_case",
    "execution_manifest",
    "call_run",
    "call_attempt",
    "call_turn",
    "runtime_event",
    "tool_call",
    "state_transition",
    "media_artifact",
    "metric_definition",
    "judge_definition",
    "judge_execution",
    "metric_result",
    "evidence",
    "aggregate_result",
    "composite_score_definition",
    "composite_score_result",
}

SUPPORT_TABLES = {"users", "user_roles", "idempotency_keys", "jobs"}

# Concepts removed by the v0.4 migration: no evaluator/evaluator-revision/
# evaluation-plan chain may reappear.
REMOVED_TABLES = {
    "test_descriptor",
    "test_descriptor_revision",
    "evaluator",
    "evaluator_revision",
    "evaluation_plan",
    "evaluation_plan_item",
}


def test_all_domain_tables_registered():
    registered = set(Base.metadata.tables)
    assert DOMAIN_TABLES <= registered


def test_all_support_tables_registered():
    registered = set(Base.metadata.tables)
    assert SUPPORT_TABLES <= registered


def test_removed_v03_tables_absent():
    registered = set(Base.metadata.tables)
    assert REMOVED_TABLES.isdisjoint(registered)


def test_required_unique_constraints_present():
    expected = {
        "agent_target": {"uq_agent_target_account_external_id"},
        "agent_target_revision": {
            "uq_target_rev_no",
            "uq_target_rev_config_hash",
            "uq_target_rev_provider",
        },
        "integration_secret": {"uq_integration_secret_account_key"},
        "run_evaluator": {"uq_run_evaluator_seq"},
        "call_run": {"uq_call_run_repetition"},
        "call_attempt": {"uq_call_attempt_no"},
        "runtime_event": {"uq_runtime_event_seq", "uq_runtime_event_provider"},
    }
    for table_name, constraint_names in expected.items():
        names = _constraint_names(_table(table_name))
        assert constraint_names <= names, f"{table_name} missing {constraint_names - names}"


def test_metric_result_value_representation_check_present():
    names = _constraint_names(_table("metric_result"))
    assert "ck_metric_result_value_representation" in names


def test_run_status_and_evaluator_count_checks_present():
    names = _constraint_names(_table("run"))
    assert "ck_run_status" in names
    assert "ck_run_evaluator_count" in names


def test_simulation_evaluator_count_check_present():
    names = _constraint_names(_table("simulation"))
    assert "ck_simulation_evaluator_count" in names


def test_runtime_event_sequence_no_is_bigint():
    column = _table("runtime_event").c["sequence_no"]
    assert str(column.type).lower() == "bigint"


def test_metric_result_has_typed_value_columns():
    table = _table("metric_result")
    for column in ("value_numeric", "value_boolean", "value_text", "value_category"):
        assert column in table.c
