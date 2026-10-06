"""Instruction checklist (spec §3.2/§3.4).

Atomic instructions from the judge prompt, compiled twice. The intersection is
kept; items seen in only one pass are kept but flagged ``unstable`` and surfaced
in caveats. Instructions are trusted input, so they are not quote-checked
against the transcript.
"""

from __future__ import annotations

from voiceeval.judging.evidence.quote_check import normalize
from voiceeval.judging.evidence.result import LedgerInputs, LedgerResult
from voiceeval.judging.evidence.schemas import InstructionItem, RawInstructionList
from voiceeval.llm.base import BaseGenerationModel, LLMError

_SYSTEM = (
    "You compile a judge prompt into atomic instructions. Each instruction is a "
    "single testable requirement. Types: must, must_not, conditional (with a "
    "trigger), ordering, style, format. Severity: critical, major, minor. "
    "Evaluator: code for mechanical checks (regex/length/forbidden strings/tool "
    "ordering/required tool call), otherwise jev."
)
_USER = """Judge prompt:
{judge_prompt}

Return the atomic instruction checklist."""


def _split_instructions(judge_prompt: str) -> list[InstructionItem]:
    items: list[InstructionItem] = []
    for index, line in enumerate(_sentences(judge_prompt)):
        if not line.strip():
            continue
        items.append(
            InstructionItem(
                instruction_id=f"instr-{index}",
                text=line.strip(),
                type="must",
                severity="major",
                evaluator="jev",
                quote=line.strip(),
                turn_ids=[],
            )
        )
    return items


def _sentences(text: str) -> list[str]:
    parts: list[str] = []
    for line in text.replace(";", ".").split("."):
        line = line.strip(" -\t\n")
        if line:
            parts.append(line)
    return parts


async def _compile(llm: BaseGenerationModel | None, judge_prompt: str) -> list[InstructionItem]:
    if llm is None or not judge_prompt.strip():
        return _split_instructions(judge_prompt)
    try:
        result = await llm.structured(
            RawInstructionList, system=_SYSTEM, user=_USER.format(judge_prompt=judge_prompt)
        )
        return list(result.items)
    except LLMError:
        return _split_instructions(judge_prompt)


async def build_instruction_checklist(
    llm: BaseGenerationModel | None, inputs: LedgerInputs
) -> LedgerResult:
    if not inputs.judge_prompt.strip():
        return LedgerResult(ledger_type="instruction", status="ok", items=[])

    first = await _compile(llm, inputs.judge_prompt)
    second = await _compile(llm, inputs.judge_prompt)

    key = lambda item: normalize(item.text)  # noqa: E731
    first_map = {key(item): item for item in first}
    second_map = {key(item): item for item in second}
    intersection = set(first_map) & set(second_map)
    unstable = (set(first_map) | set(second_map)) - intersection

    items: list[InstructionItem] = []
    for text_key in sorted(intersection):
        items.append(first_map[text_key])
    caveats: list[str] = []
    for text_key in sorted(unstable):
        item = first_map.get(text_key) or second_map[text_key]
        items.append(item.model_copy(update={"unstable": True}))
        caveats.append(f"unstable_instruction: {item.text[:80]}")

    status = "unstable" if unstable else "ok"
    return LedgerResult(ledger_type="instruction", status=status, items=items, caveats=caveats)


__all__ = ["build_instruction_checklist"]
