"""Metric evaluation flow with static decision models."""

from __future__ import annotations

from voiceeval.core.config import Settings
from voiceeval.judging.evidence.builder import Ledgers
from voiceeval.judging.evidence.result import LedgerResult
from voiceeval.judging.evidence.schemas import IntentItem
from voiceeval.judging.metrics import relevance
from voiceeval.judging.metrics.base import MetricContext, to_outcome
from voiceeval.judging.probes.jev import JevRunner
from voiceeval.judging.retrieval.base import NoopRetrieval
from voiceeval.judging.schemas import MediaValidation
from voiceeval.judging.stage0.runner import Stage0Result
from voiceeval.judging.stage0.turns import TurnRecord
from voiceeval.llm.base import DecisionAnswer, StaticDecisionModel
from voiceeval.metrics.registry import get_metric_registry
from voiceeval.metrics.signals import AttemptSignals


def _stage0() -> Stage0Result:
    turns = [
        TurnRecord(turn_id=1, speaker="caller", t_start=0, t_end=1000, text="I need to change my booking date"),
        TurnRecord(turn_id=2, speaker="agent", t_start=1200, t_end=2200, text="Sure, what date would you like?"),
    ]
    return Stage0Result(
        attempt_id="att_1",
        validation=MediaValidation(integrity_ok=True, alignment_ok=True),
        turns=turns,
    )


def _context(model: StaticDecisionModel) -> MetricContext:
    ledgers = Ledgers()
    ledgers.intent = LedgerResult(
        ledger_type="intent",
        items=[
            IntentItem(
                intent_id="intent-1",
                text="change booking date",
                critical=True,
                turn_ids=[1],
                quote="I need to change my booking date",
            )
        ],
    )
    return MetricContext(
        spec=get_metric_registry().get("relevancy"),
        stage0=_stage0(),
        signals=AttemptSignals(),
        ledgers=ledgers,
        evaluator_content={},
        judge_prompt="",
        scenario="",
        language_policy={"mode": "mirror_caller"},
        capabilities=frozenset(),
        runner=JevRunner(model),
        llm=None,
        retrieval=NoopRetrieval(),
        settings=Settings(),
        verify=None,
    )


async def test_relevancy_produces_scored_evaluation():
    model = StaticDecisionModel(
        {
            "rel.turn.v1": DecisionAnswer(
                type="choice", value="fully_addresses",
                probabilities={"fully_addresses": 0.9, "deflects_or_irrelevant": 0.1},
                confidence=0.9,
            ),
            "rel.tangent.v1": DecisionAnswer(type="noul", value=0.05),
            "rel.intent.v1": DecisionAnswer(
                type="choice", value="resolved_fully",
                probabilities={"resolved_fully": 0.95, "ignored": 0.05},
                confidence=0.9,
            ),
        }
    )
    evaluation = await relevance.evaluate(_context(model))
    assert evaluation.status == "ok"
    assert 1 <= evaluation.value <= 5
    assert evaluation.direction == "higher_is_better"
    assert evaluation.probes

    outcome = to_outcome(get_metric_registry().get("relevancy"), evaluation)
    assert outcome.is_computed
    assert outcome.value == evaluation.value
