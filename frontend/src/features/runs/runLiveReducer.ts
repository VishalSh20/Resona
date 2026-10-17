import type { QueryClient } from "@tanstack/react-query";

import {
  attemptKeys,
  callRunKeys,
  runKeys,
  simulationKeys,
} from "@/lib/queryKeys";
import type { RunLiveEvent } from "@/lib/websocket/runLive";
import type { RunDto, RunProgressDto } from "@/types/api";

const RESULTS_EVENTS = new Set([
  "metric.computed",
  "judge.completed",
  "aggregate.updated",
  "composite.updated",
]);

// Folds one live event into the query cache. The cache stays authoritative:
// complete payloads patch, notifications invalidate.
export function applyRunLiveEvent(
  queryClient: QueryClient,
  runId: string,
  event: RunLiveEvent,
): void {
  const data = event.data ?? {};
  switch (event.type) {
    case "run.status.changed": {
      const status = data.status as RunDto["status"];
      queryClient.setQueryData<RunDto | undefined>(
        runKeys.detail(runId),
        (prev) => (prev ? { ...prev, status } : prev),
      );
      const run = queryClient.getQueryData<RunDto>(runKeys.detail(runId));
      if (run?.simulation_id) {
        void queryClient.invalidateQueries({
          queryKey: simulationKeys.runs(run.simulation_id),
        });
      }
      break;
    }
    case "call_run.status.changed":
      void queryClient.invalidateQueries({ queryKey: runKeys.callRuns(runId) });
      break;
    case "attempt.status.changed": {
      const callRunId = data.call_run_id as string | undefined;
      if (callRunId) {
        void queryClient.invalidateQueries({
          queryKey: callRunKeys.attempts(callRunId),
        });
      }
      void queryClient.invalidateQueries({ queryKey: attemptKeys.all });
      break;
    }
    case "run.progress":
      queryClient.setQueryData<RunProgressDto>(
        runKeys.progress(runId),
        data as unknown as RunProgressDto,
      );
      break;
    default:
      if (RESULTS_EVENTS.has(event.type)) {
        void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
        void queryClient.invalidateQueries({ queryKey: attemptKeys.all });
      }
  }
}
