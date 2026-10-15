import { Link, useNavigate, useParams } from "react-router-dom";
import { RefreshCw } from "lucide-react";

import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  useAgent,
  useDiscoverRevisions,
  useImportRevision,
} from "@/features/agents/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import type { RevisionDiscoveryCandidateDto } from "@/types/api";

export function AgentRevisionImportPage() {
  const { agentId = "" } = useParams();
  useDocumentTitle("Import revision");
  const navigate = useNavigate();
  const agentQuery = useAgent(agentId);
  const discoverQuery = useDiscoverRevisions(agentId);
  const importRevision = useImportRevision(agentId);

  async function onImport(candidate: RevisionDiscoveryCandidateDto) {
    if (!candidate.provider_revision_id) return;
    const revision = await importRevision.mutateAsync({
      input: {
        provider_revision_id: candidate.provider_revision_id,
        branch_id: candidate.branch_id ?? null,
      },
      idempotencyKey: newIdempotencyKey("agent:revision:import"),
    });
    navigate(`/app/agents/${agentId}/revisions/${revision.id}`);
  }

  if (discoverQuery.isLoading) {
    return <LoadingState label="Discovering provider revisions…" />;
  }
  if (discoverQuery.isError) {
    return (
      <ErrorState
        error={discoverQuery.error}
        title="Could not discover provider revisions."
        onRetry={() => void discoverQuery.refetch()}
      />
    );
  }

  const candidates = discoverQuery.data?.candidates ?? [];

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader
        title={`Import revision · ${agentQuery.data?.name ?? "Agent"}`}
        description={
          <Link
            to={`/app/agents/${agentId}/overview`}
            className="hover:text-foreground"
          >
            Back to agent
          </Link>
        }
      />

      <div className="space-y-3">
        {candidates.map((candidate) => (
          <Card
            key={candidate.provider_revision_id ?? "latest"}
            className="flex items-center justify-between gap-4 p-4"
          >
            <div className="flex flex-col gap-0.5">
              <span className="font-medium">
                {candidate.label ?? candidate.provider_revision_id ?? "—"}
              </span>
              {candidate.description && (
                <span className="text-micro text-muted-foreground">
                  {candidate.description}
                </span>
              )}
              {candidate.branch_id && (
                <span className="text-micro text-muted-foreground">
                  branch {candidate.branch_id}
                </span>
              )}
            </div>
            {candidate.already_imported ? (
              <Badge variant="secondary">Imported</Badge>
            ) : (
              <Button
                size="sm"
                disabled={importRevision.isPending}
                onClick={() => void onImport(candidate)}
              >
                {importRevision.isPending ? (
                  <RefreshCw className="size-4 animate-spin" />
                ) : (
                  "Import"
                )}
              </Button>
            )}
          </Card>
        ))}

        {candidates.length === 0 && (
          <Card className="p-6 text-center text-body-sm text-muted-foreground">
            No provider revisions available to import.
          </Card>
        )}
      </div>
    </div>
  );
}
