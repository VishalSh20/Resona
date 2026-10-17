# Frontend — Phase 1 (Foundations): Progress

## Status: Complete

The React frontend foundation is scaffolded, builds cleanly, and is test- and
dev-server verified. Phase 1 covers shell, routing, typography, tokens, shadcn
setup, API client, TanStack Query, status primitives, and tables.

## What was built (under `frontend/`)

### Stack
Vite + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui (new-york style) +
React Router + TanStack Query + Zustand + Vitest.

### Design tokens & typography
- `src/styles/tokens.css` — semantic surfaces (`canvas`, `surface`,
  `surface-raised/hover/selected/elevated`), status accents (success/warning/
  danger/info), radius and a two-font system (Inter Tight + Instrument Serif),
  mapped into Tailwind v4 via `@theme inline` in `index.css`.
- `src/index.css` — full type scale (`text-display-xl` … `text-mono`) and
  `text-*` utilities, `tabular-nums` for metric values.

### shadcn primitives (`src/components/ui/`)
button, badge, card, separator, input, skeleton, table, tooltip, alert,
dropdown-menu, scroll-area, dialog. `components.json` is configured so the
shadcn CLI can add more later.

### App shell (`src/app/shell/`)
Sidebar (primary nav), Topbar (breadcrumbs + search trigger + workspace menu),
Breadcrumbs (path-derived, ID segments truncated), CommandPalette (`⌘K`).

### Routing (`src/app/router.tsx`)
Full route tree from `00-frontend-product-architecture.md` (evaluations,
evaluators, benchmarks, targets with nested overview/revisions/live/results/
runs/forensics). Feature surfaces render a shared placeholder until later
phases; `/` renders the Overview page exercising typography, status badges and
the data table.

### API client (`src/lib/api/`)
- `client.ts` — single fetch wrapper: base URL, `Authorization`,
  `X-Request-ID`, optional `Idempotency-Key`, and error-envelope normalization
  into `ApiError` (code/status/request_id).
- Typed service modules: `targets`, `evaluators`, `benchmarks` (match the
  implemented backend, snake_case DTOs), and `plans`, `runs`, `attempts`,
  `results`, `media` (documented contract, camelCase view models).
- `queryClient.ts` — TanStack Query defaults from the implementation map
  (staleTime 30s, reads retry 2, mutations retry 0).

### Status & data primitives
- `StatusBadge` / `CoverageBadge` / `FailureBadge` (semantic tone + label,
  never color-only; coverage is explicitly "not a quality score").
- `DataTable` (generic, sticky/right-aligned numerics, empty state),
  `MetricValue` (never coerces unavailable → zero), `MetricTable`.

### Types (`src/types/`)
`api.ts` (transport DTOs + common primitives), `domain.ts` (camelCase view
models for every domain object), `ui.ts`.

## Verification (all passing)
```bash
npm install            # NOTE: NODE_ENV=production was set in the shell, which
                       # skipped devDependencies; re-ran with
                       # NODE_ENV=development npm install --include=dev
npm run build          # tsc -b && vite build — clean
npm test               # 8 passed (status mapping + formatters)
npm run dev            # serves on http://localhost:5173 (200)
```

## Deferred to later phases
- Phase 2 — Targets, target revisions, evaluator library/editor, validation,
  benchmarks.
- Phase 3 — Plan wizard, preparation screen, plan overview, live console,
  WebSocket integration.
- Phase 4 — Results dashboard, metric tables, aggregates, composite, heatmap.
- Phase 5 — Run/attempt detail, conversation, timeline, events, tools, state,
  media, evidence, manifest (forensics).

## Branding (Resona)

Applied `06-naming-and-styling-prompt.md`: the product is branded **Resona**,
tagline **"Voice, measured."**, positioning **"See how your voice agent
behaves."**. Brand constants are centralized in `src/lib/constants/brand.ts`
(`BRAND`, `RESONA_COPY`, `PRODUCT_NAME`/`PRODUCT_TAGLINE`) with a reusable
`BrandWordmark` component and a `useDocumentTitle` hook. User-facing "VoiceEval"
references were replaced (browser title + meta, sidebar wordmark, overview hero,
empty states, command palette placeholder, error copy, README, package name,
localStorage key). Domain object names, API routes, and backend contracts are
unchanged. Build and tests remain green.
