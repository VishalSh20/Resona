"""LLM label extraction shared by the adjudicator and verifier (spec §5.3/§5.4)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import ProbeSpec
from voiceeval.llm.base import BaseGenerationModel, LLMError


class LabelVerdict(BaseModel):
    label: str
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


def label_options(probe: ProbeSpec) -> list[str]:
    if probe.type == "noul":
        return ["true", "false"]
    if probe.type == "score":
        levels = probe.criteria if isinstance(probe.criteria, list) else []
        return [str(index) for index in range(len(levels))]
    criteria = probe.criteria if isinstance(probe.criteria, dict) else {}
    return list(criteria.keys())


def label_to_answer(probe: ProbeSpec, label: str, confidence: float, resolver: str) -> ProbeAnswer:
    if probe.type == "noul":
        value = 1.0 if label == "true" else 0.0
        return ProbeAnswer(probe.probe_id, "noul", value, confidence, {label: 1.0}, resolver=resolver)
    if probe.type == "score":
        levels = probe.criteria if isinstance(probe.criteria, list) else []
        probabilities = {str(i): (1.0 if str(i) == label else 0.0) for i in range(len(levels))}
        return ProbeAnswer(probe.probe_id, "score", float(label or 0), confidence, probabilities, resolver=resolver)
    return ProbeAnswer(probe.probe_id, "choice", label, confidence, {label: 1.0}, resolver=resolver)


def answer_label(probe: ProbeSpec, answer: ProbeAnswer) -> str | None:
    if probe.type == "noul":
        return "true" if float(answer.value or 0.0) >= 0.5 else "false"
    if answer.probabilities:
        return max(answer.probabilities, key=answer.probabilities.get)
    if answer.value is None:
        return None
    return str(answer.value)


async def ask_label(
    llm: BaseGenerationModel,
    probe: ProbeSpec,
    state: dict[str, Any],
    *,
    model: str | None = None,
    jev_answer: ProbeAnswer | None = None,
) -> LabelVerdict | None:
    options = label_options(probe)
    system = (
        "You are an adjudicator for a single bounded decision. Choose exactly one "
        "label from the options. Return JSON with label, rationale and confidence."
    )
    payload = {
        "question": probe.instructions,
        "options": options,
        "option_criteria": probe.criteria,
        "state": state,
        "prior_jev_answer": {
            "label": answer_label(probe, jev_answer) if jev_answer else None,
            "probabilities": jev_answer.probabilities if jev_answer else None,
        },
    }
    user = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        verdict = await llm.structured(LabelVerdict, system=system, user=user, model=model)
    except (LLMError, Exception):  # noqa: BLE001 - adjudication is best-effort
        return None
    if verdict.label not in options:
        return None
    return verdict


__all__ = [
    "LabelVerdict",
    "answer_label",
    "ask_label",
    "label_options",
    "label_to_answer",
]
