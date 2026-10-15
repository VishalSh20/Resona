import { http } from "./client";
import type {
  CallAttemptDto,
  CallRunDto,
  GenerateEvaluationsRequestDto,
  GenerateEvaluationsResponseDto,
  RunDto,
  RunEvaluatorDto,
  RunEvaluatorLanguages,
  RunResultsReadDto,
} from "@/types/api";

export interface RunEvaluatorUpdateInput {
  scenario?: string;
  expected_output_prompt?: string;
  metrics?: string[];
  languages?: RunEvaluatorLanguages;
  personality?: string[];
}

export const runsApi = {
  get: (runId: string) => http.get<RunDto>(`/runs/${runId}`),
  listEvaluators: (runId: string) =>
    http.get<RunEvaluatorDto[]>(`/runs/${runId}/evaluators`),
  updateEvaluator: (
    runId: string,
    evaluatorId: string,
    input: RunEvaluatorUpdateInput,
  ) => http.patch<RunEvaluatorDto>(`/runs/${runId}/evaluators/${evaluatorId}`, input),
  generateEvaluators: (
    runId: string,
    input: GenerateEvaluationsRequestDto,
    idempotencyKey: string,
  ) =>
    http.post<GenerateEvaluationsResponseDto>(
      `/runs/${runId}/evaluators/generate`,
      input,
      { idempotencyKey },
    ),
  markReady: (runId: string) => http.post<RunDto>(`/runs/${runId}/ready`),
  start: (runId: string) => http.post<RunDto>(`/runs/${runId}/start`),
  listCallRuns: (runId: string) => http.get<CallRunDto[]>(`/runs/${runId}/call-runs`),
  listCallRunAttempts: (callRunId: string) =>
    http.get<CallAttemptDto[]>(`/call-runs/${callRunId}/attempts`),
  getResults: (runId: string) => http.get<RunResultsReadDto>(`/runs/${runId}/results`),
};
