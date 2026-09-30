# Resona — Frontend Product Branding & Identity Implementation Prompt

You are implementing the frontend for a voice-agent evaluation and forensic analysis product.

The product is **NOT called VoiceEval anymore**.

## NON-NEGOTIABLE PRODUCT NAME

The product name is:

# Resona

Use **Resona** everywhere in the user-facing frontend.

Do not use `VoiceEval` as a visible product name anywhere.

The six existing frontend design documents currently use `VoiceEval` as the working product name:

- `@00-frontend-product-architecture.md`
- `@01-frontend-view-specification.md`
- `@02-frontend-object-model-and-api-contract.md`
- `@03-frontend-realtime-forensics.md`
- `@04-frontend-design-system.md`
- `@05-frontend-implementation-map.md`

Treat those documents as the authoritative product/technical architecture, but **Resona is the final brand identity**.

Do not rewrite backend/domain terminology unnecessarily. Objects such as `EvaluationPlan`, `EvaluatorRevision`, `CallRun`, `CallAttempt`, `RuntimeEvent`, `MetricResult`, `Evidence`, etc. remain domain terminology.

Only replace the **product identity / visible brand references**.

---

# 1. BRAND POSITIONING

Resona is a serious analytical instrument for evaluating voice agents.

The frontend architecture explicitly defines the application as a:

- control interface
- observability interface
- analysis interface
- forensic interface

over the backend contract.

Preserve that positioning.

Do NOT make Resona look like:

- a generic SaaS dashboard
- a chatbot playground
- a consumer voice app
- a marketing-heavy AI wrapper
- a generic analytics dashboard
- a purple-gradient "AI platform"
- a glassmorphism-heavy startup template

The existing design direction is:

- technical
- editorial
- precise
- quietly premium
- data-dense without feeling cramped

Preserve this visual personality.

The UI should feel closer to a sophisticated developer/research tool than an ordinary CRUD application.

---

# 2. PRIMARY TAGLINE

Use this as the primary Resona tagline:

> Voice, measured.

This is the short brand tagline.

It should be treated as a reusable brand constant rather than hardcoded independently throughout the application.

Create something equivalent to:

```ts
export const PRODUCT_NAME = "Resona";

export const PRODUCT_TAGLINE = "Voice, measured.";
```

If the implementation architecture has a centralized constants/configuration location, put the values there.

Do NOT scatter hardcoded copies of the brand name across unrelated files when a shared branding constant is appropriate.

---

# 3. SECONDARY PRODUCT POSITIONING

Use this longer positioning line where more explanatory copy is appropriate:

> See how your voice agent behaves.

This should be used as the primary explanatory sentence on suitable high-level surfaces.

Potential combination:

```text
Resona

Voice, measured.

See how your voice agent behaves.
```

Do not use all three lines everywhere.

The hierarchy should be:

```text
Resona
↓
Voice, measured.
↓
See how your voice agent behaves.
```

Use the shortest version in compact UI.

Use the longer explanation only where the user benefits from product context.

---

# 4. TAGLINE VARIANTS

Create a centralized set of approved brand copy:

```ts
export const RESONA_COPY = {
  name: "Resona",

  tagline: "Voice, measured.",

  positioning: "See how your voice agent behaves.",

  laboratory:
    "Evaluate voice-agent behavior from conversation to evidence.",

  forensic:
    "Trace every result back to the interaction that produced it.",

  emptyState:
    "Run an evaluation and see what your agent actually did.",

  live:
    "Observe the conversation as it happens.",

  results:
    "Measure behavior. Inspect evidence. Understand the result.",

  forensics:
    "Go from score to evidence, event, turn, tool, and audio.",

  footer:
    "Resona — Voice, measured.",
};
```

These are starting copy values, not mandatory literal text in every location.

Use judgment about where each belongs.

Do not over-brand every sentence.

---

# 5. GLOBAL BRANDING RULE

Search the entire frontend codebase for:

```text
VoiceEval
voiceeval
VOICEEVAL
Voice Eval
voice eval
```

Replace user-facing occurrences with:

```text
Resona
```

Where the string appears in technical comments, filenames, internal identifiers, API paths, backend contracts, or imported domain types, do NOT blindly rename it if doing so would break the technical contract.

The priority is:

1. User-facing product identity → Resona
2. Browser title → Resona
3. Navigation → Resona
4. Empty states → Resona
5. Loading states → Resona
6. Error states → Resona
7. Metadata → Resona
8. Documentation/help copy → Resona
9. Source comments/internal identifiers → preserve unless safe and appropriate

---

# 6. APPLICATION SHELL

The existing application shell has the product name in the navigation rail.

Change:

```text
VoiceEval
```

to:

```text
Resona
```

The top-level shell should visually establish:

```text
Resona
Voice, measured.
```

However, keep the compact sidebar primarily as:

```text
Resona
```

Do not permanently display the full tagline in the narrow navigation rail if it compromises density.

Possible desktop treatment:

```text
RESONA
Voice, measured.
────────────────────

Overview

Evaluations
Evaluators
Benchmarks
Targets
```

Or, if the logo treatment is graphical:

```text
Resona
```

with the tagline appearing in the appropriate brand/header context.

The sidebar should remain restrained.

The existing architecture calls for a restrained left rail and wide analytical canvas. Preserve that.

---

# 7. OVERVIEW DASHBOARD

The Overview Dashboard is one of the most important branding surfaces.

Current conceptual structure:

```text
VoiceEval
New evaluation
```

Change it to:

```text
Resona
Voice, measured.

New evaluation
```

Use the serif display typography selectively.

Suggested hero treatment:

```text
Resona

Voice, measured.

See how your voice agent behaves.

[ New evaluation ]
```

Then immediately transition into analytical information:

```text
Active evaluations
Completed this week
Coverage
```

Do NOT make the dashboard feel like a marketing landing page.

The product is an instrument.

Branding should occupy the top ~10–15% of the visual hierarchy, after which data becomes dominant.

---

# 8. OVERVIEW EMPTY STATE

When there are no evaluations:

```text
Resona

Voice, measured.

No evaluations yet.

Configure a target, author an evaluator,
prepare an evaluation plan, and run your first evaluation.

[ Create evaluation ]
```

Alternative shorter version:

```text
Nothing measured yet.

Create your first evaluation.
```

Keep "Resona" visible in the surrounding shell, so the empty state itself does not need to repeat the brand excessively.

---

# 9. EVALUATION PLAN PAGES

Evaluation pages should feel like the user has entered the Resona laboratory.

Header structure:

```text
Resona
Evaluations

Support Benchmark
RUNNING
```

Do not write:

```text
VoiceEval Evaluation
```

Do not repeatedly append the brand name to object names.

Correct:

```text
Resona
Support Benchmark
RUNNING
```

Incorrect:

```text
Resona Support Benchmark Evaluation
```

---

# 10. LIVE CONSOLE

The live console should carry the strongest operational personality.

Use:

```text
LIVE · Resona
```

or:

```text
Resona · LIVE
```

Preferred:

```text
LIVE
Support Benchmark
69 / 75
```

with the Resona brand remaining in the application shell.

The live page should communicate:

> Observe the conversation as it happens.

Do not turn the live interface into a generic monitoring dashboard.

The backend/live architecture explicitly treats the browser WebSocket as an observability feed rather than a media transport. Preserve this conceptual distinction in the UI.

---

# 11. RESULTS PAGE

Results should emphasize measurement.

Preferred copy:

```text
Evaluation complete

75 logical samples

Composite
82.4 / 100

Coverage
94.7%
```

Optional supporting editorial line:

```text
Measure behavior. Inspect evidence. Understand the result.
```

Do not use exaggerated claims such as:

```text
Your agent is amazing!
```

or:

```text
AI quality score
```

The product is designed around provenance and evidence.

Keep the result language analytical.

---

# 12. FORENSIC VIEWER

The forensic viewer should use Resona's strongest technical identity.

Potential header:

```text
Resona
Forensics

Credit Card Unblock
Run 2
```

Supporting copy:

```text
Trace the result back to the interaction that produced it.
```

The forensic UI should expose the chain:

```text
Score
  ↓
Evidence
  ↓
Turn
  ↓
Event
  ↓
Tool
  ↓
Audio
```

This is one of the defining product concepts.

Do not dilute this with generic analytics language.

---

# 13. METRIC / EVIDENCE INSPECTOR

Use:

```text
Metric evidence
```

and:

```text
Evidence
3 sources
```

Supporting microcopy can use:

> Every result should be traceable.

Avoid marketing language.

The existing architecture explicitly requires qualitative results to remain traceable to evidence, turns, tool calls, and other runtime objects.

---

# 14. EVALUATOR EDITOR

The evaluator editor should feel like an engineering laboratory rather than a form builder.

Possible page title:

```text
Evaluator revision
```

Supporting editorial text:

```text
Define what Resona should observe.
```

Or:

```text
Define the behavior this evaluation is designed to measure.
```

Do not put the Resona name before every section.

---

# 15. VALIDATION VIEW

Use concise engineering-style copy.

Header:

```text
Evaluator validation
```

Supporting line:

```text
Resona checks whether this evaluator is executable and internally consistent.
```

Validation itself should remain technical:

```text
✓ Scenario validity
✓ Motive validity
✓ State consistency
✓ Success conditions
⚠ Capability validation
✓ Criteria validation
```

Do not turn validation into promotional copy.

---

# 16. BENCHMARKS

Benchmark views should remain data-oriented.

Use:

```text
Benchmarks
Benchmark version
FROZEN
```

Potential empty state:

```text
No benchmarks yet.

Create a benchmark version to define a reproducible evaluation suite.
```

Do not write:

```text
Create your first Resona benchmark!
```

unless the context is specifically onboarding.

---

# 17. TARGETS

Target pages should use:

```text
Agent targets
```

not:

```text
Resona agents
```

The target is the external voice agent being evaluated.

Keep the domain model clean.

Resona is the evaluator.

---

# 18. BROWSER TITLE / DOCUMENT METADATA

Set browser/document titles using Resona.

Examples:

```text
Resona
Resona — Overview
Resona — Evaluations
Resona — Live Evaluation
Resona — Results
Resona — Forensics
Resona — Evaluators
Resona — Benchmarks
Resona — Targets
```

For object-specific pages:

```text
Resona — Support Benchmark
Resona — Credit Card Unblock — Forensics
```

Do not use:

```text
VoiceEval
VoiceEval Dashboard
VoiceEval App
```

anywhere in browser-visible metadata.

---

# 19. FAVICON / BRAND ASSETS

If a logo/favicon system exists, name the conceptual assets around Resona.

Preferred:

```text
resona-mark
resona-wordmark
resona-icon
```

Do not create new user-facing assets called:

```text
voiceeval-logo
voiceeval-mark
```

unless they are legacy implementation filenames that can safely be renamed.

If a dedicated logo has not been designed yet, use a typographic wordmark:

```text
Resona
```

Do not invent a complicated logo unnecessarily.

The product's typography should do much of the branding work.

---

# 20. TYPOGRAPHY

Preserve the existing typography architecture:

UI:

```text
Inter Tight
```

or equivalent variable grotesk.

Display:

```text
Instrument Serif
```

or equivalent expressive serif.

Use the serif for:

- Resona hero moments
- major page titles
- major result moments
- selected empty-state editorial copy

Use the sans-serif for:

- navigation
- tables
- labels
- buttons
- metrics
- forms
- technical information

Do not turn every occurrence of "Resona" into decorative serif typography.

The brand should feel confident, not ornamental.

---

# 21. BRAND VISUAL PERSONALITY

The following are hard design constraints.

DO:

```text
strong typography
thin separators
dense tables
soft surfaces
small status accents
precise spacing
subtle depth
high information density
```

DO NOT:

```text
purple SaaS gradients
giant rounded cards
excessive glassmorphism
rainbow metric cards
huge decorative illustrations
generic AI sparkles
excessive pills
marketing-dashboard aesthetics
```

Resona should look like an instrument used by engineers and researchers.

---

# 22. BRAND + FORENSICS

A major differentiator of Resona is that it does not merely produce a score.

It preserves the provenance chain:

```text
Evaluation
  ↓
Logical Run
  ↓
Physical Attempt
  ↓
Conversation
  ↓
Runtime Events
  ↓
Tools
  ↓
State Transitions
  ↓
Media
  ↓
Metric
  ↓
Evidence
  ↓
Result
```

Use brand language that reinforces this philosophy.

Approved phrases:

```text
From conversation to evidence.
Trace every result.
Measure what happened.
See how the agent behaved.
Voice, measured.
Beyond the transcript.
```

Do not introduce claims that imply capabilities absent from the backend contract.

---

# 23. MICROCOPY LIBRARY

Use these where contextually appropriate.

## Loading

```text
Resona is preparing the evaluation…
```

For technical views, prefer:

```text
Loading evaluation…
```

Do not unnecessarily mention the brand in every loading state.

## Live connection

```text
Resona Live
```

Connection states remain:

```text
● Live
↻ Reconnecting
○ Disconnected
```

## No data

```text
Nothing measured yet.
```

## Partial data

```text
PARTIAL
68 / 75 samples observable
```

## Error

```text
Resona could not load this evaluation.

Request ID: ...
Retry
```

## Forensics

```text
Trace the evidence.
```

## Metric

```text
Measured from runtime evidence.
```

## Coverage

```text
Coverage measures observability of the metric.
It is not a quality score.
```

Preserve the existing distinction between coverage and quality.

---

# 24. COMMAND PALETTE

The command palette should have Resona branding.

Placeholder:

```text
Search Resona…
```

or preferably:

```text
Search evaluations, evaluators, targets…
```

Header:

```text
Resona
```

Commands:

```text
New evaluation
Open evaluations
Open evaluators
Open benchmarks
Open targets
Search runs
Search evidence
```

Do not use:

```text
Search VoiceEval
```

---

# 25. AUTH / WORKSPACE SURFACES

If authentication/workspace screens are implemented:

```text
Resona

Voice, measured.
```

Then:

```text
Sign in
```

Keep authentication visually minimal.

Do not turn it into a marketing landing page.

---

# 26. ERROR BOUNDARIES

Global error UI:

```text
Something went wrong.

Resona could not load this view.

Request ID: ...
Retry
```

Domain-specific:

```text
This evaluation could not be loaded.

Request ID: ...
Retry
```

Use Resona branding in the global fallback but avoid repeating it in every nested error boundary.

---

# 27. FOOTER

If the application contains a footer:

```text
Resona
Voice, measured.
```

Optionally:

```text
Resona · Voice, measured.
```

Keep it extremely subtle.

This is an analytical application, not a marketing website.

---

# 28. CODE ARCHITECTURE

Centralize brand constants.

Suggested:

```text
src/
├── lib/
│   └── constants/
│       └── brand.ts
```

Example:

```ts
export const BRAND = {
  name: "Resona",
  tagline: "Voice, measured.",
  positioning: "See how your voice agent behaves.",
} as const;
```

Then use:

```tsx
<title>{BRAND.name} — Overview</title>
```

and:

```tsx
<BrandWordmark />
```

where appropriate.

Create a reusable:

```text
BrandWordmark
```

component if the application has enough repeated branding surfaces.

Potential API:

```tsx
<BrandWordmark />
<BrandWordmark compact />
<BrandWordmark showTagline />
```

Keep this component extremely simple.

---

# 29. DO NOT RENAME DOMAIN OBJECTS

This is important.

Do NOT turn:

```text
EvaluationPlan
EvaluatorRevision
CallRun
CallAttempt
RuntimeEvent
MetricResult
Evidence
ExecutionManifest
```

into things like:

```text
ResonaEvaluation
ResonaEvaluator
ResonaRun
```

That would pollute the domain model.

Resona is the product brand.

The domain model remains generic and technically precise.

---

# 30. DO NOT RENAME API ROUTES JUST FOR BRANDING

Do not modify backend API contracts merely to replace branding.

For example, preserve:

```text
/api/v1/evaluation-plans/{id}/live
/api/v1/call-runs/{id}
/api/v1/call-attempts/{id}/events
```

The frontend branding layer is independent from the backend domain/API contract.

---

# 31. ROUTES

Preserve the existing route architecture:

```text
/
├── /evaluations
├── /evaluators
├── /benchmarks
└── /targets
```

and their nested views.

Do not change URLs to:

```text
/resona/evaluations
```

unless the backend/application architecture explicitly requires it.

The product name is Resona; the route model does not need artificial branding.

---

# 32. DATA / FORENSIC UI

The existing frontend specifications define three information densities:

```text
L1 — Executive
L2 — Analytical
L3 — Forensic
```

Preserve this.

Resona's branding should become quieter as information density increases.

For example:

### L1

```text
Resona

Voice, measured.

Composite
82.4 / 100
```

### L2

```text
Evaluation results

Metric          Mean      Coverage
TTFA            720 ms    100%
Semantic        4.0       100%
```

### L3

```text
agent.audible.start
sequence 184
derived
12,420 ms
turn_17
```

The deeper the user goes, the less decorative branding should appear.

The evidence itself becomes the interface.

---

# 33. RESPONSIVE BEHAVIOR

Preserve the existing responsive strategy.

Desktop:

```text
Resona sidebar
+
wide analytical canvas
```

Mobile:

```text
menu
current context
overflow actions
```

Do not let branding consume analytical viewport space on mobile.

Compact form:

```text
Resona
```

rather than:

```text
Resona
Voice, measured.
See how your voice agent behaves.
```

---

# 34. ACCESSIBILITY

Branding must not compromise accessibility.

Ensure:

- logo has accessible name
- wordmark has meaningful alt/label when necessary
- status is not communicated only by color
- live state uses appropriate `aria-live`
- typography remains readable
- focus states remain visible
- taglines are supplementary, not required to understand functionality

Do not make the serif brand treatment the only way information is communicated.

---

# 35. SEARCH / REPLACEMENT CHECKLIST

Before considering the branding migration complete, search the entire repository for:

```text
VoiceEval
voiceeval
Voice Eval
voice eval
```

Then classify every occurrence:

### Replace

- sidebar
- topbar
- page headers
- dashboard
- empty states
- browser titles
- metadata
- login/auth surfaces
- footer
- visible error messages
- visible loading states
- visible onboarding
- visible documentation
- visible command palette
- visible tooltips

### Preserve unless technically safe to change

- backend API paths
- domain type names
- database object names
- technical identifiers
- migration names
- historical documentation
- backend contract references
- test fixtures where the old string is intentionally testing compatibility

---

# 36. FINAL BRANDING QA

Before completion, verify all of the following.

## Brand

- [ ] Product is visibly called Resona.
- [ ] No accidental visible "VoiceEval" remains.
- [ ] Browser title uses Resona.
- [ ] Sidebar uses Resona.
- [ ] Dashboard uses Resona.
- [ ] Auth surfaces use Resona.
- [ ] Empty states use Resona appropriately.
- [ ] Error surfaces use Resona appropriately.
- [ ] Footer uses Resona if present.

## Tagline

- [ ] Primary tagline is exactly `Voice, measured.`
- [ ] Secondary positioning is `See how your voice agent behaves.`
- [ ] Tagline is not spammed across every screen.
- [ ] Tagline is strongest on high-level product surfaces.
- [ ] Forensic screens prioritize evidence over branding.

## Architecture

- [ ] Domain object names remain unchanged.
- [ ] API contracts remain unchanged.
- [ ] Routes remain unchanged unless there is an independent reason to modify them.
- [ ] Brand constants are centralized.
- [ ] No duplicated hardcoded product naming where a shared constant/component is appropriate.

## Visual identity

- [ ] Technical.
- [ ] Editorial.
- [ ] Precise.
- [ ] Quietly premium.
- [ ] Data-dense.
- [ ] No generic purple AI SaaS aesthetic.
- [ ] No excessive glassmorphism.
- [ ] No excessive rounded cards.
- [ ] No decorative chart spam.

## Product identity

The final frontend should make the following idea immediately understandable:

> **Resona measures how voice agents behave, then lets you trace the result back to the evidence that produced it.**

The product should feel like a serious instrument.

Not a dashboard.

Not a chatbot.

Not a toy.

**Resona.**

**Voice, measured.**