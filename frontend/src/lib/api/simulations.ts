import { http } from "./client";
import type {
  RunDto,
  SimulationCreatedDto,
  SimulationDto,
} from "@/types/api";

export interface SimulationCreateInput {
  name: string;
  description?: string | null;
  agent_target_id: string;
  target_revision_id: string;
  languages: string[];
  call_ambience: string[];
  metric_set: string[];
  personalities: string[];
  knowledge_base: Record<string, unknown>;
  evaluator_count: number;
}

export interface RunCreateInput {
  target_revision_id: string;
}

export const simulationsApi = {
  list: () => http.get<SimulationDto[]>("/simulations"),
  get: (simulationId: string) =>
    http.get<SimulationDto>(`/simulations/${simulationId}`),
  create: (input: SimulationCreateInput, idempotencyKey: string) =>
    http.post<SimulationCreatedDto>("/simulations", input, { idempotencyKey }),
  listRuns: (simulationId: string) =>
    http.get<RunDto[]>(`/simulations/${simulationId}/runs`),
  createRun: (
    simulationId: string,
    input: RunCreateInput,
    idempotencyKey: string,
  ) =>
    http.post<RunDto>(`/simulations/${simulationId}/runs`, input, {
      idempotencyKey,
    }),
};
