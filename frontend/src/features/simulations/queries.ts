import { useMemo } from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  simulationsApi,
  type RunCreateInput,
  type SimulationCreateInput,
} from "@/lib/api/simulations";
import { generationApi } from "@/lib/api/generation";
import { simulationKeys } from "@/lib/queryKeys";
import type { SimulationDto, SimulationPreferencesRequestDto } from "@/types/api";

export function useSimulations() {
  return useQuery({ queryKey: simulationKeys.all, queryFn: simulationsApi.list });
}

export function useSimulation(simulationId: string | undefined) {
  return useQuery({
    queryKey: simulationKeys.detail(simulationId ?? ""),
    queryFn: () => simulationsApi.get(simulationId as string),
    enabled: Boolean(simulationId),
  });
}

export function useSimulationRuns(simulationId: string | undefined) {
  return useQuery({
    queryKey: simulationKeys.runs(simulationId ?? ""),
    queryFn: () => simulationsApi.listRuns(simulationId as string),
    enabled: Boolean(simulationId),
    // Poll only while a run is queued/running; the run's live socket also
    // invalidates this list when it observes a status change.
    refetchInterval: (query) =>
      (query.state.data ?? []).some(
        (run) => run.status === "queued" || run.status === "running",
      )
        ? 5000
        : false,
  });
}

export function useCreateSimulation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      idempotencyKey,
    }: {
      input: SimulationCreateInput;
      idempotencyKey: string;
    }) => simulationsApi.create(input, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: simulationKeys.all });
    },
  });
}

export function useCreateRun(simulationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      idempotencyKey,
    }: {
      input: RunCreateInput;
      idempotencyKey: string;
    }) => simulationsApi.createRun(simulationId, input, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: simulationKeys.runs(simulationId),
      });
    },
  });
}

export function useSimulationPreferences() {
  return useMutation({
    mutationFn: (input: SimulationPreferencesRequestDto) =>
      generationApi.suggestPreferences(input),
  });
}

export interface SimulationsResult {
  simulations: SimulationDto[];
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  refetch: () => void;
}

// Simulations do not reference a revision directly — only a Run pins one — so a
// revision's simulations are the agent's simulations that have a run on it.
export function useAgentSimulations(
  agentTargetId: string | undefined,
): SimulationsResult {
  const query = useSimulations();
  const simulations = useMemo(
    () =>
      (query.data ?? []).filter(
        (simulation) => simulation.agent_target_id === agentTargetId,
      ),
    [query.data, agentTargetId],
  );
  return {
    simulations,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: () => void query.refetch(),
  };
}

export function useRevisionSimulations(
  simulations: SimulationDto[],
  revisionId: string | undefined,
): SimulationsResult {
  const runQueries = useQueries({
    queries: simulations.map((simulation) => ({
      queryKey: simulationKeys.runs(simulation.id),
      queryFn: () => simulationsApi.listRuns(simulation.id),
      enabled: Boolean(revisionId),
    })),
  });

  const filtered = useMemo(
    () =>
      simulations.filter((_, index) =>
        (runQueries[index]?.data ?? []).some(
          (run) => run.target_revision_id === revisionId,
        ),
      ),
    [simulations, runQueries, revisionId],
  );

  return {
    simulations: filtered,
    isLoading: runQueries.some((query) => query.isLoading),
    isError: runQueries.some((query) => query.isError),
    error: runQueries.find((query) => query.isError)?.error ?? null,
    refetch: () => runQueries.forEach((query) => void query.refetch()),
  };
}
