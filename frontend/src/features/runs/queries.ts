import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { runsApi, type RunEvaluatorUpdateInput } from "@/lib/api/runs";
import { resultsApi } from "@/lib/api/results";
import type {
  GenerateEvaluationsRequestDto,
  JudgeExecutionDto,
  RunResultsReadDto,
} from "@/types/api";
import { callRunKeys, runKeys, simulationKeys } from "@/lib/queryKeys";

const ACTIVE_RUN_STATUSES = new Set(["queued", "running"]);

export function useRunCallRuns(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: runKeys.callRuns(runId ?? ""),
    queryFn: () => runsApi.listCallRuns(runId as string),
    enabled: Boolean(runId) && enabled,
    // Keep the calls list fresh while the run is executing; the live socket
    // also invalidates it, this is the fallback when the socket is disconnected.
    refetchInterval: (query) =>
      (query.state.data ?? []).some((callRun) =>
        ACTIVE_RUN_STATUSES.has(callRun.status),
      )
        ? 5000
        : false,
  });
}

export function useCallRunAttempts(callRunId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: callRunKeys.attempts(callRunId ?? ""),
    queryFn: () => runsApi.listCallRunAttempts(callRunId as string),
    enabled: Boolean(callRunId) && enabled,
  });
}

export function useRun(runId: string | undefined) {
  return useQuery({
    queryKey: runKeys.detail(runId ?? ""),
    queryFn: () => runsApi.get(runId as string),
    enabled: Boolean(runId),
  });
}

export function useRunEvaluators(runId: string | undefined) {
  return useQuery({
    queryKey: runKeys.evaluators(runId ?? ""),
    queryFn: () => runsApi.listEvaluators(runId as string),
    enabled: Boolean(runId),
  });
}

export function useGenerateEvaluators(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      idempotencyKey,
    }: {
      input: GenerateEvaluationsRequestDto;
      idempotencyKey: string;
    }) => runsApi.generateEvaluators(runId, input, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: runKeys.evaluators(runId) });
      void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
    },
  });
}

export function useUpdateEvaluator(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      evaluatorId,
      input,
    }: {
      evaluatorId: string;
      input: RunEvaluatorUpdateInput;
    }) => runsApi.updateEvaluator(runId, evaluatorId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: runKeys.evaluators(runId) });
    },
  });
}

export function useMarkRunReady(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runsApi.markReady(runId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
      void queryClient.invalidateQueries({ queryKey: simulationKeys.all });
    },
  });
}

export function useStartRun(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => runsApi.start(runId),
    onSuccess: (run) => {
      queryClient.setQueryData(runKeys.detail(runId), run);
      void queryClient.invalidateQueries({ queryKey: runKeys.detail(runId) });
      void queryClient.invalidateQueries({ queryKey: runKeys.callRuns(runId) });
    },
  });
}

export function useRunResults(runId: string | undefined, poll = false) {
  return useQuery<RunResultsReadDto, Error>({
    queryKey: runKeys.results(runId ?? ""),
    queryFn: () => runsApi.getResults(runId as string),
    enabled: Boolean(runId),
    refetchInterval: poll ? 5000 : false,
  });
}

export function useJudgeExecution(judgeExecutionId: string | null | undefined) {
  return useQuery<JudgeExecutionDto, Error>({
    queryKey: ["judge-executions", judgeExecutionId],
    queryFn: () => resultsApi.getJudgeExecution(judgeExecutionId as string),
    enabled: Boolean(judgeExecutionId),
  });
}
