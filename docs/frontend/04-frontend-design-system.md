# VoiceEval — Frontend Design System & Component Architecture v0.1

## 1. Design direction

VoiceEval should look like a serious instrument, not an ordinary CRUD dashboard.

Visual personality:

```text
technical
editorial
precise
quietly premium
data-dense without looking cramped
```

Avoid the typical:

```text
purple SaaS gradient
huge rounded cards
excessive glassmorphism
every metric as a colorful donut
```

Instead use:

```text
strong typography
thin separators
dense tables
soft surfaces
small status accents
high-quality spacing
subtle depth
```

---

# 2. Typography

Use a two-font system.

### UI font

Recommended:

```text
Inter Tight
```

or an equivalent variable grotesk.

Usage:

```text
navigation
tables
labels
buttons
metric values
forms
```

### Display font

Recommended:

```text
Instrument Serif
```

or a similarly expressive serif.

Usage:

```text
page title
major plan title
large score / result moments
empty-state editorial copy
```

The serif should remain sparse.

Example:

```text
Evaluate how
your agent behaves.
```

Then all controls remain crisp sans-serif.

---

# 3. Type scale

```text
display-xl   48 / 1.0
display-lg   36 / 1.05
display-md   28 / 1.1

title-lg     22 / 1.2
title-md     18 / 1.25
title-sm     15 / 1.3

body-lg      16 / 1.5
body         14 / 1.5
body-sm      13 / 1.4

label        12 / 1.2
micro        11 / 1.2

mono         12 / 1.45
```

Metric values may use tabular numerals:

```css
font-variant-numeric: tabular-nums lining-nums;
```

---

# 4. Spacing

Use a compact analytical scale:

```text
4
6
8
10
12
16
20
24
32
40
48
64
80
```

Tables should be compact.

Editorial pages can breathe more.

---

# 5. Shape language

Prefer:

```text
4px or 6px radius
```

for analytical components.

Use larger radius only on:

```text
primary page sections
modal shells
hero result cards
```

Avoid everything looking like a pill.

---

# 6. Surface hierarchy

Suggested semantic surfaces:

```text
canvas
surface
surface-raised
surface-hover
surface-selected
surface-elevated
```

The visual hierarchy should come primarily from:

```text
contrast
typography
spacing
borders
```

not heavy shadows.

---

# 7. Status system

The state system must be semantic and text-labeled.

### Execution

```text
QUEUED
STARTING
CONNECTING
RUNNING
TERMINATING
COMPLETED
FAILED
TIMED OUT
CANCELLED
```

### Plan

```text
DRAFT
READY
QUEUED
RUNNING
PARTIAL
COMPLETED
CANCELLED
```

### Metric

```text
COMPUTED
NOT AVAILABLE
NOT APPLICABLE
INVALID
ERROR
```

### Validation

```text
PASS
WARNING
ERROR
```

Do not encode state only as color.

---

# 8. Semantic accent policy

Use accents sparingly:

```text
success → positive accent
warning → amber-like accent
danger  → red-like accent
info    → blue-like accent
neutral → muted
```

Use semantic accents on:

```text
status dot
left border
icon
small label
```

Do not flood entire metric cards with semantic color.

---

# 9. shadcn component inventory

Base primitives:

```text
Button
Badge
Card
Separator
Tabs
Input
Textarea
Select
Checkbox
Switch
Dialog
Drawer
Sheet
Tooltip
Popover
DropdownMenu
Command
ScrollArea
Skeleton
Alert
Table
Accordion
Breadcrumb
Progress
Slider
```

Custom compound components:

```text
StatusBadge
HashBadge
RevisionBadge
CapabilityCell
MetricValue
MetricStatusBadge
CoverageMeter
ProgressMatrix
MetricTable
ValidationCheckList
EvaluatorSectionNav
EvidenceCard
EvidenceDrawer
Timeline
TimelineLane
TurnCard
ToolCallCard
StateTransitionRow
EventRow
AudioArtifactPlayer
ManifestSection
RunAttemptList
```

---

# 10. Button hierarchy

### Primary

Use for:

```text
Create evaluator
Prepare evaluation
Execute evaluation
Save revision
```

### Secondary

Use for:

```text
Inspect
Compare
View manifest
View evidence
```

### Destructive

Use for:

```text
Cancel
```

with confirmation.

### Quiet/icon

Use for:

```text
Copy ID
Open source
Seek audio
Expand JSON
```

---

# 11. Badge system

Examples:

```text
[APPROVED]
[FROZEN]
[RUNNING]
[NOT AVAILABLE]
[TRANSPORT]
[DERIVED]
[PROVIDER RAW]
```

Badges should remain compact.

For IDs/hashes:

```text
evalrev_01J…7A2
```

with copy action.

---

# 12. Tables

VoiceEval depends heavily on tables.

Table rules:

- sticky header for long data
- right-aligned numbers
- tabular numerals
- left-aligned labels
- compact vertical padding
- keyboard row focus
- row click affordance
- optional column visibility
- explicit empty states

Example:

```text
Metric                Mean     Median    Min    Max    Coverage
TTFA                  720 ms   690 ms    510    980    100%
Semantic understanding 4.0      4.0      3      5      100%
```

---

# 13. Metric cards

A metric card contains:

```text
metric key
current value
unit
status
coverage
method
```

Example:

```text
TTFA
720 ms
COMPUTED

Coverage 100%
deterministic

caller.audible.end → agent.audible.start
```

Do not include unnecessary decorative charting in every card.

---

# 14. Coverage component

Coverage is not a score.

Create a dedicated component:

```text
Coverage
68 / 75
90.67%
```

or:

```text
Coverage 90.67%
7 unavailable
```

Tooltip:

```text
Coverage measures observability of the metric.
It is not a quality score.
```

This follows the result contract.

---

# 15. Composite score display

### Complete

```text
82.4
/ 100

COMPLETE
Coverage 96%
```

### Incomplete

```text
—
COMPOSITE INCOMPLETE

Coverage 88%
Unavailable weight 12%
Missing critical metrics 2
```

Do not show a partially valid number as though it were final.

---

# 16. Distribution display

For n=3:

```text
Run values
3.0   4.0   5.0

Mean     4.0
Median   4.0
Min      3.0
Max      5.0
Stddev   1.0
```

The visual priority is the raw sample set.

Do not emphasize P95.

---

# 17. Run matrix

Custom component:

```tsx
<ProgressMatrix
  rows={evaluators}
  repetitions={3}
  cells={runs}
/>
```

Each cell:

```text
Run status
attempt count
duration
selected attempt
```

Interactions:

```text
hover → compact run tooltip
click → run detail
cmd/click → open forensics
```

---

# 18. Validation component

A validation check should read like an engineering test report.

```text
✓ Scenario validity
✓ Motive validity
✓ State consistency
✓ Success conditions

⚠ Capability validation
  Tool events are optional for this target.

✓ Criteria validation
```

Error:

```text
✕ Observability validity
  Required target input transcript unavailable.
  Blocks agent_input_wer.
```

---

# 19. Capability matrix

Use a compact table:

```text
Capability                  Available     Affected metrics
target_text_stream          ✓             TTFT
target_input_transcript     ✕             agent_input_wer
tool_calls                   ✓             tool selection / args
tool_results                 ✓             result handling
agent_audio                 ✓             TTFA / voice quality
```

The "affected metrics" column is useful because capability negotiation is a plan-time concern.

---

# 20. Evaluator editor components

Create reusable field groups.

```text
SectionCard
FieldRow
ArrayEditor
KeyValueEditor
AssertionEditor
ActionList
TimeoutInput
MetricCriterionRow
```

Example assertion editor:

```text
┌────────────────────────────────────────────────────────────┐
│ unblock_card                                      REQUIRED │
├────────────────────────────────────────────────────────────┤
│ Type          tool_event                                  │
│ Weight        0.60                                         │
│ Tool          unblock_card                                 │
│ Args          card_last_four = 4821                        │
└────────────────────────────────────────────────────────────┘
```

---

# 21. JSON escape hatch

Advanced users need access to the exact JSONB content.

Provide:

```text
Structured editor | Raw JSON
```

Rules:

- structured editor is primary
- raw JSON is secondary
- invalid JSON blocks save
- after raw edit, structured view refreshes
- do not hide normalized structured validation

This accommodates extensible evaluator content without making raw JSON the main UX.

---

# 22. Revision compare view

Show:

```text
v6                          v7
─────────────────────────────────────────
personality:
neutral                     mildly_frustrated

traits:
interrupt_once              interrupt_once
                             initially_cooperative

max_recovery_attempts:
1                           2
```

Use semantic diff, not JSON text diff, as the primary comparison.

---

# 23. Hash presentation

Every immutable object may have a hash.

Use:

```text
Hash
sha256: a13b...91e7
[copy]
```

Hover/click:

```text
Copied
```

Do not clutter table rows with full hashes.

---

# 24. IDs

IDs are opaque and primarily useful for forensics.

Display:

```text
run_01J…9FA
```

with a copy button.

Never abbreviate in raw payload inspection.

---

# 25. JSON inspector

Use monospace typography.

Structure:

```text
payload
├── tool_name   "unblock_card"
├── status      "succeeded"
└── duration_ms 912
```

Add:

```text
copy JSON
expand all
collapse all
```

---

# 26. Timeline component

Properties:

```ts
interface TimelineEvent {
  id: string;
  lane: string;
  startMs: number;
  endMs?: number;
  label: string;
  source?: string;
  severity?: string;
  payloadRef?: string;
}
```

Support:

```text
zoom
pan
fit selection
seek
hover
click
keyboard navigation
```

Do not overload one event type with semantics belonging to another layer.

---

# 27. Audio player

Custom component:

```text
<AudioArtifactPlayer
  artifact={artifact}
  evidenceRange={[11720, 13100]}
/>
```

Visual:

```text
[◀] [▶]  11.720 ───────── 13.100
██████████████████░░░░░░░░░░░░
       ↑ evidence
```

When evidence range exists, highlight it visually.

---

# 28. Drawer composition

Evidence and event inspection should use drawers/sheets.

Example:

```text
Metric page
   ↓
click evidence
   ↓
right drawer
   ├── evidence
   ├── source
   ├── quote
   ├── rationale
   └── [open turn]
```

This preserves user context.

---

# 29. Command palette

`⌘K` / `Ctrl+K` should expose:

```text
Go to evaluations
Go to evaluators
Go to benchmarks
Go to targets

Create evaluation

Open recent plan
Open recent evaluator
```

For forensic pages:

```text
Go to Turn 19
Find event tool.call.end
Find tool unblock_card
Find metric TTFA
```

---

# 30. Motion

Motion should explain state changes, not decorate them.

Use:

```text
150–220ms
ease-out
```

Good uses:

- live row state transitions
- drawer open
- status changes
- timeline selection
- progress updates

Avoid:

- continuous card floating
- looping decorative animations
- excessive spring physics

For live execution, a small pulse on the current running cell is enough.

---

# 31. Error UX

API error pattern:

```text
Could not prepare evaluation

2 blockers found

[View validation]
```

Network error:

```text
Live connection lost
The page will continue showing the last known state.

[Reconnect]
```

Permission error, when the backend exposes it:

```text
You can view this object but cannot mutate it.
```

Do not surface stack traces.

---

# 32. Mobile rules

Priority order:

```text
result summary
↓
run list
↓
conversation
↓
evidence
↓
raw event payload
```

For wide tables:

```text
horizontal scrolling
```

rather than deleting critical data.

The user should never lose:

```text
status
coverage
attempt lineage
evidence linkage
```

just because of screen width.
