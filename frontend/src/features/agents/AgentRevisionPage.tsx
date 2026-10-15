import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Play } from "lucide-react";

import { ConfigInspector } from "@/components/domain/ConfigInspector";
import { CopyableId } from "@/components/domain/CopyableId";
import { HashBadge } from "@/components/domain/HashBadge";
import { JsonInspector } from "@/components/domain/JsonInspector";
import { MetaList, type MetaItem } from "@/components/domain/MetaList";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { RunSimulationDialog } from "@/features/agents/RunSimulationDialog";
import { useAgent, useAgentRevision } from "@/features/agents/queries";
import { SimulationsSection } from "@/features/simulations/SimulationsSection";
import {
  useAgentSimulations,
  useRevisionSimulations,
} from "@/features/simulations/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatTimestamp } from "@/lib/formatters/format";
import {
  revisionConfigSections,
  revisionHeadline,
  revisionTypeLabel,
  sourceKindLabel,
} from "@/lib/mappers/revision";
import type { AgentRevisionDto } from "@/types/api";

export function AgentRevisionPage() {
  const { agentId = "", revisionId = "" } = useParams();
  useDocumentTitle("Agent revision");
  const revisionQuery = useAgentRevision(agentId, revisionId);
  const agentQuery = useAgent(agentId);
  const agentSimulations = useAgentSimulations(agentId);
  const revisionSimulations = useRevisionSimulations(
    agentSimulations.simulations,
    revisionId,
  );
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  if (revisionQuery.isLoading) {
    return <LoadingState label="Loading revision…" />;
  }
  if (revisionQuery.isError) {
    return (
      <ErrorState
        error={revisionQuery.error}
        title="Could not load agent revision."
        onRetry={() => void revisionQuery.refetch()}
      />
    );
  }

  const revision = revisionQuery.data!;
  const agentName = agentQuery.data?.name ?? "Agent";
  const typeLabel =
    revisionTypeLabel(revision.provider_revision_type) ??
    sourceKindLabel(revision.source_kind);

  const retrySimulations = () => {
    void agentSimulations.refetch();
    revisionSimulations.refetch();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={agentName}
        description={
          <Link
            to={`/app/agents/${agentId}/overview`}
            className="hover:text-foreground"
          >
            Back to agent
          </Link>
        }
        meta={
          <>
            <Badge variant="secondary">rev {revision.revision_no}</Badge>
            <Badge variant="outline">{typeLabel}</Badge>
            <CopyableId id={revision.id} />
            <HashBadge hash={revision.config_hash} />
          </>
        }
        actions={
          <Button type="button" onClick={() => setRunDialogOpen(true)}>
            <Play className="size-4" />
            Run a simulation
          </Button>
        }
      />

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="simulations">Simulations</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <RevisionOverview revision={revision} />
        </TabsContent>

        <TabsContent value="configuration">
          <RevisionConfiguration revision={revision} />
        </TabsContent>

        <TabsContent value="simulations">
          <SimulationsSection
            simulations={revisionSimulations.simulations}
            isLoading={
              agentSimulations.isLoading || revisionSimulations.isLoading
            }
            isError={agentSimulations.isError || revisionSimulations.isError}
            error={agentSimulations.error ?? revisionSimulations.error}
            onRetry={retrySimulations}
            emptyMessage="No simulations run this revision yet. Use “Run a simulation” to start one."
          />
        </TabsContent>
      </Tabs>

      <RunSimulationDialog
        open={runDialogOpen}
        onOpenChange={setRunDialogOpen}
        agentId={agentId}
        agentName={agentName}
        revisionId={revision.id}
        revisionLabel={`rev ${revision.revision_no}`}
        simulations={agentSimulations.simulations}
        simulationsLoading={agentSimulations.isLoading}
      />
    </div>
  );
}

function RevisionOverview({ revision }: { revision: AgentRevisionDto }) {
  const headline = revisionHeadline(revision);
  const facts: MetaItem[] = [];
  if (headline.model) facts.push({ label: "Model", value: headline.model });
  if (headline.voice) facts.push({ label: "Voice", value: headline.voice });
  if (headline.language) {
    facts.push({ label: "Language", value: headline.language });
  }
  if (headline.toolCount != null) {
    facts.push({ label: "Tools", value: String(headline.toolCount) });
  }
  if (headline.knowledgeCount != null) {
    facts.push({
      label: "Knowledge bases",
      value: String(headline.knowledgeCount),
    });
  }
  if (headline.variableCount != null) {
    facts.push({ label: "Variables", value: String(headline.variableCount) });
  }

  return (
    <div className="space-y-4">
      <Card className="gap-3 p-6">
        <h2 className="text-title-sm font-medium">Opening message</h2>
        {revision.first_message ? (
          <p className="whitespace-pre-wrap text-body-sm leading-relaxed">
            {revision.first_message}
          </p>
        ) : (
          <p className="text-body-sm text-muted-foreground">
            This revision does not define an opening message.
          </p>
        )}
      </Card>

      {facts.length > 0 && (
        <Card className="gap-3 p-6">
          <h2 className="text-title-sm font-medium">
            Configuration at a glance
          </h2>
          <MetaList items={facts} />
        </Card>
      )}

      <Card className="gap-4 p-6">
        <h2 className="text-title-sm font-medium">Revision details</h2>
        <MetaList items={revisionDetailItems(revision)} />
        {revision.description && (
          <div className="space-y-1 border-t border-border pt-4">
            <p className="text-label uppercase tracking-wide text-muted-foreground">
              Description
            </p>
            <p className="whitespace-pre-wrap text-body-sm leading-relaxed">
              {revision.description}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

function revisionDetailItems(revision: AgentRevisionDto): MetaItem[] {
  return [
    { label: "Revision", value: `rev ${revision.revision_no}` },
    { label: "Provider revision", value: revision.provider_revision_id ?? "—" },
    {
      label: "Revision type",
      value: revisionTypeLabel(revision.provider_revision_type) ?? "—",
    },
    { label: "Source", value: sourceKindLabel(revision.source_kind) },
    { label: "Label", value: revision.revision_label ?? "—" },
    { label: "Branch", value: revision.source_branch_id ?? "—" },
    { label: "Config hash", value: <HashBadge hash={revision.config_hash} /> },
    {
      label: "Provider updated",
      value: formatTimestamp(revision.source_updated_at),
    },
    { label: "Imported", value: formatTimestamp(revision.created_at) },
  ];
}

function RevisionConfiguration({ revision }: { revision: AgentRevisionDto }) {
  const sections = revisionConfigSections(revision);

  return (
    <div className="space-y-4">
      {sections.length === 0 ? (
        <Card className="p-6 text-body-sm text-muted-foreground">
          This revision carries no normalized configuration. See the raw
          provider payload below.
        </Card>
      ) : (
        sections.map(({ section, value }) => (
          <Card key={section.key} className="gap-3 p-6">
            <div>
              <h2 className="text-title-sm font-medium">{section.label}</h2>
              <p className="text-body-sm text-muted-foreground">
                {section.description}
              </p>
            </div>
            <ConfigInspector value={value} />
          </Card>
        ))
      )}

      <Card className="gap-3 p-6">
        <div>
          <h2 className="text-title-sm font-medium">Raw payload</h2>
          <p className="text-body-sm text-muted-foreground">
            The exact payloads behind this revision, for forensic comparison.
            The structured configuration above is the primary view.
          </p>
        </div>
        <details className="group rounded-lg border border-border">
          <summary className="cursor-pointer list-none px-3 py-2 text-body-sm font-medium marker:hidden">
            Normalized payload · canonical_config
          </summary>
          <div className="border-t border-border p-3">
            <JsonInspector
              value={revision.canonical_config}
              label="canonical_config"
              maxHeight="20rem"
            />
          </div>
        </details>
        <details className="group rounded-lg border border-border">
          <summary className="cursor-pointer list-none px-3 py-2 text-body-sm font-medium marker:hidden">
            Provider payload · source_config
          </summary>
          <div className="border-t border-border p-3">
            <JsonInspector
              value={revision.source_config}
              label="source_config"
              maxHeight="20rem"
            />
          </div>
        </details>
      </Card>
    </div>
  );
}
