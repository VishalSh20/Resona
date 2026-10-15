import { Link, useNavigate, useParams } from "react-router-dom";
import { Plus, RefreshCw } from "lucide-react";

import { DataTable, type DataTableColumn } from "@/components/data/DataTable";
import { HashBadge } from "@/components/domain/HashBadge";
import { MetaList, type MetaItem } from "@/components/domain/MetaList";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  useAccounts,
  useAgent,
  useAgentRevisions,
  useProviders,
  useSyncAgent,
} from "@/features/agents/queries";
import { SimulationsSection } from "@/features/simulations/SimulationsSection";
import { useAgentSimulations } from "@/features/simulations/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatTimestamp } from "@/lib/formatters/format";
import {
  revisionHeadline,
  revisionTypeLabel,
  sourceKindLabel,
} from "@/lib/mappers/revision";
import type { AgentRevisionDto } from "@/types/api";

const columns: DataTableColumn<AgentRevisionDto>[] = [
  {
    key: "revision_no",
    header: "Revision",
    render: (row) => `rev ${row.revision_no}`,
  },
  {
    key: "provider_revision_type",
    header: "Type",
    render: (row) => revisionTypeLabel(row.provider_revision_type) ?? "—",
  },
  {
    key: "source_kind",
    header: "Source",
    render: (row) => sourceKindLabel(row.source_kind),
  },
  { key: "provider_revision_id", header: "Provider revision" },
  {
    key: "config_hash",
    header: "Config hash",
    render: (row) => <HashBadge hash={row.config_hash} />,
  },
  {
    key: "created_at",
    header: "Imported",
    render: (row) => formatTimestamp(row.created_at),
  },
];

export function AgentOverviewPage() {
  const { agentId } = useParams();
  useDocumentTitle("Agent");
  const navigate = useNavigate();
  const agentQuery = useAgent(agentId);
  const revisionsQuery = useAgentRevisions(agentId);
  const providersQuery = useProviders();
  const accountsQuery = useAccounts();
  const agentSimulations = useAgentSimulations(agentId);
  const syncAgent = useSyncAgent(agentId ?? "");

  if (agentQuery.isLoading) {
    return <LoadingState label="Loading agent…" />;
  }
  if (agentQuery.isError) {
    return (
      <ErrorState
        error={agentQuery.error}
        title="Could not load agent."
        onRetry={() => void agentQuery.refetch()}
      />
    );
  }

  const agent = agentQuery.data!;
  const revisions = revisionsQuery.data ?? [];
  const providerName =
    (providersQuery.data ?? []).find((p) => p.id === agent.provider_id)
      ?.display_name ?? agent.provider_id;
  const accountName =
    (accountsQuery.data ?? []).find(
      (account) => account.id === agent.integration_account_id,
    )?.name ?? agent.integration_account_id;
  const latest = revisions.reduce<AgentRevisionDto | undefined>(
    (acc, revision) =>
      !acc || revision.revision_no > acc.revision_no ? revision : acc,
    undefined,
  );

  const identityItems: MetaItem[] = [
    { label: "Identifier", value: agent.id },
    { label: "Provider", value: providerName },
    { label: "Account", value: accountName },
    { label: "External agent ID", value: agent.external_agent_id ?? "—" },
    {
      label: "Agent URL",
      value: agent.agent_url ? (
        <a
          href={agent.agent_url}
          target="_blank"
          rel="noreferrer noopener"
          className="break-all font-mono text-micro underline decoration-border underline-offset-2 hover:decoration-foreground"
        >
          {agent.agent_url}
        </a>
      ) : (
        "—"
      ),
    },
    { label: "Revisions", value: revisions.length.toString() },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title={agent.name}
        description={agent.external_agent_id ?? undefined}
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              disabled={syncAgent.isPending}
              onClick={() => void syncAgent.mutate()}
            >
              <RefreshCw className="size-4" />
              {syncAgent.isPending ? "Syncing…" : "Sync"}
            </Button>
            <Button asChild>
              <Link to={`/app/agents/${agent.id}/revisions/import`}>
                <Plus className="size-4" /> Add revision
              </Link>
            </Button>
          </div>
        }
      />

      {syncAgent.isError && (
        <ErrorState error={syncAgent.error} title="Could not sync agent." />
      )}

      <Card className="gap-4 p-6">
        <h2 className="text-title-sm font-medium">Agent</h2>
        <MetaList items={identityItems} />
      </Card>

      {latest ? (
        <LatestRevisionCard agentId={agent.id} revision={latest} />
      ) : (
        <Card className="gap-2 p-6">
          <h2 className="text-title-sm font-medium">Latest revision</h2>
          <p className="text-body-sm text-muted-foreground">
            This agent has no revisions yet. Sync the provider or add a revision
            to capture its configuration.
          </p>
        </Card>
      )}

      <section className="space-y-3">
        <h2 className="text-title-sm font-medium">Revisions</h2>
        {revisionsQuery.isError ? (
          <ErrorState
            error={revisionsQuery.error}
            title="Could not load revisions."
            onRetry={() => void revisionsQuery.refetch()}
          />
        ) : (
          <DataTable
            columns={columns}
            rows={revisions}
            rowKey={(row) => row.id}
            onRowClick={(row) =>
              navigate(`/app/agents/${agentId}/revisions/${row.id}`)
            }
            emptyState="No revisions yet."
          />
        )}
      </section>

      <SimulationsSection
        simulations={agentSimulations.simulations}
        isLoading={agentSimulations.isLoading}
        isError={agentSimulations.isError}
        error={agentSimulations.error}
        onRetry={agentSimulations.refetch}
        emptyMessage="No simulations for this agent yet. Run a simulation from a revision to start one."
      />
    </div>
  );
}

function LatestRevisionCard({
  agentId,
  revision,
}: {
  agentId: string;
  revision: AgentRevisionDto;
}) {
  const headline = revisionHeadline(revision);
  const items: MetaItem[] = [
    {
      label: "Type",
      value: revisionTypeLabel(revision.provider_revision_type) ?? "—",
    },
    { label: "Source", value: sourceKindLabel(revision.source_kind) },
  ];
  if (headline.model) items.push({ label: "Model", value: headline.model });
  if (headline.voice) items.push({ label: "Voice", value: headline.voice });
  if (headline.toolCount != null) {
    items.push({ label: "Tools", value: String(headline.toolCount) });
  }
  items.push(
    { label: "Provider revision", value: revision.provider_revision_id ?? "—" },
    { label: "Config hash", value: <HashBadge hash={revision.config_hash} /> },
    { label: "Imported", value: formatTimestamp(revision.created_at) },
  );

  return (
    <Card className="gap-4 p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-title-sm font-medium">Latest revision</h2>
          <Badge variant="secondary">rev {revision.revision_no}</Badge>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to={`/app/agents/${agentId}/revisions/${revision.id}`}>
            Inspect revision
          </Link>
        </Button>
      </div>
      {revision.first_message && (
        <p className="line-clamp-3 text-body-sm text-muted-foreground">
          {revision.first_message}
        </p>
      )}
      <MetaList items={items} />
    </Card>
  );
}
