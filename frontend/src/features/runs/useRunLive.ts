import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { attemptKeys, runKeys, simulationKeys } from "@/lib/queryKeys";
import { connectRunLive } from "@/lib/websocket/runLive";
import type { LiveConnectionState } from "@/types/ui";

import { applyRunLiveEvent } from "./runLiveReducer";

// Subscribes to the run's live feed and folds each event into the query cache.
export function useRunLive(runId: string | undefined): {
  connectionState: LiveConnectionState;
} {
  const queryClient = useQueryClient();
  const [connectionState, setConnectionState] =
    useState<LiveConnectionState>("idle");

  useEffect(() => {
    if (!runId) return;

    const disconnect = connectRunLive({
      runId,
      onEvent: (event) => applyRunLiveEvent(queryClient, runId, event),
      onStateChange: setConnectionState,
      onReconnect: () => {
        // No replay cursor: refetch authoritative snapshots on (re)connect.
        void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
        void queryClient.invalidateQueries({
          queryKey: runKeys.callRuns(runId),
        });
        void queryClient.invalidateQueries({ queryKey: simulationKeys.all });
        void queryClient.invalidateQueries({ queryKey: attemptKeys.all });
      },
    });

    return disconnect;
  }, [runId, queryClient]);

  return { connectionState };
}
