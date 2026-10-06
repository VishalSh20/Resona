# VoiceEval Agentic / GenAI Workflow Design
## LangChain + LangGraph + Provider Abstraction + Jev

> **Implementation spec for Codex**
>
> The attached `voiceeval_domain_schema_v0.4.md` is the source of truth for the persisted VoiceEval domain model. Do not silently change, reinterpret, or replace that schema while implementing these workflows.

---

# 0. Critical implementation instruction

This document describes **two different workflows**.

They are **NOT one combined pipeline** and should not be implemented as one generic "evaluation generation agent".

## Workflow A — `get_simulation_preferences`

This runs **first** and is intentionally smaller/basic.

Its job is:

> Given the Simulation description plus all available metrics and caller personalities, determine which metrics and personalities are useful enough to include in the Simulation's evaluation space.

It returns:

```text
selected metrics
selected personalities
```

It does **not** generate concrete evaluators or concrete scenarios.

---

## Workflow B — `get_evaluations`

This is the **core workflow / heart of the system**.

Its job is:

> Given the whole Simulation object and a detailed Simulation workflow, design concrete caller profiles, select the most useful profiles, create scenarios for them, determine which metrics those scenarios can actually measure, and generate the judge-facing expected-output prompt.

Its output is:

```text
RunEvaluator[]
```

A `RunEvaluator` is the concrete scenario that belongs to a Run and contains:

- scenario
- expected_output_prompt
- selected metrics
- languages
- background
- personality

This distinction follows the domain schema: Simulation defines the reusable evaluation space, while RunEvaluator is the concrete caller/scenario inside a Run.

---

# 1. Source-of-truth domain model

The domain hierarchy is:

```text
Simulation
    ↓ instantiates
Run
    ↓ contains
RunEvaluator
    ↓ repeats as
CallRun
    ↓ physically executes
CallAttempt
```

The important semantic distinction is:

```text
Simulation  = reusable evaluation space
Run         = one concrete instantiation/execution
RunEvaluator = one concrete caller scenario
CallRun     = one logical repetition
CallAttempt = one physical execution attempt
```

Do not introduce the removed evaluator revision hierarchy:

```text
Evaluator
EvaluatorRevision
EvaluationPlan
EvaluationPlanItem
```

The schema explicitly removes that model.

---

# 2. High-level system architecture

Use LangGraph to orchestrate a **structured state graph**, not a free-running ReAct-style agent.

```text
                         ┌─────────────────────────┐
                         │     Workflow Layer      │
                         │       LangGraph         │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
             Generation / Reasoning                Decisioning
                    │                                   │
             ┌──────▼─────────┐                   ┌─────▼─────┐
             │ LLM Gateway    │                   │    Jev    │
             └──────┬─────────┘                   └───────────┘
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
       OpenAI   Anthropic  OpenRouter
```

The responsibilities are intentionally separated:

```text
LLM
    → understands semantics
    → extracts intent
    → generates candidates
    → generates scenarios
    → generates judge instructions

Jev
    → makes bounded decisions over candidates
    → ranks/selects
    → answers decision questions

Deterministic application code
    → schema validation
    → subset checks
    → allowed-value checks
    → deduplication
    → coverage calculations
    → diversity optimization
    → mandatory metric enforcement

LangGraph
    → orchestration
    → sequencing
    → fan-out/fan-in
    → conditional routing
    → retries / repair loops
    → state management
```

### Important

Do **not** make one LLM decide everything.

Do **not** make Jev generate free-form prose.

Do **not** use an LLM for deterministic schema constraints.

---

# 3. Provider abstraction

Keep the provider abstraction thin and provider-specific details out of graph nodes.

Supported generation providers:

```text
OpenAI
Anthropic
OpenRouter
```

Decisioning provider:

```text
Jev
```

Conceptually:

```python
class GenerationModel(Protocol):
    async def generate(...): ...
    async def structured(...): ...


class DecisionModel(Protocol):
    async def decide(...): ...
    async def rank(...): ...
```

Then have implementations such as:

```text
OpenAIProvider
AnthropicProvider
OpenRouterProvider

JevDecisionModel
```

Graph nodes should not contain provider branching such as:

```python
if provider == "openai":
    ...
elif provider == "anthropic":
    ...
```

Put that behind a model factory / gateway.

---

# 4. Structured output is mandatory for generative nodes

Do not rely on parsing arbitrary prose from LLMs.

Use Pydantic / typed structured output for every important intermediate artifact.

Examples:

```python
class EvaluationIntent(BaseModel):
    objectives: list[str]
    behavioral_requirements: list[str]
    failure_modes: list[str]
    task_characteristics: list[str]
    language_requirements: list[str]
    caller_stressors: list[str]
    knowledge_dependence: str
    temporal_sensitivity: str
    ambiguity_flags: list[str]
```

Similar typed models should exist for:

```text
metric applicability
personality applicability
caller profile
scenario candidate
metric opportunity
judge prompt specification
validation result
```

The graph should consume typed objects, not fragile text.

---

# 5. Metric Registry

Before implementing the workflows, create/use a machine-readable metric registry.

Do not provide the LLM only with metric names such as:

```text
relevancy
empathy
task_completion
```

Each metric should have enough metadata to reason about applicability.

Conceptual structure:

```python
class MetricSpec(BaseModel):
    key: str
    family: str

    measurement_type: Literal[
        "instrumented",
        "judge",
        "hybrid"
    ]

    required_signals: list[str]

    relevant_behaviors: list[str]
    relevant_task_types: list[str]
    relevant_caller_traits: list[str]
    relevant_language_properties: list[str]

    evidence_sources: list[str]

    universal: bool = False
    cost_weight: float = 1.0
```

The registry is the canonical definition of what a metric means.

The LLM must not redefine metric semantics every time.

The scenario may expose a metric.

The metric registry defines what the metric means.

---

# 6. Personality Registry

Similarly, personality should have machine-readable semantics.

The domain schema models personality as composable enum values.

Example:

```text
SUPPORTIVE
CONCISE
VERBOSE
ABUSIVE
INTERRUPTOR
IMPATIENT
CONFUSED
SKEPTICAL
COOPERATIVE
UNCOOPERATIVE
HESITANT
REPETITIVE
EMOTIONAL
DEMANDING
```

Represent each trait with metadata such as:

```python
class PersonalitySpec(BaseModel):
    key: str

    behavioral_axes: list[str]
    pressure_signals: list[str]

    metric_affinities: list[str]

    compatible_with: list[str]
    incompatible_with: list[str]
```

Example:

```text
INTERRUPTOR
    behavioral_axes:
        turn_taking
        conversational_pressure

    pressure_signals:
        interrupts agent
        attempts to speak before completion

    metric_affinities:
        barge_in_latency
        barge_in_success_rate
```

The registry should help candidate generation and eliminate nonsensical combinations.

---

# 7. Workflow A — `get_simulation_preferences`

## Goal

Answer:

> "Which dimensions are actually useful for this Simulation?"

It takes:

```text
description
available metrics
available personalities
```

and returns:

```text
selected metrics
selected personalities
```

This workflow is relatively small.

---

## 7.1 Input

Conceptually:

```python
class SimulationPreferenceInput(BaseModel):
    description: str
    available_metrics: list[str]
    available_personalities: list[str]
```

The actual application can pass richer `MetricSpec` and `PersonalitySpec` objects internally.

---

# 8. Preference workflow graph

Recommended structure:

```text
START
  │
  ▼
normalize_input
  │
  ▼
analyze_simulation_intent
  │
  ├──────────────────────┐
  ▼                      ▼
analyze_metrics    analyze_personalities
  │                      │
  └──────────┬───────────┘
             ▼
      identify_ambiguity
             │
             ▼
       hybrid_decision
             │
             ▼
      coverage_optimizer
             │
             ▼
      validate_preferences
             │
             ▼
            END
```

This is intentionally NOT a giant autonomous agent.

---

# 9. Preference node: `normalize_input`

Deterministic.

Responsibilities:

```text
- normalize identifiers
- remove duplicates
- verify candidate keys
- attach MetricSpec / PersonalitySpec metadata
- prepare model input
```

No LLM call should be required.

---

# 10. Preference node: `analyze_simulation_intent`

Use an LLM.

Its job is to understand what the simulation is trying to test.

It should NOT directly produce the final metric/personality selection.

Example input:

```text
"Test whether a Hindi-English banking support agent can handle
blocked-card requests, authentication requirements and frustrated
callers."
```

Expected conceptual output:

```json
{
  "objectives": [
    "resolve blocked card issue",
    "follow authentication policy"
  ],
  "behavioral_requirements": [
    "handle frustrated caller",
    "retain authentication context"
  ],
  "failure_modes": [
    "bypass authentication",
    "invent unsupported information",
    "lose context"
  ],
  "language_requirements": [
    "Hindi",
    "English",
    "code switching"
  ],
  "caller_stressors": [
    "impatience"
  ],
  "knowledge_dependence": "high"
}
```

This is a semantic intermediate representation.

---

# 11. Preference node: metric applicability

For every available metric, reason about whether it is relevant.

But classify first:

```text
OBVIOUSLY_RELEVANT
POSSIBLY_RELEVANT
OBVIOUSLY_IRRELEVANT
```

Example:

```text
"Handle angry customers who interrupt the agent"

task_completion          → obvious
instruction_following    → obvious
hallucination            → obvious
context_retention        → likely
empathy                  → conditional
repetition               → weak
barge_in_success_rate    → relevant if interruption is intentional
```

The point is to avoid blindly running one Jev decision for every metric.

---

# 12. Preference node: personality applicability

Do the analogous semantic analysis for caller personalities.

For example:

```text
INTERRUPTOR → highly relevant
IMPATIENT   → highly relevant
SKEPTICAL   → possibly relevant
SUPPORTIVE  → lower diagnostic value
```

Again, this should be an LLM-assisted semantic analysis, not final selection.

---

# 13. Why the preference workflow is hybrid

A naïve implementation would do:

```text
for each metric:
    ask Jev
```

and:

```text
for each personality:
    ask Jev
```

Do not do that.

Contextual relevance and interaction effects matter.

Instead:

```text
LLM
  ↓
semantic candidate analysis
  ↓
candidate shortlist
  ↓
coverage / redundancy analysis
  ↓
Jev
  ↓
final bounded selection
```

The LLM is better used to understand *why something may matter*.

Jev is better used to make the bounded selection decision.

Deterministic code handles coverage and constraints.

---

# 14. Preference node: candidate generation

Reduce the universe first.

For example:

```text
15 metrics
    ↓
8 potentially useful candidates
```

and:

```text
14 personalities
    ↓
6 potentially useful candidates
```

For every candidate retain metadata such as:

```python
{
    "candidate": "...",
    "relevance": "high",
    "reason": "...",
    "covered_behaviors": [...]
}
```

---

# 15. Preference node: coverage analysis

For each candidate calculate conceptual features:

```text
relevance
coverage
redundancy
interaction_value
```

Personality combinations may provide additional value.

Example:

```text
IMPATIENT
    +
INTERRUPTOR
```

can create a much stronger turn-taking / temporal-pressure test than either trait alone.

Therefore the final selection should not blindly rank individual personality values independently.

---

# 16. Preference node: Jev selection

Now Jev receives the shortlisted candidates and the relevant coverage information.

Conceptually:

```text
candidate set
+
simulation intent
+
coverage information
+
selection constraints
```

Jev decides the final useful subset.

Prefer a bounded set-selection question rather than repeated independent yes/no loops.

Application code remains responsible for the final valid output.

---

# 17. Preference node: final validation

Deterministic:

```text
selected_metrics ⊆ available_metrics
selected_personalities ⊆ available_personalities

no duplicates
valid keys
```

Then return:

```json
{
  "metrics": [...],
  "personalities": [...]
}
```

Optional internal rationale can be retained for observability.

---

# 18. Workflow B — `get_evaluations`

This is the **core workflow**.

It should be designed as a planning system that instantiates the Simulation into concrete RunEvaluators.

The basic idea:

```text
Simulation
+
Detailed Simulation Workflow
        │
        ▼
Understand evaluation space
        │
        ▼
Generate 2N candidate caller profiles
        │
        ▼
Filter / deduplicate / measure diversity
        │
        ▼
Jev selects N
        │
        ▼
Generate multiple scenarios per selected profile
        │
        ▼
Analyze scenario × metric measurability
        │
        ▼
Select best scenario per profile
        │
        ▼
Jev selects exact contextual metrics
        │
        ▼
Generate expected-output judge prompt
        │
        ▼
Validate
        │
        ▼
RunEvaluator[]
```

---

# 19. `get_evaluations` input

Conceptually:

```python
class GetEvaluationsInput(BaseModel):
    simulation: Simulation
    simulation_workflow: SimulationWorkflowSpec
```

Where `SimulationWorkflowSpec` is a planner-level object containing the detailed workflow.

Example:

```python
class SimulationWorkflowSpec(BaseModel):
    objective: str
    task_flow: list[WorkflowStep]
    success_conditions: list[str]
    constraints: list[str]
    failure_modes: list[str]
    knowledge_usage: list[str]
    interaction_requirements: list[str]
```

This does not require changing the persisted domain schema.

---

# 20. Full evaluator graph

Recommended high-level LangGraph:

```text
START
  │
  ▼
validate_simulation
  │
  ▼
analyze_evaluation_space
  │
  ▼
build_profile_coverage_plan
  │
  ▼
generate_2n_profiles
  │
  ▼
deduplicate_and_filter_profiles
  │
  ▼
score_profiles_with_jev
  │
  ▼
select_n_diverse_profiles
  │
  ▼
fan_out_selected_profiles
  │
  ├───────────────────────────────┐
  │                               │
  ▼                               ▼
generate_scenarios          generate_scenarios
for profile 1               for profile 2
  │                               │
  └────────────── ... ────────────┘
                  │
                  ▼
          analyze_scenario_metrics
                  │
                  ▼
          select_best_scenario
                  │
                  ▼
          select_metric_candidates
                  │
                  ▼
          apply_mandatory_metrics
                  │
                  ▼
          jev_select_metrics
                  │
                  ▼
          generate_expected_output_prompt
                  │
                  ▼
          semantic_validate_evaluator
                  │
             ┌────┴────┐
             │         │
            valid     invalid
             │         │
             │         ▼
             │       repair
             │         │
             │       validate
             │         │
             └─────────┘
                  │
                  ▼
          build_run_evaluator
                  │
                  ▼
                 END
```

Use LangGraph fan-out/fan-in for the per-profile work.

---

# 21. Step 1 — `analyze_evaluation_space`

This is the first important LLM reasoning node.

Inputs:

```text
whole Simulation
detailed simulation workflow
allowed languages
allowed backgrounds
allowed personalities
available metrics
knowledge base
evaluator_count
```

Output:

```python
class EvaluationSpaceAnalysis(BaseModel):
    core_behaviors: list[str]
    stress_conditions: list[str]
    language_requirements: list[str]
    knowledge_dependencies: list[str]
    important_interaction_patterns: list[str]
    target_failure_modes: list[str]
```

Example:

```json
{
  "core_behaviors": [
    "authentication compliance",
    "context retention",
    "task resolution"
  ],
  "stress_conditions": [
    "interruption",
    "impatience",
    "ambiguous caller input"
  ],
  "language_requirements": [
    "Hindi-English interaction"
  ],
  "knowledge_dependencies": [
    "policy grounding"
  ]
}
```

This becomes the planning context for downstream candidate generation.

---

# 22. Step 2 — build profile coverage plan

Do not randomly sample:

```text
language × background × personality
```

and do not ask one LLM:

```text
"Generate N diverse users."
```

Instead construct a coverage plan.

Think in axes.

### Language axis

```text
monolingual
bilingual
English dominant
regional-language dominant
code-switching
```

### Background axis

```text
student
working professional
existing customer
technical user
non-technical user
etc.
```

### Personality axis

```text
cooperative
impatient
interrupting
skeptical
confused
emotional
demanding
etc.
```

Then map these axes against the evaluation goals.

The objective is not maximum combinatorial variety.

The objective is **maximum diagnostic coverage**.

---

# 23. Step 3 — Generate 2N candidate profiles

The unit being generated is:

```text
CallerProfile
    language(s)
    background
    personality
```

Language must preserve major/minor semantics.

Example:

```json
{
  "major": "hi",
  "minor": "en"
}
```

or:

```json
{
  "major": "en",
  "minor": null
}
```

A profile:

```text
language profile
+
one background
+
one or more personality traits
```

must always use only values allowed by the Simulation.

---

# 24. Do not generate 2N candidates in one homogeneous prompt

Use several generation objectives / passes where useful.

Conceptually:

```text
Pass A
    language-diverse candidates

Pass B
    personality-diverse candidates

Pass C
    background-diverse candidates

Pass D
    high-risk / diagnostically interesting combinations
```

Merge the results.

This reduces mode collapse where an LLM keeps generating almost identical "impatient English customer" profiles.

---

# 25. Candidate profile structure

Example:

```python
class CallerProfile(BaseModel):
    major_language: str
    minor_language: str | None

    background: str
    personality: list[str]

    rationale: str
    targeted_behaviors: list[str]
```

Do not persist this directly as the final RunEvaluator yet.

It is an intermediate planning artifact.

---

# 26. Candidate profile validation

Before Jev:

```text
language values valid
background valid
personality values valid

1 <= language count <= 2

if two languages:
    major != minor

personality combination is not contradictory
```

Also canonicalize:

```text
["IMPATIENT", "INTERRUPTOR"]
```

and:

```text
["INTERRUPTOR", "IMPATIENT"]
```

into the same canonical representation for deduplication.

Do NOT canonicalize major/minor language order because major/minor has semantic meaning.

---

# 27. Profile deduplication and diversity features

Compute deterministic features:

```text
language coverage
background coverage
personality coverage
pairwise profile similarity
behavioral coverage
```

Then retain approximately:

```text
2N meaningful candidate profiles
```

If generation produces fewer than 2N valid candidates, retry the generation stage with the missing coverage dimensions.

Do not silently accept poor diversity.

---

# 28. Step 4 — Jev profile selection

Now use Jev for the actual bounded decision.

Input:

```text
2N candidate profiles
+
evaluation space analysis
+
coverage features
+
Simulation constraints
```

Objective:

```text
select exactly N profiles that maximize:
    diagnostic relevance
    behavioral diversity
    language diversity
    background diversity
    coverage
```

while minimizing:

```text
redundancy
```

This is the correct role of Jev.

Do not simply:

```python
sort_by_jev_score()
take_first_n()
```

because that can choose five nearly identical highly-scored personas.

Instead use:

```text
Jev relevance
+
deterministic marginal coverage
-
similarity to already-selected profiles
```

A greedy diversity-aware selection algorithm is sufficient for the first implementation.

---

# 29. Step 5 — fan out over selected profiles

Once N profiles are selected:

```text
profile 1
profile 2
profile 3
...
profile N
```

become independent planning branches.

Each branch generates several scenario candidates.

Use LangGraph `Send` / map-reduce style orchestration here.

Conceptually:

```text
Selected Profiles
       │
       ├──→ Scenario generation → Profile 1
       ├──→ Scenario generation → Profile 2
       ├──→ Scenario generation → Profile 3
       └──→ Scenario generation → Profile N
```

This section is a major reason to use LangGraph rather than a plain sequential chain.

---

# 30. Step 6 — generate multiple scenarios per profile

Do NOT generate only one scenario.

Generate a small candidate set, e.g.:

```text
3–5 scenarios per selected profile
```

The exact number should be configurable.

Each scenario should be a realistic interaction, not a synthetic "metric checklist".

---

# 31. Scenario generation principle

The generation order matters.

Prefer:

```text
Simulation objective
+
workflow
+
caller profile
        ↓
realistic scenario
        ↓
identify measurable behaviors
```

Avoid:

```text
metric
        ↓
manufactured scenario
```

The metric should influence scenario utility analysis, but it should not force the model to create an obviously artificial conversation.

---

# 32. Scenario structure

The schema expects the scenario to contain:

```text
scenario context
caller instructions
how the caller should communicate
underlying problem
conversation goal
behavioral constraints
```

Use a typed structure:

```python
class ScenarioCandidate(BaseModel):
    title: str

    context: str
    caller_instructions: str
    communication_behavior: str
    underlying_problem: str
    conversation_goal: str

    behavioral_constraints: list[str]

    required_knowledge: list[str]
    expected_agent_behaviors: list[str]

    metric_opportunities: list["MetricOpportunity"]
```

---

# 33. Metric opportunity model

Do not have the scenario generator merely output:

```json
{
  "metrics": [
    "empathy",
    "task_completion"
  ]
}
```

Instead require:

```python
class MetricOpportunity(BaseModel):
    metric: str

    measurability: Literal[
        "primary",
        "secondary",
        "incidental",
        "not_measurable"
    ]

    observable_behavior: str
    evidence_source: list[str]
```

Example:

```json
{
  "metric": "context_retention",
  "measurability": "primary",
  "observable_behavior": "The agent must remember authentication information provided earlier.",
  "evidence_source": ["turn"]
}
```

This creates a useful scenario × metric evidence matrix.

---

# 34. Step 7 — scenario × metric analysis

For each candidate scenario calculate:

```text
metric coverage
measurement strength
task relevance
behavioral authenticity
evidence quality
profile alignment
redundancy
```

A scenario that nominally touches 8 metrics is not necessarily better than one that cleanly measures 4.

Measurement strength matters.

Conceptually:

```text
scenario_score =
      metric_coverage
    + measurement_strength
    + task_relevance
    + behavioral_authenticity
    + evidence_quality
    - redundancy
```

The exact weighting should live in configuration, not hidden in prompts.

---

# 35. Step 8 — select the best scenario

Use deterministic scoring for obvious cases.

Use Jev as a bounded tie-breaker / final comparator where scenarios are semantically close.

Example:

```text
Scenario A
    strong task completion
    medium context retention
    weak empathy

Scenario B
    strong task completion
    strong context retention
    strong empathy

Scenario C
    strong language behavior
    weak task measurement
```

Jev should compare the shortlisted scenarios against the actual simulation objective.

It should NOT generate another scenario at this stage.

---

# 36. Step 9 — precise metric selection

Now the selected scenario is fixed.

For each evaluator:

```text
selected scenario
+
available Simulation metrics
+
metric registry
+
metric opportunities
```

produce metric candidates and then let Jev decide the contextual metrics.

The process is:

```text
scenario
    ↓
metric applicability analysis
    ↓
candidate metric subset
    ↓
mandatory metrics
    ↓
Jev precise selection
    ↓
final evaluator metric set
```

---

# 37. Mandatory metrics

Mandatory instrumentation should NEVER depend on the LLM.

Define an explicit policy:

```python
class MetricPolicy(BaseModel):
    mandatory_metrics: list[str]
    minimum_metrics_per_evaluator: int
    maximum_metrics_per_evaluator: int
```

Then:

```text
final_metrics =
    mandatory_metrics
    ∪ Jev_selected_contextual_metrics
```

with:

```text
final_metrics ⊆ simulation.metric_set
```

Important:

The current metric list supplied for this implementation contains:

```text
LATENCY & TURN-TAKING
    TTFA
    TTFT
    Barge-in Latency
    Barge-in Success Rate

CONVERSATION QUALITY
    Relevancy
    Context Retention
    Repetition
    Instruction Following
    Empathy

TASK & KNOWLEDGE QUALITY
    Task Completion
    Hallucination
    Knowledge Base Groundedness

LANGUAGE QUALITY
    Language Detection Accuracy
    Code-Switching Accuracy
    Semantic Preservation
    Language Consistency
```

There is not currently a separately named "audio quality" metric in that supplied list.

Therefore:

```text
support mandatory audio-quality metrics in the architecture,
but do not invent metric keys that do not exist in the Simulation
metric_set / metric registry.
```

If audio-quality metrics are added later, they can be added to the mandatory metric policy.

---

# 38. Step 10 — generate expected-output prompt

This is a separate LLM node from scenario generation.

The semantic distinction is:

```text
scenario
    = instructions for the synthetic caller

expected_output_prompt
    = instructions for the evaluator/judge
```

The schema explicitly keeps them separate.

Inputs:

```text
Simulation objective
selected scenario
selected metrics
metric definitions
knowledge base
expected agent behavior
```

Generate a structured judge specification first:

```python
class JudgePromptSpec(BaseModel):
    objective: str

    expected_agent_behavior: list[str]

    metric_expectations: list["MetricExpectation"]

    evidence_requirements: list[str]

    prohibited_assumptions: list[str]

    outcome_definition: str
```

Then render it into the final:

```text
expected_output_prompt
```

---

# 39. MetricExpectation

Example:

```python
class MetricExpectation(BaseModel):
    metric: str
    what_to_evaluate: str
    pass_condition: str
    failure_condition: str
    evidence_to_consider: list[str]
```

For hallucination:

```text
what_to_evaluate:
    Whether the agent introduces unsupported factual information.

pass_condition:
    The agent stays within available information or communicates uncertainty.

failure_condition:
    The agent invents unsupported account, policy, or action information.

evidence:
    relevant conversation turns
    knowledge-base evidence
```

The prompt generator should use the canonical metric definitions.

It must not redefine what a metric means.

---

# 40. Scenario vs metric vs judge responsibilities

Keep these boundaries strict.

```text
Metric Registry
    = canonical meaning of metric

Scenario
    = what actually happens in this synthetic interaction

Expected Output Prompt
    = what the judge must inspect in this specific interaction
```

Do not allow:

```text
LLM invents metric semantics
```

during evaluator generation.

---

# 41. Step 11 — semantic validation

After building a candidate RunEvaluator, validate it.

## Deterministic validation

Must check:

```text
scenario is non-empty
expected_output_prompt is non-empty

1 <= number of languages <= 2

if two languages:
    major/minor are distinct

background ∈ simulation.backgrounds

personality ⊆ simulation.personalities

metrics ⊆ simulation.metric_set
```

Also ensure:

```text
evaluator_count is respected
```

---

## Semantic validation

Optionally use an LLM / Jev check to detect:

```text
scenario does not actually reflect selected personality
scenario does not use selected language profile correctly
selected metrics are not genuinely measurable
judge prompt is inconsistent with scenario
scenario violates Simulation workflow constraints
```

Do this only after deterministic validation.

---

# 42. Repair loop

Validation failure should not cause an uncontrolled agent loop.

Recommended:

```text
generate
  ↓
validate
  ├── valid → continue
  │
  └── invalid
        ↓
      repair
        ↓
      validate
        ↓
      valid
```

Allow one repair pass initially.

At most a small configurable number of retries should exist.

If still invalid:

```text
return structured failure
```

Do not silently manufacture a result.

---

# 43. LangGraph state

Graph state should be orchestration state, not a mirror of database tables.

A conceptual state:

```python
class EvaluationGenerationState(TypedDict):
    simulation: Simulation
    simulation_workflow: SimulationWorkflowSpec

    evaluation_analysis: EvaluationSpaceAnalysis

    profile_candidates: list[CallerProfile]
    selected_profiles: list[CallerProfile]

    evaluator_states: list[EvaluatorPlanningState]

    generated_evaluators: list[RunEvaluator]

    errors: list[str]
```

Per-evaluator state:

```python
class EvaluatorPlanningState(BaseModel):
    profile: CallerProfile

    scenario_candidates: list[ScenarioCandidate]
    selected_scenario: ScenarioCandidate | None

    metric_candidates: list[MetricCandidate]
    selected_metrics: list[str]

    judge_prompt_spec: JudgePromptSpec | None
    expected_output_prompt: str | None

    validation: ValidationResult | None
```

Do not make one giant flat state full of every intermediate field if it makes branching difficult.

---

# 44. Suggested node boundaries

Use explicit graph nodes such as:

```text
get_simulation_preferences
    normalize_input
    analyze_simulation_intent
    analyze_metric_applicability
    analyze_personality_applicability
    build_preference_candidates
    resolve_preference_selection
    validate_preferences


get_evaluations
    validate_simulation
    analyze_evaluation_space
    build_profile_coverage_plan
    generate_profile_candidates
    deduplicate_profiles
    score_profiles_with_jev
    select_diverse_profiles
    generate_scenarios
    analyze_scenario_metric_opportunities
    select_best_scenario
    build_metric_candidates
    apply_mandatory_metrics
    select_metrics_with_jev
    generate_judge_prompt
    validate_evaluator
    repair_evaluator
    build_run_evaluator
```

Node names do not have to be exact, but keep the semantic separation.

---

# 45. Important implementation rule: graph state != persisted schema

The domain schema says the final RunEvaluator has fields such as:

```text
scenario
expected_output_prompt
metrics
languages
background
personality
```

Do not persist every hidden planning artifact there.

Intermediate things such as:

```text
profile score
candidate alternatives
coverage calculations
LLM rationale
Jev decisions
scenario candidates
```

should remain workflow/tracing metadata unless there is an explicit domain requirement to persist them.

The final domain object should stay clean.

---

# 46. Observability / debugging

The most useful debugging questions will be:

```text
Why was this profile generated?
Why was this profile selected?
Why was this scenario selected?
Why was this metric selected?
Why was this evaluator repaired?
Why did validation fail?
```

Therefore retain structured internal metadata during workflow execution.

Example:

```json
{
  "decision_model": "jev",
  "model_provider": "anthropic",
  "model": "...",
  "selection_reason": "...",
  "coverage": {
    "turn_taking": 0.94,
    "task": 0.88,
    "language": 0.73
  },
  "alternatives_considered": [...]
}
```

This can live in traces / workflow execution metadata rather than the core RunEvaluator schema.

---

# 47. Exact responsibility matrix

| Responsibility | LLM | Jev | Deterministic Code |
|---|---:|---:|---:|
| Understand simulation | YES | NO | NO |
| Extract evaluation intent | YES | NO | NO |
| Explain metric applicability | YES | NO | NO |
| Explain personality applicability | YES | NO | NO |
| Generate profile candidates | YES | NO | NO |
| Generate scenarios | YES | NO | NO |
| Generate judge prompt | YES | NO | NO |
| Select useful metrics | SUPPORT | YES | YES for constraints |
| Select useful personalities | SUPPORT | YES | YES for constraints |
| Select N profiles | SUPPORT | YES | YES for diversity |
| Compare scenarios | SUPPORT | YES | YES for scoring |
| Select contextual metrics | SUPPORT | YES | YES for mandatory rules |
| Deduplicate | NO | NO | YES |
| Validate schema | NO | NO | YES |
| Validate subset membership | NO | NO | YES |
| Enforce language count | NO | NO | YES |
| Enforce mandatory metrics | NO | NO | YES |
| Enforce evaluator count | NO | NO | YES |

"SUPPORT" means the LLM produces semantic signals that help the decision; it does not own the final correctness constraint.

---

# 48. Do not make these mistakes

## Mistake 1

```text
One giant agent:
"Generate evaluators."
```

Do not do this.

---

## Mistake 2

```text
Jev(metric1)
Jev(metric2)
Jev(metric3)
...
```

and call that intelligent selection.

Use candidate generation + contextual decision + coverage.

---

## Mistake 3

```text
sort Jev scores
take top N
```

without diversity.

This creates correlated evaluators.

---

## Mistake 4

Generating scenarios directly from metric names.

This produces artificial benchmark-looking conversations.

Generate realistic scenarios first, then identify what they measure.

---

## Mistake 5

Letting an LLM decide mandatory metrics.

Mandatory instrumentation belongs in configuration/application code.

---

## Mistake 6

Letting LLMs bypass Simulation membership constraints.

No generated:

```text
language
background
personality
metric
```

may escape the Simulation's allowed sets.

---

## Mistake 7

Using generated prose as the internal contract.

Use typed structured outputs.

---

## Mistake 8

Letting provider-specific APIs leak into graph nodes.

All generation should go through the provider abstraction.

---

## Mistake 9

Creating uncontrolled retry loops.

Every repair path must have an explicit bounded retry count.

---

# 49. Recommended implementation philosophy

The system should behave like:

```text
                 semantic search / synthesis
LLM  ────────────────────────────────────────────►
                    candidate space


                 bounded decisions
Jev  ────────────────────────────────────────────►
                    selection


                 hard guarantees
Code ────────────────────────────────────────────►
                    correctness


                 orchestration
LangGraph ───────────────────────────────────────►
                    execution flow
```

This gives you an agentic system without making the whole thing unpredictable.

---

# 50. Final architecture

## `get_simulation_preferences`

```text
Input:
    description
    all available metrics
    all available personalities

        ↓

intent analysis
        ↓
semantic applicability analysis
        ↓
candidate shortlist
        ↓
coverage / interaction analysis
        ↓
Jev bounded selection
        ↓
deterministic validation

Output:
    selected metrics
    selected personalities
```

This workflow is **small/basic**.

---

## `get_evaluations`

```text
Input:
    whole Simulation
    detailed Simulation workflow

        ↓

analyze evaluation space
        ↓
build diversity / coverage plan
        ↓
generate 2N profile candidates
        ↓
validate + deduplicate
        ↓
Jev scoring / selection
        ↓
diversity-aware N selection
        ↓

       FAN OUT
          │
          ├── profile 1
          ├── profile 2
          ├── profile 3
          └── profile N
               │
               ▼
       generate multiple scenarios
               │
               ▼
       scenario × metric analysis
               │
               ▼
       select best scenario
               │
               ▼
       metric candidate generation
               │
               ▼
       mandatory metrics
               │
               ▼
       Jev precise metric selection
               │
               ▼
       expected-output prompt generation
               │
               ▼
       deterministic + semantic validation
               │
               ▼
       bounded repair if required
               │
               ▼

Output:
    RunEvaluator[]
```

---

# 51. Codex execution rules

These rules are important.

## Rule 1 — Do not guess architecture when a requirement is ambiguous

If something in the existing codebase, schema, interfaces, database layer, model configuration, or Jev integration is unclear:

**STOP and ASK ME.**

Do not invent a compatibility layer just because it is convenient.

---

## Rule 2 — Inspect the repository before modifying code

Before implementing:

```text
find existing workflow code
find existing LangChain setup
find LangGraph setup
find provider abstractions
find Jev client/integration
find Pydantic/domain models
find existing metric registry
find existing personality definitions
find tests
```

Reuse existing abstractions where appropriate.

Do not create duplicate model/provider abstractions blindly.

---

## Rule 3 — Preserve existing domain boundaries

Do not introduce:

```text
EvaluatorRevision
EvaluationPlan
EvaluationPlanItem
```

into the new execution path.

The domain model is:

```text
Simulation
    ↓
Run
    ↓
RunEvaluator
```

---

## Rule 4 — Ask before making a semantic assumption

Examples of things that require asking if unclear:

```text
- exact Jev API/interface
- Jev score semantics
- model configuration conventions
- provider configuration structure
- how Simulation workflow is represented in the codebase
- mandatory metric policy location
- expected persistence behavior
- existing LangGraph conventions
- tracing/observability conventions
- whether an intermediate artifact should be persisted
- exact retry policy if not already defined
```

Do not silently choose one and pretend it was specified.

---

## Rule 5 — Prefer the smallest change that fits the architecture

Do not rewrite unrelated code.

Do not replace existing infrastructure without evidence that it is necessary.

Implement the new graph around existing project conventions.

---

## Rule 6 — Keep the workflows separate

Do not merge:

```text
get_simulation_preferences
```

and:

```text
get_evaluations
```

into one graph.

They have different responsibilities, complexity, and inputs/outputs.

---

## Rule 7 — The evaluator workflow is the core

Spend most design/implementation effort on:

```text
profile generation
profile selection
diversity
scenario generation
scenario quality
scenario-metric measurability
metric selection
judge prompt generation
validation
```

Do not over-engineer the smaller preference workflow while under-engineering evaluator generation.

---

## Rule 8 — Ask the user rather than hallucinating missing requirements

This is an explicit instruction:

> **Whenever you are confused, encounter an ambiguity, find an underspecified interface, or discover that an implementation decision materially affects behavior, fucking ask me instead of guessing.**

A short clarification question is preferable to implementing the wrong architecture.

---

# 52. First implementation order

Implement in this order:

```text
1. inspect existing repository architecture
2. identify/reuse model abstraction
3. identify/reuse Jev integration
4. identify metric registry / personality registry
5. implement get_simulation_preferences
6. write tests for preference selection
7. implement evaluator planning state/types
8. implement evaluation-space analysis
9. implement 2N profile generation
10. implement profile validation/deduplication
11. implement Jev profile selection
12. implement diversity-aware N selection
13. implement per-profile scenario generation
14. implement scenario × metric opportunity analysis
15. implement scenario selection
16. implement precise metric selection
17. implement expected-output prompt generation
18. implement semantic/deterministic validation
19. implement bounded repair
20. end-to-end tests
```

Do not start by writing one huge `get_evaluations()` function.

Build the graph as composable typed nodes.

---

# 53. Tests that should exist

At minimum test:

```text
Preference workflow:
    obvious metric
    ambiguous metric
    irrelevant metric
    personality interaction
    empty candidates
    invalid candidate keys

Profile generation:
    exactly 2N candidate target
    valid language constraints
    major/minor semantics
    valid background
    valid personality subsets
    duplicate removal
    contradictory personality combinations

Profile selection:
    Jev selection
    diversity preservation
    exact N output
    insufficient candidate fallback

Scenario generation:
    multiple candidates per profile
    scenario structure completeness
    metric opportunity structure
    profile alignment

Metric selection:
    mandatory metrics retained
    contextual metrics selected by Jev
    invalid metrics rejected
    subset constraint enforced

Judge prompt:
    selected metrics represented
    scenario represented
    expected behavior represented
    no invented metric semantics

Validation:
    malformed evaluator rejected
    repair path
    bounded retries
    final failure returned explicitly
```

---

# 54. Non-negotiable output quality principles

The generated evaluator set should optimize for:

```text
diagnostic value
coverage
diversity
realism
measurability
```

not:

```text
maximum number of metrics
maximum personality combinations
maximum prompt complexity
maximum LLM calls
```

A good evaluation set is one where every evaluator has a reason to exist.

---

# 55. Bottom line

The architecture should preserve this separation:

```text
                 GET_SIMULATION_PREFERENCES
                 ──────────────────────────
                   "What matters here?"
                           │
                           ▼
                    useful dimensions


                 GET_EVALUATIONS
                 ───────────────
                "What should we run?"
                           │
                           ▼
                    concrete callers
                           +
                      scenarios
                           +
                      exact metrics
                           +
                    judge prompts
```

And the core implementation philosophy is:

```text
LLM
    → semantic understanding + generation

Jev
    → bounded, contextual decisioning

Deterministic code
    → constraints + coverage + correctness

LangGraph
    → orchestration + parallelism + bounded control flow
```

**Do not turn this into a single autonomous agent.**
It should be an explicit, inspectable planning graph whose individual nodes may be agentic/GenAI-powered.

And again:

> **If anything in the repository or requirements is unclear, ask me. Do not guess and build an entire abstraction around an assumption.**
