"""Jev probe runner and answer interpretation."""

from __future__ import annotations

import pytest

from voiceeval.judging.metrics.judge_common import answer_credit
from voiceeval.judging.probes.jev import JevRunner
from voiceeval.judging.probes.registry import get_probe
from voiceeval.llm.base import DecisionAnswer, DecisionQuestion, StaticDecisionModel


async def test_jev_runner_returns_typed_answers():
    model = StaticDecisionModel(
        {
            "is_urgent": DecisionAnswer(type="noul", value=0.93),
            "team": DecisionAnswer(
                type="choice", value="billing", confidence=0.8,
                probabilities={"billing": 0.8, "technical": 0.2},
            ),
        }
    )
    runner = JevRunner(model)
    questions = {
        "is_urgent": DecisionQuestion("noul", "urgent?", {"true": "y", "false": "n"}),
        "team": DecisionQuestion("choice", "team?", {"billing": "", "technical": ""}),
    }
    answers = await runner.run({"ticket": "x"}, questions)
    assert answers["is_urgent"].value == pytest.approx(0.93)
    assert answers["team"].value == "billing"


def test_answer_credit_noul_and_choice():
    noul = get_probe("emp.move.v1")
    answer = DecisionAnswer(type="noul", value=0.8)
    from voiceeval.judging.probes.jev import ProbeAnswer

    assert answer_credit(noul, ProbeAnswer("emp.move.v1", "noul", 0.8)) == pytest.approx(0.8)

    choice = get_probe("rel.turn.v1")
    answer = ProbeAnswer(
        "rel.turn.v1", "choice", "fully_addresses",
        probabilities={"fully_addresses": 0.7, "deflects_or_irrelevant": 0.3},
    )
    assert answer_credit(choice, answer) == pytest.approx(0.7)


def test_answer_credit_inverted_noul():
    probe = get_probe("sp.add.v1")  # inverted
    from voiceeval.judging.probes.jev import ProbeAnswer

    assert answer_credit(probe, ProbeAnswer("sp.add.v1", "noul", 0.9)) == pytest.approx(0.1)
