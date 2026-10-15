"""Pipecat caller conversation context: window bound, memory, hygiene, transcript."""

from __future__ import annotations

import json

from pipecat.frames.frames import LLMContextFrame, LLMUpdateSettingsFrame, TextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.utils.context.llm_context_summarization import LLMContextSummarizationUtil

from voiceeval.runtime.caller.persona import PersonaProfile
from voiceeval.runtime.pipecat_caller.call_context import (
    SUMMARY_PREFIX,
    SUMMARY_TEMPLATE,
    SUMMARIZE_AFTER,
    WINDOW_MESSAGES,
    CallContextProcessor,
    CallMemory,
    CallScript,
    CallTranscript,
    hygiene,
    summarization_config,
)
from voiceeval.runtime.scenario import parse_scenario

SCENARIO_DICT = parse_scenario(
    {
        "motive": {"objective": "Get help with my locked account"},
        "facts": [{"id": "account_id", "value": "AC-1234"}],
        "language": {"primary": "hi-IN", "secondary": "en-IN"},
    }
)
PERSONA = PersonaProfile(
    version="persona.v1", traits=("friendly", "patient"), primary_language="hi-IN"
)


def test_call_script_renders_persona_scenario_and_style():
    script = CallScript.from_scenario(SCENARIO_DICT, PERSONA, greet_first=False)
    rendered = script.render(CallMemory())
    assert "friendly" in rendered and "patient" in rendered
    assert "account_id" in rendered and "AC-1234" in rendered
    assert "Get help with my locked account" in rendered
    assert "Hindi" in rendered and "English" in rendered
    assert "CALL STATE:" in rendered


def test_opening_prompt_only_before_the_first_turn():
    script = CallScript(persona="friendly", scenario="s", goal="g", greet_first=True)
    memory = CallMemory()
    assert "Open the call now" in script.render(memory)
    memory.goal_status = "in progress"
    assert "Open the call now" not in script.render(memory)


def test_summarization_config_keeps_the_window_bounded():
    config = summarization_config()
    assert config.max_unsummarized_messages == SUMMARIZE_AFTER
    assert config.summary_config.min_messages_after_summary == WINDOW_MESSAGES
    # A fresh summary must not immediately re-trigger.
    assert config.max_unsummarized_messages > config.summary_config.min_messages_after_summary
    assert "GOAL_STATUS" in config.summary_config.summary_prompt
    assert config.summary_config.summary_message_template.startswith(SUMMARY_PREFIX)


def test_long_call_window_stays_bounded_and_memory_survives():
    """40 turns through Pipecat's own selection logic, then read the summary back."""
    script = CallScript(persona="friendly", scenario="s", goal="g")
    memory = CallMemory()
    messages: list[dict] = []
    peak = 0
    after_summary: list[int] = []

    for turn in range(40):
        messages.append({"role": "user", "content": f"user turn {turn}"})
        messages.append({"role": "assistant", "content": f"assistant turn {turn}"})
        if len(messages) >= SUMMARIZE_AFTER:
            # Exactly what LLMContextSummarizer is configured to do: summarize
            # everything outside the window and inject the summary message.
            todo = LLMContextSummarizationUtil.get_messages_to_summarize(
                _as_context(messages), WINDOW_MESSAGES
            )
            summary = {"role": "user", "content": SUMMARY_TEMPLATE.format(summary=_SUMMARY_BODY)}
            messages[:] = [summary] + messages[todo.last_summarized_index + 1 :]
            after_summary.append(len(messages))
        peak = max(peak, len(messages))

    # It compresses on the threshold, never past it, and leaves the window behind.
    assert peak <= SUMMARIZE_AFTER
    assert after_summary
    assert set(after_summary) == {WINDOW_MESSAGES + 1}

    assert hygiene(messages, memory) is True
    assert memory.summary == "the other person asked for a password reset"
    assert memory.already_said == ["gave the account id"]
    assert memory.goal_status == "in progress"
    assert "reset link" in memory.goal_note

    rendered = script.render(memory)
    assert "CALL STATE:" in rendered
    assert "already said: gave the account id" in rendered
    assert "goal: in progress (waiting for the reset link)" in rendered


def test_barge_in_merges_adjacent_user_messages():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "one"},
        {"role": "user", "content": "two"},
    ]
    hygiene(messages, CallMemory())
    assert [m["content"] for m in messages] == ["hello", "hi", "one two"]


def test_hygiene_reads_the_summary_without_merging_into_it():
    summary = {"role": "user", "content": SUMMARY_TEMPLATE.format(summary="CONVERSATION: x")}
    messages = [summary, {"role": "user", "content": "next thing"}]
    memory = CallMemory()
    assert hygiene(messages, memory) is True
    assert memory.summary == "x"
    assert len(messages) == 2


async def test_context_processor_refreshes_the_system_instruction():
    """After a summary lands, the CALL STATE block is pushed to the LLM."""
    script = CallScript(persona="friendly", scenario="s", goal="g")
    memory = CallMemory()
    pushed: list = []

    class _Probe(CallContextProcessor):
        async def push_frame(self, frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

    context = LLMContext(
        [{"role": "user", "content": SUMMARY_TEMPLATE.format(summary=_SUMMARY_BODY)}]
    )
    await _Probe(script, memory).process_frame(
        LLMContextFrame(context), FrameDirection.DOWNSTREAM
    )

    assert memory.goal_status == "in progress"
    refreshes = [frame for frame in pushed if isinstance(frame, LLMUpdateSettingsFrame)]
    assert len(refreshes) == 1
    instruction = refreshes[0].delta.given_fields()["system_instruction"]
    assert instruction.startswith("You are a friendly caller")
    assert "CALL STATE:" in instruction
    assert "goal: in progress (waiting for the reset link)" in instruction


async def test_touch_refreshes_on_the_next_frame():
    """A memory change at a turn boundary reaches the LLM without waiting a turn."""
    script = CallScript(persona="friendly", scenario="s", goal="g")
    memory = CallMemory()
    pushed: list = []

    class _Probe(CallContextProcessor):
        async def push_frame(self, frame, direction=FrameDirection.DOWNSTREAM):
            pushed.append(frame)

    processor = _Probe(script, memory)
    memory.goal_status = "in progress"
    processor.touch()
    await processor.process_frame(TextFrame(text="anything"), FrameDirection.DOWNSTREAM)

    refreshes = [frame for frame in pushed if isinstance(frame, LLMUpdateSettingsFrame)]
    assert len(refreshes) == 1
    instruction = refreshes[0].delta.given_fields()["system_instruction"]
    assert "- goal: in progress" in instruction
    assert "Open the call now" not in instruction


def test_transcript_records_completed_turns_only(tmp_path):
    transcript = CallTranscript()
    transcript.add("user", "", "2026-01-01T00:00:00Z")  # empty turn: dropped
    transcript.add("user", "namaste", "2026-01-01T00:00:00Z")
    transcript.add("assistant", "namaste, bataiye", "2026-01-01T00:00:01Z", True)

    assert [entry.role for entry in transcript.entries] == ["user", "assistant"]
    assert transcript.entries[1].interrupted is True

    path = transcript.dump(tmp_path / "transcript.json")
    payload = json.loads(path.read_text())
    assert [entry["idx"] for entry in payload] == [0, 1]
    assert payload[1]["interrupted"] is True


_SUMMARY_BODY = (
    "CONVERSATION: the other person asked for a password reset\n"
    "FROM_TARGET: they forgot the password\n"
    "FROM_US:\n- gave the account id\n"
    "GOAL_STATUS: in progress - waiting for the reset link\n"
    "UNRESOLVED: the reset link"
)


class _Context:
    """Minimal stand-in for LLMContext; the util only reads ``messages``."""

    def __init__(self, messages: list[dict]) -> None:
        self.messages = messages


def _as_context(messages: list[dict]) -> _Context:
    return _Context(messages)
