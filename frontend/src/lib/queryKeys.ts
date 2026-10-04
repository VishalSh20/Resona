// Central TanStack Query key structure, shared by feature hooks so mutations can
// invalidate the exact right cache entries.
import type { EventFilters } from "@/lib/api/attempts";

export const simulationKeys = {
  all: ["simulations"] as const,
  detail: (simulationId: string) => ["simulations", simulationId] as const,
  runs: (simulationId: string) => ["simulations", simulationId, "runs"] as const,
};

export const runKeys = {
  detail: (runId: string) => ["runs", runId] as const,
  evaluators: (runId: string) => ["runs", runId, "evaluators"] as const,
  evaluator: (runId: string, evaluatorId: string) =>
    ["runs", runId, "evaluators", evaluatorId] as const,
  callRuns: (runId: string) => ["runs", runId, "call-runs"] as const,
  progress: (runId: string) => ["runs", runId, "progress"] as const,
  composite: (runId: string) => ["runs", runId, "composite"] as const,
  results: (runId: string) => ["runs", runId, "results"] as const,
};

export const callRunKeys = {
  all: ["call-runs"] as const,
  attempts: (callRunId: string) =>
    ["call-runs", callRunId, "attempts"] as const,
};

export const attemptKeys = {
  all: ["attempts"] as const,
  detail: (attemptId: string) => ["attempts", attemptId] as const,
  conversation: (attemptId: string) => ["attempts", attemptId, "conversation"] as const,
  events: (attemptId: string, filters?: EventFilters) =>
    ["attempts", attemptId, "events", filters ?? {}] as const,
  media: (attemptId: string) => ["attempts", attemptId, "media"] as const,
};

export const metricKeys = {
  detail: (metricResultId: string) =>
    ["metric-results", metricResultId] as const,
  evidence: (metricResultId: string) =>
    ["metric-results", metricResultId, "evidence"] as const,
};
