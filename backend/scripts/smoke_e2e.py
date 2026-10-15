"""End-to-end local smoke test.

Drives the full evaluation lifecycle against live Postgres + Redis using the
deterministic fake target — no third-party provider, no browser:

    target -> revision -> evaluator -> revision -> validate -> approve
           -> plan -> prepare -> execute -> expand runs -> run attempts
           -> runtime events -> metrics -> judge -> aggregation -> composite
           -> forensic retrieval

Run it with the Docker dependencies up and migrations applied:

    docker compose up -d postgres redis
    uv run alembic upgrade head
    uv run python scripts/smoke_e2e.py

This writes real rows. Raw runtime events are append-only (DB trigger), so the
smoke test intentionally does not clean up after itself; each run creates fresh
identities.
"""

from __future__ import annotations

import asyncio
import json
import sys

from voiceeval.aggregation.engine import AggregationEngine
from voiceeval.core.config import get_settings
from voiceeval.core.ids import EntityKind, new_id, new_plain_ulid
from voiceeval.core.logging import configure_logging
from voiceeval.db.models import domain
from voiceeval.db.repositories import CallAttemptRepository, CallRunRepository
from voiceeval.db.session import get_session_factory
from voiceeval.domain.enums import CallRunStatus, EvaluatorStatus, PlanStatus
from voiceeval.judges.engine import JudgeEngine
from voiceeval.judges.llm import StaticLLMProvider
from voiceeval.metrics.engine import MetricEngine
from voiceeval.observability.tracing import init_tracing
from voiceeval.orchestration.completion import PlanCompletionService
from voiceeval.orchestration.executor import ExecutionOrchestrator
from voiceeval.runtime.adapters import FakeTargetServer
from voiceeval.runtime.adapters.fake import FAKE_CAPABILITY_SNAPSHOT
from voiceeval.runtime.dispatch import InlineRunnerDispatcher
from voiceeval.services.evaluators import EvaluatorService
from voiceeval.services.plans import PlanService
from voiceeval.services.results import ForensicsService
from voiceeval.services.targets import TargetService
from voiceeval.workers.jobs.validation import validate_evaluator_revision

JUDGE_OUTPUT = json.dumps(
    {
        "motive_fulfilled": True,
        "semantic_understanding": 4,
        "response_clarity": 4,
        "context_retention": 4,
        "language_adaptation": 4,
        "reason_codes": [],
        "confidence": 0.85,
    }
)


def evaluator_content(tag: str) -> dict:
    """Concrete evaluator document.

    ``tag`` makes the content unique per run: revisions are content-addressed
    (``UNIQUE(content_hash)``), so a re-run with byte-identical content would be
    rejected as a duplicate revision.
    """
    return {
        "schema_version": "evaluator.v1",
        "persona": {"age": 30, "personality": "cooperative"},
        "language": {"primary": "en", "allowed": ["en", "hi"]},
        "motive": {
            "objective": "Get my account issue resolved",
            "assertions": [
                {"id": "authentication_complete", "type": "state", "required": True},
                {"id": "objective_fulfilled", "type": "state", "required": True},
            ],
        },
        "behaviour": {
            "allowed_actions": [
                "present_problem",
                "provide_information",
                "clarify",
                "recover",
                "acknowledge_resolution",
                "end_call",
            ],
            "recovery": {"max_attempts": 2},
        },
        "stop_conditions": {
            "natural_success": True,
            "conversation_stall_ms": 10_000,
            "wall_clock_timeout_ms": 180_000,
        },
        "evaluation_criteria": [
            {"metric": "ttfa", "required": True},
            {"metric": "ttft", "required": True},
            {"metric": "motive_fulfillment", "required": True},
        ],
        "facts": [{"id": "account_id", "value": f"AC-{tag}"}],
        "initial_state": {"authenticated": False},
    }

REPEAT_COUNT = 3


async def _noop_enqueue(*args, **kwargs) -> None:
    return None


def _check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    return ok


async def run() -> int:
    configure_logging()
    init_tracing()
    factory = get_session_factory()
    run_tag = new_plain_ulid()
    results_ok: list[bool] = []

    server = await FakeTargetServer().start()
    print(f"[smoke] fake target listening at {server.url}\n")

    try:
        # --- 1. configuration truth -----------------------------------------
        async with factory() as session:
            target = await TargetService(session).create_target(
                "Smoke Target", provider="fake"
            )
            revision = await TargetService(session).create_revision(
                target.id,
                transport="websocket",
                adapter_name="fake",
                adapter_version="1.0.0",
                endpoint_config={"url": server.url},
                capability_snapshot=FAKE_CAPABILITY_SNAPSHOT,
            )
            # unique keys so the smoke test is re-runnable
            evaluator = await EvaluatorService(session).create_evaluator(
                f"smoke_evaluator_{new_plain_ulid()}", "Smoke Evaluator", "custom"
            )
            eval_revision = await EvaluatorService(session).create_revision(
                evaluator.id, evaluator_content(new_plain_ulid())
            )
            # a custom plan references a test descriptor revision
            descriptor = domain.TestDescriptor(
                id=new_id(EntityKind.TEST_DESCRIPTOR), name="Smoke Descriptor"
            )
            session.add(descriptor)
            await session.flush()
            descriptor_revision = domain.TestDescriptorRevision(
                id=new_id(EntityKind.TEST_DESCRIPTOR_REVISION),
                test_descriptor_id=descriptor.id,
                revision_no=1,
                source_text="smoke test descriptor",
            )
            session.add(descriptor_revision)
            await session.commit()
            target_revision_id = revision.id
            eval_revision_id = eval_revision.id
            descriptor_revision_id = descriptor_revision.id

        print("[smoke] created target/evaluator")
        results_ok.append(
            _check("target revision has a config hash", bool(revision.config_hash))
        )
        results_ok.append(
            _check("evaluator revision starts DRAFT", eval_revision.status == "draft")
        )

        # --- 2. validation + approval ---------------------------------------
        async with factory() as session:
            service = EvaluatorService(session)
            job = await service.request_validation(
                eval_revision_id,
                idempotency_key=f"smoke-validate-{run_tag}",
                enqueue=_noop_enqueue,
            )
            await session.commit()
            job_id = job.id

        # run the real validation worker job (own session)
        status = await validate_evaluator_revision({}, eval_revision_id, job_id)

        async with factory() as session:
            revision_row = await EvaluatorService(session).get_revision(eval_revision_id)
            validated = revision_row.status == EvaluatorStatus.VALIDATED.value
            results_ok.append(_check("validation advanced to VALIDATED", validated, status))
            if validated:
                approved = await EvaluatorService(session).approve(eval_revision_id)
                await session.commit()
                results_ok.append(
                    _check("revision APPROVED", approved.status == "approved")
                )
            else:
                results_ok.append(_check("revision APPROVED", False, "validation failed"))
                return 1

        # --- 3. plan preparation --------------------------------------------
        async with factory() as session:
            plan = await PlanService(session).create_plan(
                kind="custom",
                agent_target_revision_id=target_revision_id,
                repeat_count=REPEAT_COUNT,
                test_descriptor_revision_id=descriptor_revision_id,
                evaluator_revision_ids=[eval_revision_id],
            )
            await session.commit()
            plan_id = plan.id

        async with factory() as session:
            prepared = await PlanService(session).prepare(plan_id)
            await session.commit()
            results_ok.append(
                _check("plan READY with manifest", prepared.plan.plan_status == "ready")
            )
            results_ok.append(
                _check("manifest hash computed", bool(prepared.manifest.manifest_hash))
            )
            results_ok.append(
                _check("one plan item", len(prepared.items) == 1)
            )

        # --- 4. execute + run attempts --------------------------------------
        async with factory() as session:
            await PlanService(session).execute(
                plan_id, idempotency_key=f"smoke-execute-{run_tag}", enqueue=_noop_enqueue
            )
            await session.commit()

        async with factory() as session:
            orchestrator = ExecutionOrchestrator(
                session, max_attempts_per_run=get_settings().max_attempts_per_run
            )
            plan_row = await orchestrator.get_plan(plan_id)
            # the execution_plan_start worker does this; we drive the orchestrator
            # directly here, so advance QUEUED -> RUNNING ourselves
            if plan_row.plan_status == PlanStatus.QUEUED.value:
                await orchestrator.transition_plan(plan_row, PlanStatus.RUNNING)
            runs = await orchestrator.ensure_runs(plan_row)
            attempt_ids: dict[str, str] = {}
            for run in runs:
                attempt = await orchestrator.start_run(run.id)
                await orchestrator.start_attempt(attempt.id)
                attempt_ids[run.id] = attempt.id
            await session.commit()

        results_ok.append(
            _check(
                f"{REPEAT_COUNT} repetitions create exactly {REPEAT_COUNT} CallRuns",
                len(runs) == REPEAT_COUNT,
                f"{len(runs)} runs",
            )
        )

        dispatcher = InlineRunnerDispatcher()
        for run_id, attempt_id in attempt_ids.items():
            # replay the deterministic script for each fresh connection
            server.caller_turns_seen = 0
            await dispatcher.dispatch(attempt_id)

        # --- 5. evaluation pipeline -----------------------------------------
        provider = StaticLLMProvider(JUDGE_OUTPUT)
        async with factory() as session:
            run_rows = await CallRunRepository(session).list_runs(plan_id)
            for run in run_rows:
                attempts = await CallAttemptRepository(session).list_attempts(run.id)
                eligible = [
                    a
                    for a in attempts
                    if a.eligible_for_evaluation and a.status == "terminal"
                ]
                if eligible:
                    await MetricEngine(session).compute_for_attempt(eligible[-1].id)
                await JudgeEngine(session, provider=provider).evaluate_run(run.id)
            # the judge worker advances plan status once every run has settled
            await PlanCompletionService(session).maybe_complete(plan_id)
            await session.commit()

        async with factory() as session:
            completed = [
                r for r in await CallRunRepository(session).list_runs(plan_id)
                if r.status == CallRunStatus.COMPLETED.value
            ]
            results_ok.append(
                _check(
                    "all runs completed",
                    len(completed) == REPEAT_COUNT,
                    f"{len(completed)}/{REPEAT_COUNT}",
                )
            )
            final_plan = await PlanService(session).get_plan(plan_id)
            results_ok.append(
                _check("plan reached a terminal status", final_plan.plan_status == "completed")
            )

        async with factory() as session:
            engine = AggregationEngine(session)
            aggregates = await engine.aggregate_plan(plan_id)
            composite = await engine.compute_composite(plan_id)
            await session.commit()
            results_ok.append(
                _check("aggregates written", len(aggregates) > 0, f"{len(aggregates)}")
            )
            results_ok.append(
                _check(
                    "composite computed",
                    composite.status in {"complete", "incomplete"},
                    f"status={composite.status} score={composite.score_0_100}",
                )
            )

        # --- 6. forensic retrieval ------------------------------------------
        first_run_id = next(iter(attempt_ids))
        async with factory() as session:
            bundle = await ForensicsService(session).reconstruct(first_run_id)
            results_ok.append(
                _check(
                    "forensic bundle reconstructs the run",
                    bool(bundle.get("run")) and bool(bundle.get("conversation")),
                )
            )
            events = bundle.get("conversation", {}).get("events", [])
            turns = bundle.get("conversation", {}).get("turns", [])
            results_ok.append(
                _check("runtime events materialized", len(events) > 0, f"{len(events)}")
            )
            results_ok.append(
                _check("conversation turns materialized", len(turns) > 0, f"{len(turns)}")
            )

        print("\n[smoke] plan status:")
        async with factory() as session:
            plan_row = await PlanService(session).get_plan(plan_id)
            print(f"  plan_status={plan_row.plan_status}")

    finally:
        await server.stop()

    passed = all(results_ok)
    print(f"\n[smoke] {'ALL CHECKS PASSED' if passed else 'SOME CHECKS FAILED'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
