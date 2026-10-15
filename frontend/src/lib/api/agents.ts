import { http } from "./client";
import type {
  AgentCreatedDto,
  AgentDto,
  AgentPreviewRequestDto,
  AgentPreviewResponseDto,
  AgentRevisionDto,
  RevisionDiscoveryResponseDto,
  RevisionImportRequestDto,
  TargetConnectionUpsertDto,
} from "@/types/api";

export interface AgentCreateInput {
  provider_id: string;
  integration_account_id: string;
  // Provider-backed agents: the provider external id to introspect.
  external_agent_id?: string;
  // Manual / custom agents: a name (+ optional reachable websocket URL).
  name?: string;
  agent_url?: string;
}

export const agentsApi = {
  list: () => http.get<AgentDto[]>("/targets"),
  get: (agentId: string) => http.get<AgentDto>(`/targets/${agentId}`),
  create: (input: AgentCreateInput) => http.post<AgentCreatedDto>("/targets", input),
  preview: (input: AgentPreviewRequestDto) =>
    http.post<AgentPreviewResponseDto>("/targets/preview", input),
  listRevisions: (agentId: string) =>
    http.get<AgentRevisionDto[]>(`/targets/${agentId}/revisions`),
  getRevision: (agentId: string, revisionId: string) =>
    http.get<AgentRevisionDto>(`/targets/${agentId}/revisions/${revisionId}`),
  discoverRevisions: (agentId: string) =>
    http.post<RevisionDiscoveryResponseDto>(
      `/targets/${agentId}/revisions/discover`,
    ),
  importRevision: (
    agentId: string,
    input: RevisionImportRequestDto,
    idempotencyKey: string,
  ) =>
    http.post<AgentRevisionDto>(`/targets/${agentId}/revisions`, input, {
      idempotencyKey,
    }),
  sync: (agentId: string) => http.post<AgentRevisionDto>(`/targets/${agentId}/sync`),
  setConnection: (agentId: string, input: TargetConnectionUpsertDto) =>
    http.post<AgentRevisionDto>(`/targets/${agentId}/connection`, input),
};
