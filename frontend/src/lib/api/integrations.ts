import { http } from "./client";
import type { IntegrationAccountDto, IntegrationProviderDto } from "@/types/api";

export interface IntegrationAccountCreateInput {
  provider_id: string;
  name: string;
  config: Record<string, unknown>;
  secrets: Record<string, string>;
}

export const integrationsApi = {
  listProviders: () => http.get<IntegrationProviderDto[]>("/integrations/providers"),
  listAccounts: () => http.get<IntegrationAccountDto[]>("/integrations/accounts"),
  createAccount: (input: IntegrationAccountCreateInput) =>
    http.post<IntegrationAccountDto>("/integrations/accounts", input),
};
