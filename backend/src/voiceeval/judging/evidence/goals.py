"""Goal checklist (spec §3.2): required conditions from the scenario outcome."""

from __future__ import annotations

from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import GoalItem, RawGoalList
from voiceeval.llm.base import BaseGenerationModel, LLMError

_SYSTEM = (
    "You compile a scenario's expected outcome into atomic required conditions. "
    "Each condition needs a verification_source: tool, external_state or "
    "conversation. Mark conditions whose failure defeats the call as critical."
)
_USER = """Scenario / expected outcome:
{scenario}

Return the required-condition checklist."""


def _fallback(scenario: str) -> list[GoalItem]:
    items: list[GoalItem] = []
    for index, line in enumerate(scenario.replace(";", ".").split(".")):
        line = line.strip(" -\t\n")
        if not line:
            continue
        items.append(
            GoalItem(
                goal_id=f"goal-{index}",
                condition=line,
                critical=False,
                verification_source="conversation",
                quote=line,
                turn_ids=[],
            )
        )
    return items


async def build_goal_checklist(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    if not inputs.scenario.strip():
        return LedgerResult(ledger_type="goal", status="ok", items=[])
    items: list[GoalItem]
    if llm is None:
        items = _fallback(inputs.scenario)
    else:
        try:
            result = await llm.structured(
                RawGoalList, system=_SYSTEM, user=_USER.format(scenario=inputs.scenario)
            )
            items = list(result.items)
        except LLMError:
            items = _fallback(inputs.scenario)
    if not items:
        items = _fallback(inputs.scenario)
    return LedgerResult(ledger_type="goal", status="ok", items=items)


__all__ = ["build_goal_checklist"]
