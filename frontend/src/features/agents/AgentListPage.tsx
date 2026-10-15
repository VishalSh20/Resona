import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Button } from "@/components/ui/button";
import {
  agentKeys,
  useAgents,
  useProviders,
} from "@/features/agents/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { agentsApi } from "@/lib/api/agents";
import type { AgentDto, AgentRevisionDto } from "@/types/api";

interface AgentRow {
  agent: AgentDto;
  latest?: AgentRevisionDto;
}

export function AgentListPage() {
  useDocumentTitle("Agents");
  const navigate = useNavigate();
  const agentsQuery = useAgents();
  const providersQuery = useProviders();
  const agents = agentsQuery.data ?? [];
  const providerNames = new Map(
    (providersQuery.data ?? []).map((provider) => [provider.id, provider.display_name]),
  );

  const revisionQueries = useQueries({
    queries: agents.map((agent) => ({
      queryKey: agentKeys.revisions(agent.id),
      queryFn: () => agentsApi.listRevisions(agent.id),
    })),
  });

  const columns: DataTableColumn<AgentRow>[] = [
    {
      key: "name",
      header: "Agent",
      render: (row) => (
        <div className="flex flex-col">
          <span className="font-medium">{row.agent.name}</span>
          {row.agent.external_agent_id && (
            <span className="text-micro text-muted-foreground">
              {row.agent.external_agent_id}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "provider",
      header: "Provider",
      render: (row) => providerNames.get(row.agent.provider_id) ?? row.agent.provider_id,
    },
    {
      key: "revision",
      header: "Latest revision",
      align: "right",
      render: (row) =>
        row.latest
          ? `rev ${row.latest.revision_no}${
              row.latest.provider_revision_id
                ? ` · ${row.latest.provider_revision_id}`
                : ""
            }`
          : "—",
    },
    {
      key: "type",
      header: "Kind",
      render: (row) => row.latest?.provider_revision_type ?? "—",
    },
  ];

  const rows: AgentRow[] = agents.map((agent, index) => {
    const revisions = revisionQueries[index]?.data ?? [];
    const latest = revisions.reduce<AgentRevisionDto | undefined>(
      (acc, revision) =>
        !acc || revision.revision_no > acc.revision_no ? revision : acc,
      undefined,
    );
    return { agent, latest };
  });

  if (agentsQuery.isLoading) {
    return <LoadingState label="Loading agents…" />;
  }
  if (agentsQuery.isError) {
    return (
      <ErrorState
        error={agentsQuery.error}
        title="Could not load agents."
        onRetry={() => void agentsQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        description="The external voice agents being evaluated."
        actions={
          <Button asChild>
            <Link to="/app/agents/new">
              <Plus className="size-4" /> New agent
            </Link>
          </Button>
        }
      />
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.agent.id}
        onRowClick={(row) => navigate(`/app/agents/${row.agent.id}/overview`)}
        emptyState="No agents yet. Add an agent to start evaluating it."
      />
    </div>
  );
}
