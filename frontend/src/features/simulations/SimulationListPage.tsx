import { Link, useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Button } from "@/components/ui/button";
import { useSimulations } from "@/features/simulations/queries";
import { useAgents } from "@/features/agents/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import type { SimulationDto } from "@/types/api";

const columns: DataTableColumn<SimulationDto>[] = [
  {
    key: "name",
    header: "Simulation",
    render: (row) => (
      <div className="flex flex-col">
        <span className="font-medium">{row.name}</span>
        {row.description && (
          <span className="line-clamp-1 text-micro text-muted-foreground">
            {row.description}
          </span>
        )}
      </div>
    ),
  },
  {
    key: "metrics",
    header: "Metrics",
    align: "right",
    render: (row) => row.metric_set.length.toString(),
  },
  {
    key: "personalities",
    header: "Personalities",
    align: "right",
    render: (row) => row.personalities.length.toString(),
  },
  {
    key: "evaluator_count",
    header: "Evaluators",
    align: "right",
    render: (row) => row.evaluator_count.toString(),
  },
];

export function SimulationListPage() {
  useDocumentTitle("Simulations");
  const navigate = useNavigate();
  const simulationsQuery = useSimulations();
  const agentsQuery = useAgents();

  if (simulationsQuery.isLoading) {
    return <LoadingState label="Loading simulations…" />;
  }
  if (simulationsQuery.isError) {
    return (
      <ErrorState
        error={simulationsQuery.error}
        title="Could not load simulations."
        onRetry={() => void simulationsQuery.refetch()}
      />
    );
  }

  const agents = new Map(
    (agentsQuery.data ?? []).map((agent) => [agent.id, agent.name]),
  );
  const rows: SimulationDto[] = simulationsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Simulations"
        description="Reusable evaluation spaces: the agent, caller languages, call ambience, metrics and personalities an evaluation may cover."
        actions={
          <Button asChild>
            <Link to="/app/simulations/new">
              <Plus className="size-4" /> New simulation
            </Link>
          </Button>
        }
      />
      <DataTable
        columns={[
          ...columns,
          {
            key: "agent",
            header: "Agent",
            render: (row) =>
              row.agent_target_id
                ? (agents.get(row.agent_target_id) ?? "—")
                : "—",
          },
        ]}
        rows={rows}
        rowKey={(row) => row.id}
        onRowClick={(row) => navigate(`/app/simulations/${row.id}`)}
        emptyState="No simulations yet. Create a simulation to define what your voice agent should be measured against."
      />
    </div>
  );
}
