"""Cross-metric consistency checks (spec §5.6).

Flags route the run to human review; they never change a score.
"""

from __future__ import annotations

from typing import Any


def evaluate_consistency(metrics: dict[str, dict[str, Any]]) -> list[str]:
    flags: list[str] = []

    def value(key: str):
        block = metrics.get(key)
        return block.get("value") if block else None

    def breakdown(key: str) -> dict:
        block = metrics.get(key)
        return (block or {}).get("breakdown") or {}

    hallucination = value("hallucination")
    contradicted_rate = breakdown("kb_groundedness").get("contradicted_rate")
    if hallucination is not None and float(hallucination) >= 4 and contradicted_rate:
        flags.append("hallucination_high_but_kb_contradicted")

    task = value("task_completion")
    instruction = value("instruction_following")
    if task == "completed" and instruction is not None and float(instruction) <= 2:
        flags.append("completed_but_critical_instruction_violated")

    context = value("context_retention")
    repetition = value("repetition")
    if context is not None and float(context) >= 4 and repetition is not None and float(repetition) > 0.25:
        flags.append("context_retention_high_but_repetition")

    consistency = value("language_consistency")
    detection = value("language_detection_accuracy")
    if consistency is not None and float(consistency) >= 4 and detection is not None and float(detection) < 0.6:
        flags.append("language_consistency_high_but_detection_low")

    return flags


__all__ = ["evaluate_consistency"]
