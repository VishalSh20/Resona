"""Caller runtime tests: state, policy, actions, language, controller."""

from __future__ import annotations

from voiceeval.runtime.caller import (
    ActionSelector,
    CallerController,
    LanguageController,
    PolicyEngine,
    ScenarioState,
)
from voiceeval.runtime.caller.policy import CallerObservation
from voiceeval.runtime.events import CanonicalEventBuilder, EventSource, EventType
from voiceeval.runtime.media.tts import TTS
from voiceeval.runtime.providers.deterministic import DeterministicTTS


def _controller(scenario):
    builder = CanonicalEventBuilder("att_1", monotonic_clock=lambda: 0)
    tts = TTS(DeterministicTTS(), builder)
    return CallerController(scenario, tts=tts, builder=builder), builder


def _agent_text(builder, text, assertions=()):
    return builder.build(
        EventType.AGENT_TEXT_FINAL,
        source=EventSource.PROVIDER_NORMALIZED,
        payload={"text": text, "assertions": list(assertions)},
    )


def _tool_result(builder):
    return builder.build(
        EventType.TOOL_CALL_RESULT,
        source=EventSource.PROVIDER_NORMALIZED,
        payload={"tool_name": "verify_identity", "status": "succeeded"},
    )


# --- state -------------------------------------------------------------------


def test_state_apply_increments_version_and_records_transition():
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    mutation = state.apply("authentication_state", True)
    assert mutation.previous_value is False
    assert mutation.new_value is True
    assert mutation.state_version == 1
    assert state.state_version == 1


def test_state_apply_supports_nested_paths():
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    state.apply("known_information.country", "IN")
    assert state.known_information["country"] == "IN"


# --- policy ------------------------------------------------------------------


def test_policy_marks_assertions_and_tracks_progress(scenario):
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    policy = PolicyEngine(scenario)
    outcome = policy.observe(
        state, CallerObservation(kind="agent_text", text="done", assertions=["objective_fulfilled"])
    )
    assert outcome.progress is True
    assert policy.satisfied_assertion_ids(state) == {"objective_fulfilled"}
    assert policy.unsatisfied_required(state) == ["authentication_complete"]
    assert policy.required_assertions_satisfied(state) is False


def test_policy_tool_result_sets_authentication(scenario):
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    outcome = PolicyEngine(scenario).observe(
        state, CallerObservation(kind="tool_result", tool_name="verify", tool_status="succeeded")
    )
    assert state.authentication_state is True
    assert outcome.progress is True


def test_policy_records_recovery_and_reports_exhaustion(scenario):
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    policy = PolicyEngine(scenario)
    _, exhausted_first = policy.record_recovery(state)
    _, exhausted_second = policy.record_recovery(state)
    assert exhausted_first is False
    assert exhausted_second is True


# --- actions / language ------------------------------------------------------


def test_action_selector_prefers_acknowledgement_then_end():
    selector = ActionSelector()
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    # Opening turn states the problem.
    assert selector.select(state, required_satisfied=False) == "present_problem"

    state.turn_count = 1
    state.authentication_state = True
    # Objective met but not yet acknowledged -> acknowledge first.
    assert selector.select(state, required_satisfied=True) == "acknowledge_resolution"

    state.acknowledged = True
    assert selector.select(state, required_satisfied=True) == "end_call"


def test_action_selector_requests_recovery_and_information():
    selector = ActionSelector()
    state = ScenarioState.initial(
        facts={}, user_goal="g", initial_state={}, allowed_actions=[]
    )
    state.turn_count = 1
    assert selector.select(state, required_satisfied=False) == "provide_information"
    state.authentication_state = True
    assert (
        selector.select(state, required_satisfied=False, recovery_requested=True)
        == "recover"
    )


def test_language_controller_code_switches_deterministically():
    controller = LanguageController(primary="en-IN", secondary="hi-IN", code_switch=True)
    assert controller.language_for_turn(0) == "en-IN"
    assert controller.language_for_turn(1) == "hi-IN"
    language, text = controller.realize("present_problem", turn_index=0)
    assert language == "en-IN" and text


def test_language_controller_uses_facts_for_templates():
    controller = LanguageController(primary="en-IN")
    _, text = controller.realize(
        "provide_information", turn_index=0, facts={"account_id": "AC-9"}
    )
    assert "AC-9" in text


# --- controller --------------------------------------------------------------


async def test_controller_opens_with_present_problem(scenario):
    controller, builder = _controller(scenario)
    start = await controller.start()
    assert start.events[0].type == EventType.CALLER_STATE_INITIALIZED.value

    step = await controller.observe_agent_event(None, [_agent_text(builder, "Hello")])
    assert step.action == "present_problem"
    assert step.audio  # caller spoke
    assert step.turn_id is not None


async def test_controller_reaches_natural_success(scenario):
    controller, builder = _controller(scenario)
    await controller.start()

    await controller.observe_agent_event(None, [_agent_text(builder, "Hello")])
    await controller.observe_agent_event(
        None, [_agent_text(builder, "Please verify"), _tool_result(builder)]
    )
    step = await controller.observe_agent_event(
        None,
        [
            _agent_text(
                builder,
                "All done",
                assertions=["authentication_complete", "objective_fulfilled"],
            )
        ],
    )
    assert step.terminal is True
    assert step.terminal_reason == "NATURAL_SUCCESS"
    assert controller.state.acknowledged is True


async def test_controller_emits_state_mutation_events(scenario):
    controller, builder = _controller(scenario)
    await controller.start()
    step = await controller.observe_agent_event(
        None, [_agent_text(builder, "Verified", assertions=["authentication_complete"])]
    )
    mutated = [e for e in step.events if e.type == EventType.CALLER_STATE_MUTATED.value]
    assert mutated
    payload = mutated[0].payload
    assert {"state_path", "previous", "new", "state_version"} <= set(payload)


async def test_controller_stops_cleanly(scenario):
    controller, _ = _controller(scenario)
    await controller.start()
    await controller.stop()
