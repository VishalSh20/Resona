import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  agentsApi,
  type AgentCreateInput,
} from "@/lib/api/agents";
import {
  integrationsApi,
  type IntegrationAccountCreateInput,
} from "@/lib/api/integrations";
import type { RevisionImportRequestDto } from "@/types/api";

export const agentKeys = {
  all: ["agents"] as const,
  detail: (agentId: string) => ["agents", agentId] as const,
  revisions: (agentId: string) => ["agents", agentId, "revisions"] as const,
  revision: (agentId: string, revisionId: string) =>
    ["agents", agentId, "revisions", revisionId] as const,
  discover: (agentId: string) => ["agents", agentId, "discover"] as const,
};

export const integrationKeys = {
  providers: ["integrations", "providers"] as const,
  accounts: ["integrations", "accounts"] as const,
};

export function useProviders() {
  return useQuery({
    queryKey: integrationKeys.providers,
    queryFn: integrationsApi.listProviders,
  });
}

export function useAccounts() {
  return useQuery({
    queryKey: integrationKeys.accounts,
    queryFn: integrationsApi.listAccounts,
  });
}

export function useAgents() {
  return useQuery({ queryKey: agentKeys.all, queryFn: agentsApi.list });
}

export function useAgent(agentId: string | undefined) {
  return useQuery({
    queryKey: agentKeys.detail(agentId ?? ""),
    queryFn: () => agentsApi.get(agentId as string),
    enabled: Boolean(agentId),
  });
}

export function useAgentRevisions(agentId: string | undefined) {
  return useQuery({
    queryKey: agentKeys.revisions(agentId ?? ""),
    queryFn: () => agentsApi.listRevisions(agentId as string),
    enabled: Boolean(agentId),
  });
}

export function useAgentRevision(
  agentId: string | undefined,
  revisionId: string | undefined,
) {
  return useQuery({
    queryKey: agentKeys.revision(agentId ?? "", revisionId ?? ""),
    queryFn: () => agentsApi.getRevision(agentId as string, revisionId as string),
    enabled: Boolean(agentId && revisionId),
  });
}

export function useDiscoverRevisions(agentId: string | undefined) {
  return useQuery({
    queryKey: agentKeys.discover(agentId ?? ""),
    queryFn: () => agentsApi.discoverRevisions(agentId as string),
    enabled: Boolean(agentId),
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: IntegrationAccountCreateInput) =>
      integrationsApi.createAccount(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: integrationKeys.accounts });
    },
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AgentCreateInput) => agentsApi.create(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.all });
    },
  });
}

export function useImportRevision(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      input,
      idempotencyKey,
    }: {
      input: RevisionImportRequestDto;
      idempotencyKey: string;
    }) => agentsApi.importRevision(agentId, input, idempotencyKey),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.revisions(agentId) });
    },
  });
}

export function useSyncAgent(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => agentsApi.sync(agentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentKeys.revisions(agentId) });
    },
  });
}
