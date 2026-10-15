"""Assemble the naive caller pipeline.

    transport.input() -> agent tap -> STT -> user aggregator -> context -> LLM
      -> TTS -> turn-end -> caller tap -> transport.output() -> assistant aggregator

The graph mirrors the reference sample; the taps record both audio directions,
``CallContextProcessor`` owns conversation-context hygiene, and the turn-end
processor forwards the target-protocol control message.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMAssistantAggregatorParams,
    LLMUserAggregatorParams,
)

from voiceeval.core.config import Settings
from voiceeval.runtime.livekit.recording import AttemptRecording
from voiceeval.runtime.pipecat_caller.call_context import (
    CallContextProcessor,
    CallMemory,
    CallScript,
    CallTranscript,
    attach_transcript,
    summarization_config,
)
from voiceeval.runtime.pipecat_caller.context import CallerContext
from voiceeval.runtime.pipecat_caller.control import CallerTurnEndProcessor
from voiceeval.runtime.pipecat_caller.recording import AgentAudioTap, CallerAudioTap
from voiceeval.runtime.pipecat_caller.services import (
    build_llm,
    build_stt,
    build_tts,
    build_vad,
)
from voiceeval.runtime.pipecat_caller.settings import PipecatCallerSettings
from voiceeval.runtime.pipecat_caller.transport import (
    VOICE_EVAL_PROTOCOL,
    build_websocket_transport,
)


#: Suffix marking a reply that was cut off by a barge-in.
_INTERRUPTED = " [interrupted]"


@dataclass
class CallerPipeline:
    """The assembled pipeline plus the handles the runner needs."""

    transport: Any
    context: LLMContext
    task: PipelineWorker
    recording: AttemptRecording
    llm: Any
    script: CallScript
    memory: CallMemory
    transcript: CallTranscript


def build_caller_pipeline(
    *,
    caller_context: CallerContext,
    settings: PipecatCallerSettings,
    recording: AttemptRecording,
    core: Settings | None = None,
    memory: CallMemory | None = None,
) -> CallerPipeline:
    script = caller_context.script
    memory = memory or CallMemory()
    transport = build_websocket_transport(
        url=caller_context.target_ws_url,
        sample_rate=caller_context.in_sample_rate,
        headers=caller_context.target_headers,
        protocol=caller_context.target_protocol,
    )
    stt = build_stt(settings, core)
    tts = build_tts(settings, core)
    llm = build_llm(core, system_instruction=script.render(memory))
    vad = build_vad(caller_context.in_sample_rate)

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
        assistant_params=LLMAssistantAggregatorParams(
            enable_auto_context_summarization=True,
            auto_context_summarization_config=summarization_config(
                window_messages=settings.window_messages,
                summarize_after=settings.summarize_after,
            ),
        ),
    )

    transcript = CallTranscript()
    context_processor = CallContextProcessor(script, memory)

    async def _on_assistant_stop(message) -> None:
        # The call has been opened, so the greeting prompt must not repeat.
        if message.content and memory.goal_status == "not started":
            memory.goal_status = "in progress"
            context_processor.touch()
        # Keep an interrupted reply in the history, marked, instead of losing the
        # turn (which would otherwise leave two user messages adjacent). Pipecat
        # can report the same barged-in turn more than once, so this is
        # idempotent: a reply is never marked twice.
        if message.interrupted and message.content:
            messages = context.get_messages()
            tail = messages[-1] if messages else None
            text = str(tail.get("content", "")) if isinstance(tail, dict) else ""
            if message.content[:40] in text:
                if not text.endswith(_INTERRUPTED):
                    tail["content"] = f"{text}{_INTERRUPTED}"
            else:
                context.add_message(
                    {"role": "assistant", "content": f"{message.content}{_INTERRUPTED}"}
                )

    attach_transcript(
        user_aggregator, assistant_aggregator, transcript, _on_assistant_stop
    )

    pipeline = Pipeline(
        [
            transport.input(),
            AgentAudioTap(recording),
            stt,
            user_aggregator,
            context_processor,
            llm,
            tts,
            # The turn-end control message is specific to the voiceeval target
            # protocol; a native Pipecat agent drives its own turn boundaries.
            *(
                [CallerTurnEndProcessor()]
                if caller_context.target_protocol == VOICE_EVAL_PROTOCOL
                else []
            ),
            CallerAudioTap(recording),
            transport.output(),
            assistant_aggregator,
        ]
    )
    params = PipelineParams(
        audio_in_sample_rate=caller_context.in_sample_rate,
        audio_out_sample_rate=caller_context.out_sample_rate,
        enable_metrics=True,
        enable_usage_metrics=True,
    )
    return CallerPipeline(
        transport=transport,
        context=context,
        # RTVI is a client/server control protocol this caller does not speak; a
        # target that emits RTVI messages would only produce decode warnings.
        task=PipelineWorker(pipeline, params=params, enable_rtvi=False),
        recording=recording,
        llm=llm,
        script=script,
        memory=memory,
        transcript=transcript,
    )


__all__ = ["CallerPipeline", "build_caller_pipeline"]
