# VoiceEval — Frontend Design Pack v0.1

This pack defines the React + TypeScript + Tailwind + shadcn frontend over the VoiceEval backend contract.

## Documents

1. `00-frontend-product-architecture.md` — product architecture, IA, routes, state boundaries, and UX invariants.
2. `01-frontend-view-specification.md` — detailed views, screens, user journeys, and workflows.
3. `02-frontend-object-model-and-api-contract.md` — TypeScript view models and endpoint-to-view mapping.
4. `03-frontend-realtime-forensics.md` — WebSocket behavior, live execution UX, timeline, evidence, and forensic inspection.
5. `04-frontend-design-system.md` — typography, component system, tables, status, metric cards, timeline, audio, motion, and responsive behavior.
6. `05-frontend-implementation-map.md` — code structure, API/query strategy, mutations, testing, performance, and MVP order.

## Backend-grounded model

The frontend preserves the backend source-of-truth hierarchy:

`Test truth → Observed truth → Evaluation truth`

and the logical distinction:

`CallRun = statistical sample`

`CallAttempt = physical execution history`
