import { useMemo } from "react";
import { useQueries, useQuery, type Query } from "@tanstack/react-query";

import { resultsApi } from "@/lib/api/results";
import { simulationsApi } from "@/lib/api/simulations";
import { runKeys, simulationKeys } from "@/lib/queryKeys";
import { useSimulations } from "@/features/simulations/queries";
import type { RunDto } from "@/types/api";

export interface OverviewRunsResult {
  runs: RunDto[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => void;
}

// There is no cross-simulation runs endpoint, so the overview fans out one runs
// query per simulation (the same pattern as `useRevisionSimulations`) and
// flattens the results.
export function useAllRuns(): OverviewRunsResult {
  const simulationsQuery = useSimulations();
  const runQueries = useQueries({
    queries: (simulationsQuery.data ?? []).map((simulation) => ({
      queryKey: simulationKeys.runs(simulation.id),
      queryFn: () => simulationsApi.listRuns(simulation.id),
      refetchInterval: (query: Query<RunDto[], Error>) =>
        (query.state.data ?? []).some(
          (run) => run.status === "queued" || run.status === "running",
        )
          ? 5000
          : false,
    })),
  });

  const runs = useMemo(
    () => runQueries.flatMap((query) => query.data ?? []),
    [runQueries],
  );

  return {
    runs,
    isLoading: simulationsQuery.isLoading || runQueries.some((q) => q.isLoading),
    isError: simulationsQuery.isError || runQueries.some((q) => q.isError),
    error:
      simulationsQuery.error ?? runQueries.find((q) => q.isError)?.error ?? null,
    refetch: () => {
      void simulationsQuery.refetch();
      runQueries.forEach((query) => void query.refetch());
    },
  };
}

// A run with no composite score yet returns 404, so don't retry.
export function useRunComposite(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: runKeys.composite(runId ?? ""),
    queryFn: () => resultsApi.getComposite(runId as string),
    enabled: Boolean(runId) && enabled,
    retry: false,
  });
}
