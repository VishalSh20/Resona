import asyncio
import json

from voiceeval.core.config import get_settings
from voiceeval.generation import SimulationPreferencesWorkflow, EvaluationsWorkflow
from voiceeval.generation.models import SimulationInput, SimulationWorkflowSpec

s = get_settings()
print("== config ==", s.llm_provider, s.openrouter_model, s.jev_model, flush=True)


async def main():
    print("\n[1/2] Workflow A (preferences) ...", flush=True)
    prefs = await SimulationPreferencesWorkflow().run(
        description=(
            "Test whether a Hindi-English banking support voice agent can correctly "
            "handle blocked credit-card requests, complete mandatory authentication, "
            "and adapt to frustrated callers who interrupt and code-switch."
        ),
        available_metrics=[
            "ttfa", "ttft", "barge_in_latency", "barge_in_success_rate",
            "language_detection_accuracy", "relevancy", "context_retention",
            "instruction_following", "empathy", "hallucination",
            "semantic_preservation", "language_consistency", "repetition",
            "task_completion", "kb_groundedness", "code_switching_accuracy",
        ],
        available_personalities=[
            "SUPPORTIVE", "CONCISE", "VERBOSE", "ABUSIVE", "INTERRUPTOR",
            "IMPATIENT", "CONFUSED", "SKEPTICAL", "COOPERATIVE", "UNCOOPERATIVE",
            "HESITANT", "REPETITIVE", "EMOTIONAL", "DEMANDING",
        ],
    )
    print("Workflow A metrics:", json.dumps([str(m) for m in prefs.metrics]), flush=True)
    print(
        "Workflow A personalities:",
        json.dumps([str(p) for p in prefs.personalities]),
        flush=True,
    )

    print("\n[2/2] Workflow B (evaluations) ...", flush=True)
    sim = SimulationInput(
        name="Credit Card Support",
        description="Handle blocked credit-card requests with mandatory authentication.",
        languages=["hi", "en"],
        backgrounds=[
            "WORKING_PROFESSIONAL",
            "STUDENT",
            "EXISTING_CUSTOMER",
            "NON_TECHNICAL_USER",
        ],
        metric_set=prefs.metrics,
        personalities=prefs.personalities,
        knowledge_base={"facts": {"customer_name": "Rahul", "card_last_four": "4821"}},
        evaluator_count=2,
    )
    spec = SimulationWorkflowSpec(
        objective="Verify the agent unblocks the card only after completing authentication.",
        task_flow=[
            {"step": "greet", "description": "agent greets and asks how to help"},
            {"step": "authenticate", "description": "agent verifies identity before acting"},
            {"step": "resolve", "description": "agent unblocks the card or explains next steps"},
        ],
        success_conditions=["card unblocked after authentication", "no invented information"],
        constraints=["must authenticate before acting"],
        failure_modes=["bypassing authentication", "inventing unsupported information"],
        knowledge_usage=["use card_last_four only when asked"],
    )
    drafts = await EvaluationsWorkflow().run(simulation=sim, workflow_spec=spec)
    print(f"\ngenerated {len(drafts)} evaluators", flush=True)
    for i, d in enumerate(drafts, 1):
        print(f"\n--- Evaluator {i} ---")
        print("background:", d.background)
        print("languages:", json.dumps(d.languages))
        print("personality:", json.dumps([str(p) for p in d.personality]))
        print("metrics:", json.dumps([str(m) for m in d.metrics]))
        print("scenario:\n", d.scenario)
        print("expected_output_prompt:\n", d.expected_output_prompt)


asyncio.run(main())
