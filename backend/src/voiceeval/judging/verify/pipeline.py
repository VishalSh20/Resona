"""Verification pipeline (spec §5.3/§5.4): variants, adjudication, verifier."""

from __future__ import annotations

import logging
from typing import Any

from voiceeval.judging.probes.jev import ProbeAnswer
from voiceeval.judging.probes.registry import ProbeSpec
from voiceeval.judging.verify.adjudicator import Adjudicator
from voiceeval.judging.verify.asr_guard import ASRGuard
from voiceeval.judging.verify.labels import (
    LabelVerdict,
    answer_label,
    label_to_answer,
)
from voiceeval.judging.verify.verifier import Verifier, majority_label
from voiceeval.llm.base import BaseGenerationModel

logger = logging.getLogger("voiceeval.judging.verify")


class VerificationPipeline:
    def __init__(
        self,
        llm: BaseGenerationModel | None,
        *,
        adjudicator_model: str | None = None,
        verifier_model: str | None = None,
        asr_guard: ASRGuard | None = None,
    ) -> None:
        self._adjudicator = Adjudicator(llm, model=adjudicator_model)
        self._verifier = Verifier(llm, model=verifier_model)
        self._llm = llm
        self.asr_guard = asr_guard
        self.needs_human_review = False
        self.escalations = 0

    async def adjudicate(
        self,
        probe: ProbeSpec,
        state: dict[str, Any],
        jev_answer: ProbeAnswer,
        turn_ids: list[int | str],
    ) -> tuple[ProbeAnswer, bool, bool | None]:
        """Return ``(final_answer, escalated, variants_agree)``."""
        variants_agree: bool | None = None
        if probe.variants:
            variants_agree = await self._check_variants(probe, state, jev_answer)

        adjudicated = await self._adjudicator.adjudicate(probe, state, jev_answer)
        verified = None
        if probe.critical or adjudicated is None:
            verified = await self._verifier.verify(probe, state, jev_answer)

        label, review = majority_label(probe, jev_answer, adjudicated, verified)
        if review:
            self.needs_human_review = True
            logger.info("probe %s has no majority label; flagged for review", probe.probe_id)

        final = adjudicated or verified
        if final is None:
            self.escalations += 1
            return jev_answer, True, variants_agree
        if label is not None:
            final = label_to_answer(probe, label, final.confidence or 0.5, final.resolver)
        final = _with_model(final, jev_answer.model)
        self.escalations += 1
        return final, True, variants_agree

    async def _check_variants(
        self, probe: ProbeSpec, state: dict[str, Any], jev_answer: ProbeAnswer
    ) -> bool | None:
        if self._llm is None:
            return None
        base_label = answer_label(probe, jev_answer)
        if base_label is None:
            return None
        from voiceeval.judging.verify.labels import ask_label

        for variant in probe.variants:
            variant_probe = ProbeSpec(
                probe_id=probe.probe_id,
                metric_key=probe.metric_key,
                type=probe.type,
                instructions=variant,
                criteria=probe.criteria,
                credits=probe.credits,
                weight=probe.weight,
                critical=probe.critical,
                invert=probe.invert,
            )
            verdict: LabelVerdict | None = await ask_label(
                self._llm, variant_probe, state, model=None, jev_answer=jev_answer
            )
            if verdict is not None and verdict.label != base_label:
                return False
        return True


def _with_model(answer: ProbeAnswer, model: str | None) -> ProbeAnswer:
    answer.model = model
    return answer


__all__ = ["VerificationPipeline"]
