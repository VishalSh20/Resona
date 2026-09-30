# Resona Frontend

React + TypeScript + Tailwind + shadcn control, observability and forensic
interface over the Resona backend contract, plus a public marketing landing page
at `/`.

## Routing

- `/` — public landing page (animated Pattern Waves hero).
- `/signin`, `/signup` — public auth surfaces.
- `/app` and below (`/app/simulations`, `/app/benchmarks`, `/app/agents`,
  `/app/runs/:runId`) — the authenticated application, guarded by `RequireAuth`.

## Stack

- React 19, TypeScript, Vite
- React Router, TanStack Query, Zustand
- Tailwind CSS v4, shadcn/ui, Radix primitives
- Vitest

## Setup

```bash
npm install
cp .env.example .env.local   # optional; defaults to /api/v1
npm run dev                  # http://localhost:5173
```

The dev server proxies `/api` to the backend on `http://localhost:8000`.

## Scripts

```bash
npm run dev          # start dev server
npm run build        # typecheck + production build
npm run preview      # preview the production build
npm test             # run unit tests (vitest)
```

## Structure

```
src/
├── app/            routing, providers, shell, pages
├── features/       landing, auth, agents, simulations, benchmarks, runs
├── components/
│   ├── ui/         shadcn primitives
│   ├── backgrounds/ vendored React Bits backgrounds (PatternWaves)
│   ├── status/     StatusBadge, CoverageBadge, CompositeScoreCard
│   ├── data/       DataTable, MetricValue, ProgressBar, TurnCard, EventRow, …
│   ├── timeline/   Timeline
│   └── audio/      AudioArtifactPlayer
├── lib/
│   ├── api/        HTTP client, TanStack Query client, typed service modules
│   ├── mappers/    DTO -> view model
│   ├── websocket/  live plan client + reconnect
│   ├── constants/  status maps, navigation
│   └── formatters/ value/time/ID/hash formatting
├── stores/         Zustand UI + session state
├── styles/         tokens, typography, globals
└── types/          API DTOs + domain view models
```

## Features

- **Landing** — public page at `/` with a React Bits Pattern Waves hero; the nav
  and hero CTAs route to `/signin` and `/signup`.
- **Auth** — sign up / sign in (`/signin`, `/signup`); the application under
  `/app` is behind a session guard. A rejected token clears the session and
  routes back to sign-in.
- **Configuration** — targets + revisions, evaluators + revision editor +
  validation, benchmarks + versions.
- **Execution** — plan list, creation wizard (scope → target → evaluators →
  repeats → prepare), plan overview (segmented progress), and a live console
  driven by the observability-only WebSocket.
- **Results** — composite score, category cards, metric aggregate table and an
  evaluator heatmap.
- **Forensics** — run detail with attempt lineage and retry, conversation /
  timeline / event stream / inspector, signed media playback with evidence seek,
  and the sealed manifest viewer.

The API layer fetches snake_case DTOs and maps them to the camelCase view models
in `types/domain.ts` (`lib/mappers`). Canonical metric statuses are never coerced
to zero.

