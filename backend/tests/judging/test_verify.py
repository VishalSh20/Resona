"""Verification majority logic, consistency flags and probe catalogue."""

from __future__ import annotations

from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import PROBES, get_probe, probes_for_metric
from voiceeval.judging.verify.consistency import evaluate_consistency
from voiceeval.judging.verify.verifier import majority_label


def _choice_answer(label: str) -> ProbeAnswer:
    return ProbeAnswer("rel.intent.v1", "choice", label, 0.8, {label: 1.0})


def test_majority_label_agrees():
    probe = get_probe("rel.intent.v1")
    jev = _choice_answer("resolved_fully")
    adj = _choice_answer("resolved_fully")
    ver = _choice_answer("resolved_fully")
    label, review = majority_label(probe, jev, adj, ver)
    assert label == "resolved_fully"
    assert review is False


def test_majority_label_all_differ_flags_review():
    probe = get_probe("rel.intent.v1")
    jev = _choice_answer("resolved_fully")
    adj = _choice_answer("resolved_partially")
    ver = _choice_answer("ignored")
    label, review = majority_label(probe, jev, adj, ver)
    assert review is True


def test_consistency_flags_detected():
    metrics = {
        "hallucination": {"value": 5, "breakdown": {}},
        "kb_groundedness": {"value": 0.5, "breakdown": {"contradicted_rate": 0.4}},
        "task_completion": {"value": "completed", "breakdown": {}},
        "instruction_following": {"value": 1, "breakdown": {}},
    }
    flags = evaluate_consistency(metrics)
    assert "hallucination_high_but_kb_contradicted" in flags
    assert "completed_but_critical_instruction_violated" in flags


def test_probe_catalogue_is_unique_and_covers_metrics():
    ids = [probe.probe_id for probe in PROBES]
    assert len(ids) == len(set(ids))
    for probe in PROBES:
        assert probe.type in {"noul", "choice", "score"}
        if probe.type == "choice" and probe.credits is not None:
            # Credits must reference declared options.
            assert set(probe.credits) <= set(probe.criteria or {})
    assert probes_for_metric("relevancy")
    assert probes_for_metric("semantic_preservation")
