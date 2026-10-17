# Run Results Page — Frontend Design

## Goals

- Replace the cluttered evaluator table with a clean, card-based list.
- Hide verbose text (scenario, judge prompt) inside accordions.
- Surface the right fields at a glance: status, language, personality, metric count, duration, score.
- Add a dedicated results section with run-level metrics charts and per-evaluator detail.
- Each evaluator result must expose: call recording, conversation, judge metrics, and summary.

---

## Page sections

```
RunDetailPage
├── RunHeader
│   ├── Run id + back link
│   ├── Run status badge
│   ├── Start / finish timestamps
│   ├── Duration
│   └── Primary actions (re-run, export)
├── RunProgressSummary
│   ├── Progress bar (queued / running / completed / failed)
│   ├── Overall composite score (when ready)
│   └── Coverage ratio
├── EvaluatorsSection
│   └── EvaluatorCard × n
│       ├── Collapsed header
│       └── Expanded accordion body
├── ResultsSection  (shown when any results exist)
│   ├── MetricsOverview
│   │   ├── Score distribution chart
│   │   ├── Category radar / bar chart
│   │   └── Metric-by-metric comparison grid
│   └── EvaluatorResultsPanel
│       └── EvaluatorResultCard × n
│           ├── CallRecording
│           ├── ConversationTranscript
│           ├── MetricsGrid
│           └── JudgeSummary
└── Empty / loading / error states
```

---

## 1. RunHeader

**Data:** `RunDto` + `SimulationDto`

**Fields shown:**
- `run.id` (truncated)
- `run.status` → `StatusBadge`
- Simulation name/link
- `run.created_at`
- `run.started_at` (if present)
- `run.finished_at` (if present)
- Duration = finished_at - started_at or `Date.now() - started_at` for active runs
- Target revision (truncated, copyable)

**Actions:**
- Back to simulation
- Re-run (if run is completed/partial)
- Cancel (if running)

---

## 2. RunProgressSummary

**Data:** `RunProgressDto` + `CompositeRead | null`

**Fields shown:**
- Total evaluators
- Completed count
- Running count
- Failed/cancelled count
- Progress bar
- Composite score (`score_0_100`) with circular score widget when available
- Coverage ratio badge
- Missing metrics list (chips)

---

## 3. EvaluatorsSection

### 3.1 EvaluatorCard (collapsed)

**Data:** `RunEvaluatorDto` + matching `CallRunDto[]` + aggregated metrics

**Fields shown:**
- Evaluator # (`sequence_no`)
- Status of associated call runs (derive dominant status)
- Major/minor language
- Personality tags (1-2 visible, overflow count)
- Metric count chip
- Call duration
- Result mini-score (when available)
- Expand/collapse chevron

**Hidden until expanded:**
- Full scenario text
- Full expected output prompt (judge prompt)
- Full personality list
- Full metric list

### 3.2 EvaluatorCard (expanded)

**Tabs or stacked sections:**

#### Tab: Details
- **Scenario** (collapsible read-only textarea / prose block)
- **Expected output prompt** (collapsible)
- **Languages**
- **Personality**
- **Metrics selected**

#### Tab: Call Run(s)
For each repetition / `CallRunDto`:
- Status badge
- Repetition number
- Duration
- Selected attempt id (link)
- Terminal status / reason
- Link to forensics

#### Tab: Results (appears once judged)
- See `EvaluatorResultCard` below

---

## 4. ResultsSection

Shown only when `RunResultsRead.evaluators` has any `metric_results` or `metrics`.

### 4.1 MetricsOverview

**Data:** `RunResultsRead.composite` + aggregated `AggregateRead[]`

**Visualizations:**

1. **Overall score card**
   - Big composite score number (0-100)
   - Colored by threshold: >=80 green, >=60 amber, <60 red
   - Coverage ratio

2. **Category score chart**
   - Horizontal bar chart or radar chart
   - One bar per category from `category_scores`

3. **Metric distribution**
   - Group metrics by status: ok, not_applicable, invalid, error
   - Donut / pie chart

4. **Metric comparison table**
   - Rows: metric_key
   - Columns: per-evaluator value + aggregate mean
   - Highlight outliers

### 4.2 EvaluatorResultCard

**Data:** `EvaluatorRunResults` + `ForensicsRead` (fetched on demand for the selected call run)

**Sub-components:**

#### CallRecording
- Fetch presigned URL for the `mixed` artifact via `GET /media/{artifact_id}/url`
- `<audio>` element with the mixed track as default
- Optional track switcher: caller original / agent original / mixed
- Download button

#### ConversationTranscript
- Fetch via `GET /call-runs/{call_run_id}/forensics`
- Render diarized turns (caller / agent)
- Turn-level: speaker, text, start/end timestamps
- Highlight turns with findings
- Optional: show ASR confidence, tool calls inline

#### MetricsGrid
- Grid of metric cards for this evaluator
- Each card:
  - metric_key name
  - Status badge
  - Score/value (large)
  - Direction indicator (higher/lower is better)
  - Confidence bar
  - Short summary (from judge `summary`)
  - Expandable: findings list, probes, caveats

#### JudgeSummary
- Evidence coverage
- `needs_human_review` flag
- `alignment_conflict` flag
- Caveats list
- Timeline flags (turns with issues)

---

## 5. State machine

```
RunDetailPage
  ├─ runQuery: loading | success | error
  ├─ evaluatorsQuery: loading | success | error
  ├─ resultsQuery: loading | success | error (poll while run.status in [running, partial])
  └─ expandedEvaluatorId: string | null
```

**Polling:**
- While `run.status` is `running` or `partial`, poll `useRunResults(runId)` every 5s.
- Stop polling when `run.status` is `completed`, `cancelled`, or `partial` but no active call runs remain.

**Loading states:**
- Run header skeleton
- Evaluator cards skeleton
- Results section skeleton with chart placeholders

**Empty states:**
- No evaluators: "No evaluators configured."
- Run not started: "Start the run to dispatch calls."
- Run running, no results yet: "Calls are in progress. Results will appear here."
- Run completed but no judge results: "Calls finished. Judging is in progress."

---

## 6. Data hooks to add / reuse

```ts
// features/runs/queries.ts
export function useRunResults(runId: string | undefined) {
  return useQuery({
    queryKey: ["runs", runId, "results"],
    queryFn: () => runsApi.getResults(runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) => {
      const run = query.state.data as RunResultsRead | undefined;
      if (run?.status === "running" || run?.status === "partial") return 5000;
      return false;
    },
  });
}

// lib/api/runs.ts
export function getResults(runId: string) {
  return http.get<RunResultsRead>(`/runs/${runId}/results`);
}
```

---

## 7. API endpoints already available

| Purpose | Endpoint |
|---|---|
| Run info | `GET /runs/{run_id}` |
| Evaluators | `GET /runs/{run_id}/evaluators` |
| Call runs | `GET /runs/{run_id}/call-runs` |
| Run results | `GET /runs/{run_id}/results` |
| Composite | `GET /runs/{run_id}/composite` |
| Forensics | `GET /call-runs/{call_run_id}/forensics` |
| Attempt media | `GET /call-attempts/{attempt_id}/media` |
| Media presigned URL | `GET /media/{media_artifact_id}/url` |

---

## 8. Component inventory

### New components

| Component | Location |
|---|---|
| `RunHeader` | `features/runs/RunHeader.tsx` |
| `RunProgressSummary` | `features/runs/RunProgressSummary.tsx` |
| `EvaluatorsSection` | `features/runs/EvaluatorsSection.tsx` |
| `EvaluatorCard` | `features/runs/EvaluatorCard.tsx` |
| `EvaluatorDetails` | `features/runs/EvaluatorDetails.tsx` |
| `CallRunsList` | `features/runs/CallRunsList.tsx` |
| `ResultsSection` | `features/runs/results/ResultsSection.tsx` |
| `MetricsOverview` | `features/runs/results/MetricsOverview.tsx` |
| `ScoreCard` | `features/runs/results/ScoreCard.tsx` |
| `CategoryChart` | `features/runs/results/CategoryChart.tsx` |
| `MetricDistributionChart` | `features/runs/results/MetricDistributionChart.tsx` |
| `MetricComparisonTable` | `features/runs/results/MetricComparisonTable.tsx` |
| `EvaluatorResultCard` | `features/runs/results/EvaluatorResultCard.tsx` |
| `CallRecording` | `components/audio/CallRecording.tsx` |
| `ConversationTranscript` | `components/conversation/ConversationTranscript.tsx` |
| `MetricsGrid` | `features/runs/results/MetricsGrid.tsx` |
| `MetricResultCard` | `features/runs/results/MetricResultCard.tsx` |
| `JudgeSummary` | `features/runs/results/JudgeSummary.tsx` |

### Reused components

- `StatusBadge`
- `PageHeader`
- `ProgressBar`
- `Card`
- `Badge`
- `Tabs`
- `Accordion` (Radix UI based)
- `AudioArtifactPlayer` (extend for track switching)

---

## 9. UX decisions

1. **No more full scenario in the table.** It belongs in the expanded accordion; the card header shows at most a 2-line preview or nothing at all.
2. **Status is first-class.** The evaluator card header leads with status so users can scan quickly.
3. **Results are opt-in.** The `ResultsSection` only renders when data exists; it doesn't clutter the page during setup or execution.
4. **Recording is per-evaluator.** Each evaluator's selected attempt has its own recording. If there are multiple repetitions, show a dropdown to pick the attempt.
5. **Charts over tables for overview.** Tables remain for forensic detail; charts communicate the headline.
6. **Progressive disclosure.** Findings, probes, and caveats live inside collapsible metric cards.

---

## 10. Suggested chart library

Use `recharts` (already common in React projects) or a lighter alternative like `@visx`:

- Horizontal bar chart for category scores
- Donut chart for metric status distribution
- Radar chart for multi-metric comparison
- Progress bar for run completion

If adding a chart dependency, prefer `recharts` for quick, accessible charts with responsive containers.

---

## 11. Accessibility notes

- Each evaluator card is an accordion with `aria-expanded` and `aria-controls`.
- The audio player has visible track labels and transcript links.
- Charts have `aria-label` summaries and fallback tables for screen readers.
- Focus moves to the expanded accordion body on open.
