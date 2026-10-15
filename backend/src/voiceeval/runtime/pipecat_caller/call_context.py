"""Conversation context for the pipecat caller: script, memory, window, transcript.

Three layers, plus a transcript that is kept separately:

* :class:`CallScript` — the static per-call facts (persona, scenario, goal,
  style). Rendered once into the LLM's ``system_instruction``; this is the only
  place the persona is stored.
* :class:`CallMemory` — the small mutable state that survives summarization
  (rolling summary, what we have already said, goal status). Rendered into a
  ``CALL STATE`` block appended to the system instruction.
* The recent window — the last ``WINDOW_MESSAGES`` context messages kept
  verbatim. Older ones are folded into :attr:`CallMemory.summary` by Pipecat's
  context summarizer, configured in :func:`summarization_config`.

All context changes happen between turns: :class:`CallContextProcessor` runs
hygiene (and a system-instruction refresh) as a completed turn is handed to the
LLM, never while a turn is in flight.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipecat.frames.frames import Frame, LLMContextFrame, LLMUpdateSettingsFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.settings import LLMSettings

from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.scenario import Scenario

#: Messages kept verbatim; the summarizer folds everything older into memory.
WINDOW_MESSAGES = 12
#: Summarize once this many messages have accumulated. Must exceed
#: WINDOW_MESSAGES, or a fresh summary would immediately re-trigger.
SUMMARIZE_AFTER = 20
#: Marker the summarizer's injected message carries, so we can read it back.
SUMMARY_PREFIX = "[CALL SUMMARY]"
SUMMARY_TEMPLATE = SUMMARY_PREFIX + "\n{summary}"

_LANGUAGE_NAMES = {
    "hi": "Hindi", "en": "English", "bn": "Bengali", "ta": "Tamil", "te": "Telugu",
    "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "or": "Odia", "as": "Assamese", "ur": "Urdu", "ne": "Nepali",
}

STYLE_RULES = """\
- Every reply is spoken aloud: one or two short sentences, no lists or markdown.
- Write numbers the way they are said out loud.
- Vary your phrasing. Never repeat anything listed under already said below.
- Never re-ask for information the other person has already given you.
- Stay in character: never mention that you are an AI, a model or a test."""

SUMMARIZATION_PROMPT = """\
Summarize the conversation so far as the caller's own memory. Reply with exactly
these labeled sections and nothing else:

CONVERSATION: two or three sentences on what has happened.
FROM_TARGET: facts the other person gave us, one per line.
FROM_US: facts or requests we have already given, one per line.
GOAL_STATUS: one of not started / in progress / done / blocked, then " - " and a short note.
UNRESOLVED: what is still open.

Omit greetings and small talk. The transcript follows."""


def _language_label(code: Any) -> str:
    if not code:
        return "Hindi"
    return _LANGUAGE_NAMES.get(str(code).split("-")[0].lower(), str(code))


@dataclass(frozen=True)
class CallScript:
    """The static script for one call; rendered into the system instruction."""

    persona: str
    scenario: str
    goal: str
    style_rules: str = STYLE_RULES
    greet_first: bool = False

    @classmethod
    def from_scenario(
        cls, scenario: Scenario, persona: PersonaProfile, *, greet_first: bool
    ) -> "CallScript":
        goal = scenario.objective or "have a short, natural conversation"
        language = _language_label(
            persona.primary_language or scenario.language.get("primary")
        )
        secondary = persona.secondary_language or scenario.language.get("secondary")
        speak = f"- Speak {language}"
        if secondary:
            speak += f", mixing in {_language_label(secondary)} where it is natural"
        scenario_text = f"You are calling about: {goal}."
        if scenario.facts:
            facts = "; ".join(f"{key}: {value}" for key, value in scenario.facts.items())
            scenario_text += f"\nFacts you may share if asked: {facts}"
        return cls(
            persona=", ".join(persona.traits) if persona.traits else "neutral",
            scenario=scenario_text,
            goal=goal,
            style_rules=f"{speak}\n{STYLE_RULES}",
            greet_first=greet_first,
        )

    def render(self, memory: "CallMemory") -> str:
        """Render the full system instruction for the current memory state."""
        parts = [
            f"You are a {self.persona} caller on a live voice call.",
            self.scenario,
            "Rules:",
            self.style_rules,
            memory.render(),
        ]
        if self.greet_first and memory.goal_status == "not started":
            parts.append("Open the call now with a brief spoken greeting.")
        return "\n".join(parts)


@dataclass
class CallMemory:
    """The small mutable state carried across summarization."""

    summary: str = ""
    already_said: list[str] = field(default_factory=list)
    goal_status: str = "not started"
    goal_note: str = ""
    max_already_said: int = 10

    def render(self) -> str:
        if not self.summary and not self.already_said and self.goal_status == "not started":
            return "CALL STATE:\n- nothing said yet."
        lines = ["CALL STATE:"]
        if self.summary:
            lines.append(f"- so far: {self.summary}")
        if self.already_said:
            lines.append("- already said: " + "; ".join(self.already_said))
        note = f" ({self.goal_note})" if self.goal_note else ""
        lines.append(f"- goal: {self.goal_status}{note}")
        return "\n".join(lines)

    def update_from_summary(self, text: str) -> bool:
        """Read the summarizer's labeled sections back into memory."""
        before = (self.summary, tuple(self.already_said), self.goal_status, self.goal_note)
        sections: dict[str, list[str]] = {}
        current = ""
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            key, sep, value = line.partition(":")
            if sep and key.strip().upper() in _SUMMARY_SECTIONS:
                current = key.strip().upper()
                sections.setdefault(current, [])
                if value.strip():
                    sections[current].append(value.strip())
            elif current:
                sections[current].append(line)

        conversation = " ".join(sections.get("CONVERSATION", [])).strip()
        if conversation:
            self.summary = conversation
        said = [s.lstrip("-• ").strip() for s in sections.get("FROM_US", []) if s.strip()]
        if said:
            self.already_said = said[-self.max_already_said :]
        status = " ".join(sections.get("GOAL_STATUS", [])).strip()
        if status:
            head, _, note = status.partition("-")
            head = head.strip().lower()
            if head in _GOAL_STATUSES:
                self.goal_status = head
                self.goal_note = note.strip()
        after = (self.summary, tuple(self.already_said), self.goal_status, self.goal_note)
        return after != before


_SUMMARY_SECTIONS = frozenset(
    {"CONVERSATION", "FROM_TARGET", "FROM_US", "GOAL_STATUS", "UNRESOLVED"}
)
_GOAL_STATUSES = frozenset({"not started", "in progress", "done", "blocked"})


def is_summary_message(message: Any) -> bool:
    return (
        isinstance(message, dict)
        and message.get("role") == "user"
        and isinstance(message.get("content"), str)
        and message["content"].startswith(SUMMARY_PREFIX)
    )


def hygiene(messages: list[Any], memory: CallMemory) -> bool:
    """Run between-turn context hygiene, in place. Returns True if memory changed.

    Two fixes to the raw context: the summarizer's injected summary is read back
    into memory, and barge-in left-over consecutive user messages are merged so
    the LLM never sees two user turns in a row.
    """
    changed = False
    if messages and is_summary_message(messages[0]):
        body = messages[0]["content"][len(SUMMARY_PREFIX) :].strip()
        changed = memory.update_from_summary(body)

    merged: list[Any] = []
    for message in messages:
        previous = merged[-1] if merged else None
        if (
            isinstance(message, dict)
            and isinstance(previous, dict)
            and message.get("role") == "user"
            and previous.get("role") == "user"
            and not is_summary_message(message)
            and not is_summary_message(previous)
        ):
            previous["content"] = (
                f"{previous.get('content', '')} {message.get('content', '')}".strip()
            )
        else:
            merged.append(message)
    if len(merged) != len(messages):
        messages[:] = merged
    return changed


def summarization_config(
    *, window_messages: int = WINDOW_MESSAGES, summarize_after: int = SUMMARIZE_AFTER
) -> Any:
    """Pipecat auto-summarization config, tuned to keep the window bounded."""
    from pipecat.utils.context.llm_context_summarization import (
        LLMAutoContextSummarizationConfig,
        LLMContextSummaryConfig,
    )

    return LLMAutoContextSummarizationConfig(
        max_context_tokens=6000,
        max_unsummarized_messages=summarize_after,
        summary_config=LLMContextSummaryConfig(
            target_context_tokens=500,
            min_messages_after_summary=window_messages,
            summarization_prompt=SUMMARIZATION_PROMPT,
            summary_message_template=SUMMARY_TEMPLATE,
        ),
    )


class CallContextProcessor(FrameProcessor):
    """Between-turn hygiene and CALL STATE refresh; sits just before the LLM."""

    def __init__(self, script: CallScript, memory: CallMemory) -> None:
        super().__init__()
        self._script = script
        self._memory = memory
        self._last_rendered: str | None = script.render(memory)
        self._dirty = False

    def touch(self) -> None:
        """Flag that memory changed; the refresh is pushed on the next frame."""
        self._dirty = True

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame) and hygiene(
            frame.context.get_messages(), self._memory
        ):
            self._dirty = True
        # Refresh on any frame, so a memory change made at a turn boundary does
        # not wait for the next user turn to reach the LLM.
        if self._dirty:
            self._dirty = False
            rendered = self._script.render(self._memory)
            if rendered != self._last_rendered:
                self._last_rendered = rendered
                await self.push_frame(
                    LLMUpdateSettingsFrame(
                        delta=LLMSettings(system_instruction=rendered)
                    ),
                    FrameDirection.DOWNSTREAM,
                )
        await self.push_frame(frame, direction)


@dataclass
class TranscriptEntry:
    idx: int
    role: str
    text: str
    t_start: str
    interrupted: bool = False


@dataclass
class CallTranscript:
    """Debug/judging transcript. Never fed back to the LLM."""

    entries: list[TranscriptEntry] = field(default_factory=list)

    def add(
        self, role: str, text: str, t_start: str, interrupted: bool = False
    ) -> None:
        if not text:
            return
        # Pipecat can fire a turn-stop more than once for a barged-in turn; only
        # the first report of a given turn belongs in the transcript.
        if self.entries and (
            self.entries[-1].role,
            self.entries[-1].text,
            self.entries[-1].t_start,
        ) == (role, text, t_start):
            return
        self.entries.append(
            TranscriptEntry(len(self.entries), role, text, t_start, interrupted)
        )

    def dump(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [entry.__dict__ for entry in self.entries]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return path


def attach_transcript(
    user_aggregator: Any,
    assistant_aggregator: Any,
    transcript: CallTranscript,
    on_assistant_stop: Any = None,
) -> None:
    """Record completed turns from the aggregators' own events."""

    @user_aggregator.event_handler("on_user_turn_message_added")
    async def _on_user_turn(aggregator, message) -> None:
        transcript.add("user", message.content, message.timestamp)

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def _on_assistant_turn(aggregator, message) -> None:
        transcript.add(
            "assistant", message.content, message.timestamp, message.interrupted
        )
        if on_assistant_stop is not None:
            await on_assistant_stop(message)


__all__ = [
    "SUMMARY_PREFIX",
    "SUMMARIZATION_PROMPT",
    "SUMMARIZE_AFTER",
    "WINDOW_MESSAGES",
    "CallContextProcessor",
    "CallMemory",
    "CallScript",
    "CallTranscript",
    "TranscriptEntry",
    "attach_transcript",
    "hygiene",
    "is_summary_message",
    "summarization_config",
]
