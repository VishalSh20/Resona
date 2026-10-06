"""The Voice-Agent Judge.

Replaces the single-shot ``StructuredJudge`` with the staged architecture in
``docs/V2-changes/judge-implementation.md``: a media resolver + Stage 0 audio
alignment, Stage 1 evidence ledgers, Stage 2 parallel metric evaluators built on
Jev bounded decisions plus LLM investigation, and Stage 3 verification /
escalation. Fixed code performs all arithmetic and aggregation.

Public entry point: :class:`voiceeval.judging.engine.JudgeEngine`.
"""

from voiceeval.judging.engine import JudgeEngine

__all__ = ["JudgeEngine"]
