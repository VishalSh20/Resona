"""Voice-Agent Judge constants and calibrated parameters.

Everything marked ``[P]`` in the spec is a calibration starting point, collected
here so a labeled call set can tune it in one place. Runtime-configurable knobs
(models, timeouts, thresholds) live on :class:`voiceeval.core.config.Settings`;
this module holds the fixed rubric data (credits, anchors, lexicons, ranks).
"""

from __future__ import annotations

from voiceeval.core.config import get_settings

JUDGE_KEY = "voice_agent_judge"
JUDGE_VERSION = "1.0"
JUDGE_KIND = "probe_judge"
OUTPUT_SCHEMA_VERSION = "judge.voice_agent.v1"

# §0.5: every judge metric is 1-5, higher is better (hallucination: 5 = none).
METRIC_SCALE = (1, 5)

# Non-adjacent anchors used by §8 ``to_1_5``. [P] replace with an isotonic fit.
ANCHORS: list[tuple[float, float]] = [
    (0.0, 1.0),
    (0.25, 1.5),
    (0.50, 2.5),
    (0.70, 3.0),
    (0.85, 4.0),
    (0.95, 5.0),
    (1.0, 5.0),
]

# §6.2 task_completion decision table.
TASK_COMPLETION_CATEGORY_MAP = {
    "completed": 100.0,
    "partial": 60.0,
    "failed": 0.0,
    "unknown": None,
}

# §6.2 task_completion evidence source ranking (strongest first).
SOURCE_RANK_ORDER = (
    "external_state",
    "verified_tool_result",
    "provider_event",
    "conversation_evidence",
    "llm_inference",
)

# §6.1 barge-in backchannel lexicon (multilingual, lowercase, matching tokens).
BACKCHANNEL_LEXICON = frozenset(
    {
        "hmm", "hm", "mm", "mhm", "uhhuh", "uh-huh", "okay", "ok", "yeah", "yep",
        "yes", "right", "sure", "haan", "ha", "achha", "accha", "theek", "thik",
        "theek hai", "thik hai", "ji", "ji haan", "hmm okay", "oh", "ohh", "ah",
        "ahaan", "haan ji",
    }
)

# Languages the LID tiebreak choice may return; deployments may override.
LANGUAGE_OPTIONS = ("en", "hi", "mr", "ta", "te", "bn", "kn", "mixed_hinglish", "other")

# §4.2 packet budget after which a decision falls back to the LLM adjudicator.
def packet_budget() -> int:
    return get_settings().packet_token_budget


def packet_cap() -> int:
    return get_settings().packet_token_cap


def rubric_version() -> str:
    return get_settings().judging_rubric_version


__all__ = [
    "ANCHORS",
    "BACKCHANNEL_LEXICON",
    "JUDGE_KEY",
    "JUDGE_KIND",
    "JUDGE_VERSION",
    "LANGUAGE_OPTIONS",
    "METRIC_SCALE",
    "OUTPUT_SCHEMA_VERSION",
    "SOURCE_RANK_ORDER",
    "TASK_COMPLETION_CATEGORY_MAP",
    "packet_budget",
    "packet_cap",
    "rubric_version",
]
