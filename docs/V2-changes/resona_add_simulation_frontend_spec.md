# Resona — Add Simulation Frontend Specification

## 1. Purpose

This document is the implementation specification for the **Add Simulation** flow in Resona.

The Excalidraw designs are the visual source of truth for the rough layout and flow. The frontend implementation should turn them into a polished, production-quality UI without changing the intended information architecture.

### Core flow

```text
Add Simulation
      ↓
Page 1 — Target + Test Description
      ↓
Page 2 — Evaluator Count + Languages + Call Ambience
      ↓
Backend preference generation
      ↓
Loading / Preference Generation State
      ↓
Page 3 — Personas
      ↓
Page 4 — Metrics
      ↓
Review
      ↓
Evaluators
```

The existing **Review** and **Evaluators** pages should remain visually/functionally consistent with their current implementation.

---

# 2. Global UI / Layout Requirements

## 2.1 Screen-size safety

The UI MUST NOT create a page that overflows the viewport horizontally or vertically.

### Requirements

- The main application viewport should remain within `100vw`.
- No fixed-width form container should exceed the available viewport width.
- Long forms must scroll vertically inside the appropriate page/content area.
- On smaller screens, content should stack instead of causing horizontal overflow.
- Cards, grids, chips and option groups must wrap naturally.
- Text must be allowed to wrap where necessary.
- Avoid hardcoded heights for the overall form.
- Use `min-height` rather than fixed `height` for major page containers where possible.
- Buttons must remain reachable when the form is long.
- The primary navigation/footer area should remain usable even when content exceeds viewport height.

### Recommended structure

```text
Application viewport
└── Simulation Form Shell
    ├── Header / Step indicator
    ├── Scrollable Content Area
    │   └── Page content
    └── Navigation / Actions
```

The content area should be the scrolling region rather than allowing the entire application to become awkwardly oversized.

---

# 3. Selection State — IMPORTANT DESIGN CHANGE

This applies to:

- Languages
- Personas
- Metrics
- Any other multi-select option cards/chips in the Add Simulation flow

## Current behavior

Selected options currently change their background color.

## New behavior

**Do NOT use a filled/background-color change as the primary selected state.**

Instead, selected items should retain their normal background and receive a **clear, attractive selection border**.

Example:

```text
Normal:

┌──────────────────────┐
│  English             │
└──────────────────────┘


Selected:

╔══════════════════════╗
║  English          ✓  ║
╚══════════════════════╝
```

### Selection styling

Use:

- Slightly stronger border
- Optional subtle ring/glow
- Small check icon on the selected item
- Preserve the original background color
- Smooth transition

Recommended visual treatment:

```css
border: 1.5px solid <accent>;
box-shadow: 0 0 0 1px <accent-subtle>;
```

Do not make the selected card look like a completely different filled button.

### Interaction

- Entire option card should be clickable.
- Keyboard accessible.
- Selected state should be visually obvious without relying only on color.
- Hover and selected states should not conflict.
- Use `aria-selected` / appropriate semantic attributes where applicable.

---

# 4. Icon Strategy

## Primary UI icon library

Use **Lucide / lucide-react** for generic UI icons.

This should be the default source for:

- ArrowRight
- ArrowLeft
- Check
- ChevronDown
- ChevronUp
- Plus
- Sparkles
- Loader / LoaderCircle
- Globe / Languages
- Volume2
- Mic
- Users
- Target
- SlidersHorizontal
- WandSparkles
- Info
- AlertCircle

Do not manually draw generic SVG icons unless there is a specific design requirement.

## Provider icons / logos

For voice-agent providers, use their **official brand/logo SVGs** where available.

Providers:

- ElevenLabs
- Vapi
- Retell
- LiveKit
- Pipecat

Do not use generic icons as a substitute when a recognizable provider logo is available.

If an official logo asset is not available in the existing codebase:

1. Prefer a maintained brand-icon source such as Simple Icons.
2. Otherwise use a clean generic voice/agent icon.
3. Do not create fake provider logos.

Provider logos should be visually consistent in size, generally around `20–24px`.

## Language icons

Do **not** rely on country flags as the primary language representation.

Reason:

- Hinglish does not map cleanly to one country flag.
- Languages such as English are spoken across many countries.
- A flag can incorrectly imply country rather than language.

Prefer:

- `Languages` / `Globe2` icon
- Language label
- Optional short language code

Example:

```text
┌─────────────────┐
│  EN             │
│  English        │
└─────────────────┘
```

For a polished UI, language cards can use small typographic language codes rather than flags.

---

# 5. Page 1 — Target + Test Description

## Purpose

Collect the minimum information required to understand:

1. Which voice agent is being tested.
2. Which version of that agent is being tested.
3. What the user wants Resona to test.

### Page heading

```text
New Simulation
```

Supporting copy should explain that the description helps Resona generate useful evaluators/personas and test scenarios.

Example:

```text
Describe what you want to test so Resona can generate relevant evaluators.
```

---

## 5.1 Select Target

Create a clearly separated section:

```text
Select Target
```

### Agent selector

The user selects the target agent.

The selector should support the available providers:

- ElevenLabs
- Vapi
- Retell
- LiveKit
- Pipecat

Provider identity should be visible in the option/card.

Possible option structure:

```text
┌──────────────────────────────────────┐
│ [provider logo]  Agent name          │
│                  Provider             │
└──────────────────────────────────────┘
```

### Version selector

Once an agent is selected, allow selecting the target version.

Example:

```text
Agent
[ Customer Support Agent       ▼ ]

Version
[ v1.4.2                       ▼ ]
```

If there is no version available, show an appropriate empty state rather than breaking the form.

---

## 5.2 Test Description

Use a prominent multiline textarea.

Label:

```text
What do you want to test?
```

Placeholder should guide the user toward useful test requirements.

Example:

```text
Describe the behavior, scenarios, or requirements you want Resona to evaluate...
```

The textarea should:

- Expand to a sensible maximum height.
- Remain scrollable when content becomes long.
- Never force the whole viewport wider.
- Have clear focus styling.
- Preserve entered text when navigating between steps.

---

# 6. Page 2 — Evaluation Configuration

Page 2 contains the high-level configuration used to generate the evaluator set.

---

## 6.1 Evaluator Count

Label:

```text
Evaluator count
```

Allowed range:

```text
1–100
```

Prefer a number input or controlled stepper.

Validation:

- Minimum: `1`
- Maximum: `100`
- No negative values.
- No non-numeric values.
- Show inline validation if invalid.

---

# 7. Languages

## Available languages

The canonical language options are:

```ts
export const LANGUAGE_OPTIONS: LanguageOption[] = [
  { key: "en", label: "English" },
  { key: "hi", label: "Hindi" },
  { key: "hinglish", label: "Hinglish" },
  { key: "mr", label: "Marathi" },
  { key: "ta", label: "Tamil" },
  { key: "te", label: "Telugu" },
  { key: "bn", label: "Bengali" },
  { key: "kn", label: "Kannada" },
];
```

## UI

Display languages as selectable cards/chips in a responsive wrapping grid.

Example:

```text
Languages

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ EN English  │  │ HI Hindi    │  │ Hinglish    │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ MR Marathi  │  │ TA Tamil    │  │ TE Telugu   │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────┐
│ BN Bengali  │
└─────────────┘
```

The exact number of columns should be responsive rather than fixed.

Recommended:

```css
grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
```

or an equivalent responsive flex-wrap implementation.

### Selection

Use the border-based selected state described in Section 3.

---

# 8. Call Ambience

The user should be able to select environmental/background conditions for calls.

Example options from the design:

- Noisy
- People talking
- etc.

These should be represented as selectable cards/chips.

The list should be extensible without requiring a layout rewrite.

Possible structure:

```text
Call ambience

┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ Noisy        │  │ People talking  │  │ Quiet        │
└──────────────┘  └─────────────────┘  └──────────────┘
```

Use the same border-based selection state.

---

# 9. Backend Preference Generation — NEW FLOW

This is an important addition.

After Page 2 is submitted and before Page 3 (Personas) is displayed, call the backend to determine useful evaluation preferences.

The backend receives the relevant simulation configuration and returns:

- Recommended metrics
- Recommended personas

These recommendations are then used to **autoselect** the corresponding options on the next pages.

## Flow

```text
Page 2
  │
  │ Continue
  ▼
POST preference-generation endpoint
  │
  ▼
Loading state
  │
  ├── "Making evaluation preferences..."
  ├── "Choosing helpful metrics..."
  └── "Finding relevant personas..."
  │
  ▼
Backend response
  │
  ├── recommended metrics
  └── recommended personas
  │
  ▼
Page 3 — Personas
```

---

# 10. Preference Generation Loading State

The loading state should feel intentional and intelligent rather than like a generic spinner.

Use a centered loading experience.

Example:

```text
             ✦

     Making evaluation preferences...

     Choosing helpful metrics...

     Finding relevant personas...
```

The lines should change/rotate during the request.

Recommended behavior:

- Show one line at a time.
- Change every ~1–1.5 seconds.
- Use a subtle fade/slide transition.
- Keep a small spinner or animated sparkle icon.
- Do not make the animation distracting.

Suggested messages:

```text
Making evaluation preferences...
Choosing helpful metrics...
Finding relevant personas...
Preparing your evaluation...
```

The actual number of messages can be 3–4.

### Important

This loading state exists **between Page 2 and Page 3**.

It is not a separate user-editable form page.

The user should not need to click anything while preference generation is running.

### Error handling

If preference generation fails:

```text
Couldn't generate evaluation preferences.

[ Try again ]
```

Do not silently continue with an empty configuration.

Provide a retry path.

If appropriate, a fallback can allow the user to continue with manual selection, but this should be an explicit product decision rather than silently hiding the failure.

---

# 11. Page 3 — Personas

The Persona page follows the preference-generation loading state.

## Purpose

Allow the user to review and modify the personas Resona will use to generate evaluators.

The backend-recommended personas should already be selected when this page loads.

### Persona card

Each persona should contain:

```text
Persona name
Short description
```

Example:

```text
┌──────────────────────────────────┐
│ Frustrated customer           ✓  │
│ Impatient user with a problem    │
│ and low tolerance for delays.    │
└──────────────────────────────────┘
```

### Selection

Recommended personas returned by the backend are selected automatically.

The selected state MUST use the border-based treatment, not a filled background.

The user must still be able to:

- Deselect a recommended persona.
- Select another persona.
- Review all available personas.

Do not lock the backend recommendations.

---

# 12. Page 4 — Metrics

The Metrics page follows the Persona page.

## Purpose

Allow the user to review which evaluation metrics will be used.

Backend-recommended metrics should already be selected.

Each metric should contain:

```text
Metric name
Short explanation / definition
```

Example:

```text
┌─────────────────────────────────────────────┐
│ Relevancy                                   │
│ Measures whether the agent's response       │
│ addresses the user's actual request.     ✓  │
└─────────────────────────────────────────────┘
```

Second example:

```text
┌─────────────────────────────────────────────┐
│ Context Retention                           │
│ Measures whether the agent correctly uses   │
│ information established earlier in the call.│
└─────────────────────────────────────────────┘
```

### Selection

Use the same border-based selected state.

Recommended metrics from the backend should be preselected.

Users can modify the selection.

---

# 13. Navigation

Every page should provide clear navigation.

Recommended:

```text
[ ← Back ]                              [ Continue → ]
```

On the final configuration page:

```text
[ ← Back ]                           [ Review Simulation → ]
```

The navigation should not become inaccessible when the content is long.

### Button behavior

- Disable Continue when required fields are invalid.
- Show validation close to the problematic field.
- Preserve all entered data when navigating backward.
- Prevent duplicate submissions while an async operation is running.

---

# 14. Step Progress

The flow is long enough that users should understand where they are.

Recommended step indicator:

```text
1 Target
   │
2 Configuration
   │
3 Personas
   │
4 Metrics
   │
5 Review
```

The preference-generation loader should **not** appear as an additional user-facing step.

It is an internal transition between steps 2 and 3.

---

# 15. Responsive Behavior

The design should work across:

- Desktop
- Laptop
- Tablet
- Narrow viewport

### Desktop

Use the available width efficiently while keeping a readable maximum content width.

### Tablet

Cards should reduce columns naturally.

### Narrow screens

Stack sections vertically.

For example:

```text
Languages

┌───────────────────────┐
│ English               │
└───────────────────────┘

┌───────────────────────┐
│ Hindi                 │
└───────────────────────┘

┌───────────────────────┐
│ Hinglish              │
└───────────────────────┘
```

Do not allow horizontal scrolling merely because a grid has too many items.

---

# 16. Component Architecture Recommendation

Prefer reusable components instead of implementing every page independently.

Suggested structure:

```text
AddSimulation
├── SimulationFormShell
│   ├── StepIndicator
│   ├── SimulationFormContent
│   └── SimulationFormNavigation
│
├── SimulationTargetStep
│   ├── AgentSelector
│   ├── VersionSelector
│   └── TestDescriptionInput
│
├── SimulationConfigurationStep
│   ├── EvaluatorCountInput
│   ├── LanguageSelector
│   └── CallAmbienceSelector
│
├── PreferenceGenerationLoader
│
├── PersonaSelectionStep
│   └── PersonaCard
│
├── MetricSelectionStep
│   └── MetricCard
│
└── ReviewStep
```

Generic reusable selection components are preferred where the behavior is identical:

```text
SelectableCard
SelectableChip
SelectionGrid
```

---

# 17. State / Data Flow

The complete form should maintain one coherent simulation draft.

Conceptually:

```ts
type SimulationDraft = {
  target: {
    agentId: string;
    versionId: string;
  };

  description: string;

  evaluatorCount: number;

  languages: string[];

  callAmbience: string[];

  personas: string[];

  metrics: string[];
};
```

The exact existing domain types should be reused if already available in the codebase.

Do not introduce duplicate domain models unnecessarily.

---

# 18. Preference API Contract

The frontend should treat preference generation as an asynchronous operation.

Conceptually:

```ts
const preferences = await getSimulationPreferences({
  description,
  target,
  evaluatorCount,
  languages,
  callAmbience,
});
```

Expected response:

```ts
{
  metrics: string[],
  personas: string[]
}
```

The exact endpoint and existing API client conventions should be used from the project.

### On success

```text
preferences.metrics
    ↓
preselected metrics

preferences.personas
    ↓
preselected personas
```

### On failure

Show the dedicated error/retry state.

Do not leave the user staring at an infinite loader.

---

# 19. Accessibility

The implementation should support:

- Keyboard navigation
- Visible focus states
- Screen-reader-readable labels
- `aria-selected` where applicable
- Buttons with meaningful labels
- No interaction that depends solely on color
- Adequate contrast
- Form errors associated with their inputs

The border-based selection state is intentionally useful here because selected state should remain understandable without relying exclusively on background color.

---

# 20. Visual Direction

The Excalidraw drawings intentionally represent **layout and information hierarchy**, not the final visual styling.

The implementation should make the result feel:

- Clean
- Modern
- Calm
- Premium
- AI-native
- Lightweight

Avoid:

- Excessive gradients
- Giant cards
- Huge text
- Excessive shadows
- Overly colorful selected states
- Dense dashboards inside the form
- Unnecessary animations

The UI should feel like a focused configuration wizard, not an admin panel.

---

# 21. Non-Negotiable Implementation Rules

1. **Do not change the intended page flow.**
2. **Do not remove the backend preference-generation step.**
3. Preference generation happens after Page 2 and before Page 3.
4. Show the dedicated animated loading state while preferences are generated.
5. Backend-recommended metrics and personas are automatically selected.
6. Users can modify those selections afterward.
7. Selected language/metric/persona cards use a **border/ring**, not a filled background.
8. Use Lucide/lucide-react for generic icons.
9. Use official/recognized provider logos for voice providers where possible.
10. Do not use country flags as the primary language icon.
11. All pages must handle vertical overflow correctly.
12. No page should create accidental horizontal overflow.
13. Responsive grids must wrap/stack.
14. Long text must wrap correctly.
15. Async actions must prevent duplicate submissions.
16. Async preference generation must have a failure/retry state.
17. Form data must persist while navigating between steps.
18. The implementation should reuse existing project components/design tokens wherever available.
19. Do not invent additional product concepts that are not represented by the design or existing application.
20. When the Excalidraw sketch is ambiguous, prefer the simplest implementation consistent with the existing Resona UI.

---

# 22. Implementation Priority

Implement in this order:

### P0 — Flow correctness

- Page 1
- Page 2
- Preference API call
- Loading state
- Page 3
- Page 4
- Existing Review flow

### P1 — Interaction quality

- Selection border state
- Auto-selection from backend
- Responsive layout
- Scroll management
- Validation
- Error/retry state

### P2 — Polish

- Provider logos
- Lucide icons
- Animations/transitions
- Empty states
- Fine typography/spacing
- Accessibility refinements

---

# 23. Final Mental Model

The user experience should feel like:

```text
"Tell Resona what agent I want to test"
              ↓
"Tell Resona what kind of evaluation I want"
              ↓
"Let Resona intelligently recommend what matters"
              ↓
"Review / modify the personas"
              ↓
"Review / modify the metrics"
              ↓
"Review the complete simulation"
              ↓
"Generate evaluators"
```

The important product principle is that **Resona should do the thinking-heavy selection automatically, while still giving the user control to inspect and modify the result.**
