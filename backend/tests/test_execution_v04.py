"""v0.4 run-centric execution path: structural invariants.

Full DB-backed execution is exercised in CI against Postgres; these lock the
renamed columns, repository/orchestrator surface and deterministic seed so a
regression in the plan→run migration fails loudly without a database.
"""

from __future__ import annotations

import inspect

from voiceeval.aggregation.engine import AggregationEngine
from voiceeval.db.models import results, runtime
from voiceeval.db.repositories import CallRunRepository
from voiceeval.orchestration.executor import ExecutionOrchestrator
from voiceeval.orchestration.retry import derive_run_seed


def test_call_run_and_result_tables_use_v04_columns():
    call_run_cols = runtime.CallRun.__table__.columns
    assert {"run_id", "run_evaluator_id", "repetition_no", "run_seed"} <= set(
        call_run_cols.keys()
    )
    aggregate_cols = results.AggregateResult.__table__.columns
    assert {"run_id", "run_evaluator_id", "scope"} <= set(aggregate_cols.keys())
    composite_cols = results.CompositeScoreResult.__table__.columns
    assert "run_id" in composite_cols
    assert "evaluation_plan_id" not in aggregate_cols
    assert "evaluation_plan_id" not in composite_cols


def test_call_run_repository_is_run_based():
    params = inspect.signature(CallRunRepository.create_run).parameters
    assert {"run_id", "run_evaluator_id", "repetition_no", "run_seed"} <= set(params)
    assert "evaluation_plan_id" not in params


def test_orchestrator_exposes_run_lifecycle():
    for name in (
        "begin_run",
        "ensure_call_runs",
        "start_call_run",
        "start_attempt",
        "record_attempt_terminal",
        "retry_call_run",
        "cancel_run",
        "resume_run",
    ):
        assert hasattr(ExecutionOrchestrator, name)
    assert "max_attempts_per_run" in inspect.signature(ExecutionOrchestrator).parameters


def test_aggregation_engine_is_run_based():
    for name in (
        "is_run_evaluation_complete",
        "aggregate_run",
        "compute_composite",
    ):
        assert hasattr(AggregationEngine, name)
    assert not hasattr(AggregationEngine, "aggregate_plan")


def test_derive_run_seed_is_deterministic_and_identity_sensitive():
    a = derive_run_seed("run_1", "runeval_1", 1)
    assert a == derive_run_seed("run_1", "runeval_1", 1)
    assert a != derive_run_seed("run_1", "runeval_1", 2)
    assert a != derive_run_seed("run_2", "runeval_1", 1)


def test_enqueue_helpers_reference_run_jobs():
    import voiceeval.workers.enqueue as enqueue

    source = inspect.getsource(enqueue)
    assert "execution_run_start" in source
    assert "execution_call_run_start" in source
    assert "compute_call_run_judges" in source
    assert "compute_run_aggregation" in source
    assert "execution_plan_start" not in source
    assert "compute_plan_aggregation" not in source
