import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plus } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { MetaList } from "@/components/domain/MetaList";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateRun,
  useSimulation,
  useSimulationRuns,
} from "@/features/simulations/queries";
import { useAgentRevisions, useAgents } from "@/features/agents/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import { callAmbienceLabel } from "@/lib/constants/ambience";
import { languageLabel } from "@/lib/constants/languages";
import { metricLabel } from "@/lib/constants/metrics";
import { personalityLabel } from "@/lib/constants/personalities";
import { formatTimestamp } from "@/lib/formatters/format";
import type { RunDto } from "@/types/api";

const runColumns: DataTableColumn<RunDto>[] = [
  { key: "status", header: "Status", render: (row) => <StatusBadge status={row.status} /> },
  {
    key: "target_revision_id",
    header: "Agent revision",
    render: (row) => <span className="font-mono">{row.target_revision_id}</span>,
  },
  {
    key: "evaluator_count",
    header: "Evaluators",
    align: "right",
    render: (row) => row.evaluator_count.toString(),
  },
  {
    key: "created_at",
    header: "Created",
    render: (row) => formatTimestamp(row.created_at),
  },
];

export function SimulationOverviewPage() {
  const { simulationId } = useParams();
  useDocumentTitle("Simulation");
  const navigate = useNavigate();
  const simulationQuery = useSimulation(simulationId);
  const runsQuery = useSimulationRuns(simulationId);
  const agentsQuery = useAgents();

  const agentTargetId = simulationQuery.data?.agent_target_id;
  const revisionsQuery = useAgentRevisions(agentTargetId);
  const createRun = useCreateRun(simulationId ?? "");

  const [revisionId, setRevisionId] = useState("");

  if (simulationQuery.isLoading) {
    return <LoadingState label="Loading simulation…" />;
  }
  if (simulationQuery.isError) {
    return (
      <ErrorState
        error={simulationQuery.error}
        title="Could not load simulation."
        onRetry={() => void simulationQuery.refetch()}
      />
    );
  }

  const simulation = simulationQuery.data!;
  const agent = (agentsQuery.data ?? []).find(
    (t) => t.id === simulation.agent_target_id,
  );
  const runs = runsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={simulation.name}
        description={simulation.description ?? undefined}
      />

      <Card className="gap-4 p-6">
        <MetaList
          items={[
            { label: "Identifier", value: <span className="font-mono">{simulation.id}</span> },
            { label: "Agent", value: agent?.name ?? simulation.agent_target_id },
            { label: "Evaluator count", value: simulation.evaluator_count.toString() },
            {
              label: "Languages",
              value: simulation.languages.map(languageLabel).join(", ") || "—",
            },
            {
              label: "Call ambience",
              value:
                simulation.call_ambience.map(callAmbienceLabel).join(", ") || "—",
            },
            {
              label: "Metrics",
              value: simulation.metric_set.map(metricLabel).join(", ") || "—",
            },
            {
              label: "Personalities",
              value: simulation.personalities.map(personalityLabel).join(", ") || "—",
            },
          ]}
        />
      </Card>

      <section className="space-y-3">
        <h2 className="text-title-sm font-medium">Runs</h2>

        <Card className="gap-3 p-4">
          <p className="text-body-sm text-muted-foreground">
            A run instantiates this simulation against a revision of its agent.
            Runs after the first inherit the first run's evaluators.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <Select value={revisionId || undefined} onValueChange={setRevisionId}>
              <SelectTrigger className="w-64">
                <SelectValue placeholder="Select a target revision" />
              </SelectTrigger>
              <SelectContent>
                {(revisionsQuery.data ?? []).map((revision) => (
                  <SelectItem key={revision.id} value={revision.id}>
                    rev {revision.revision_no} ·{" "}
                    {revision.provider_revision_id ?? revision.source_kind}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              disabled={!revisionId || createRun.isPending}
              onClick={async () => {
                const run = await createRun.mutateAsync({
                  input: { target_revision_id: revisionId },
                  idempotencyKey: newIdempotencyKey("run:create"),
                });
                navigate(`/app/simulations/${simulation.id}/runs/${run.id}`);
              }}
            >
              <Plus className="size-4" />
              New run
            </Button>
          </div>
          {createRun.isError && (
            <ErrorState error={createRun.error} title="Could not create run." />
          )}
        </Card>

        <DataTable
          columns={runColumns}
          rows={runs}
          rowKey={(row) => row.id}
          onRowClick={(row) =>
            navigate(`/app/simulations/${simulation.id}/runs/${row.id}`)
          }
          emptyState="No runs yet. Runs are created against revisions of this simulation's agent."
        />
      </section>
    </div>
  );
}
