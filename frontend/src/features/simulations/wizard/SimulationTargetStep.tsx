import { Link } from "react-router-dom";

import { ProviderLogo } from "@/components/brand/ProviderLogo";
import { FormField } from "@/components/forms/FormField";
import { SelectableCard } from "@/components/forms/SelectableCard";
import { SelectionGrid } from "@/components/forms/SelectionGrid";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { SimulationDraft } from "@/features/simulations/wizard/types";
import type {
  AgentDto,
  AgentRevisionDto,
  IntegrationProviderDto,
} from "@/types/api";

interface SimulationTargetStepProps {
  draft: SimulationDraft;
  update: (patch: Partial<SimulationDraft>) => void;
  agents: AgentDto[];
  providers: Map<string, IntegrationProviderDto>;
  revisions: AgentRevisionDto[];
  revisionsLoading: boolean;
  touched: Record<string, boolean>;
  touch: (field: string) => void;
}

export function SimulationTargetStep({
  draft,
  update,
  agents,
  providers,
  revisions,
  revisionsLoading,
  touched,
  touch,
}: SimulationTargetStepProps) {
  const selectedAgent = agents.find((a) => a.id === draft.agentTargetId);

  return (
    <div className="space-y-6">
      <FormField
        label="Name"
        htmlFor="simulation-name"
        required
        error={
          touched.name && !draft.name.trim() ? "Give the simulation a name." : undefined
        }
      >
        <Input
          id="simulation-name"
          value={draft.name}
          onChange={(event) => update({ name: event.target.value })}
          onBlur={() => touch("name")}
          placeholder="Credit card support"
        />
      </FormField>

      <section className="space-y-3">
        <div>
          <h2 className="text-title-sm font-medium">Select Target</h2>
          <p className="text-body-sm text-muted-foreground">
            Choose the voice agent and revision this simulation will test.
          </p>
        </div>

        {agents.length === 0 ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-dashed border-border px-4 py-6">
            <p className="text-body-sm text-muted-foreground">
              No agents yet. Connect one before creating a simulation.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/app/agents/new">Add agent</Link>
            </Button>
          </div>
        ) : (
          <SelectionGrid minWidth="240px">
            {agents.map((agent) => {
              const provider = providers.get(agent.provider_id);
              return (
                <SelectableCard
                  key={agent.id}
                  selected={draft.agentTargetId === agent.id}
                  onToggle={() =>
                    update({ agentTargetId: agent.id, targetRevisionId: "" })
                  }
                  leading={<ProviderLogo slug={provider?.slug} />}
                  title={agent.name}
                  description={
                    provider?.display_name ?? agent.external_agent_id ?? "Agent"
                  }
                />
              );
            })}
          </SelectionGrid>
        )}

        {touched.agentTargetId && !draft.agentTargetId && (
          <p className="text-micro text-red-600">Select an agent to continue.</p>
        )}
      </section>

      <FormField
        label="Version"
        htmlFor="simulation-revision"
        required
        error={
          touched.targetRevisionId && !draft.targetRevisionId
            ? "Select a revision for the first run."
            : undefined
        }
        hint={
          selectedAgent && !revisionsLoading && revisions.length === 0
            ? "This agent has no imported revisions yet. Import one from the agent's page."
            : undefined
        }
      >
        <Select
          value={draft.targetRevisionId || undefined}
          onValueChange={(value) => {
            update({ targetRevisionId: value });
            touch("targetRevisionId");
          }}
          disabled={!draft.agentTargetId || revisions.length === 0}
        >
          <SelectTrigger id="simulation-revision" className="w-full max-w-md">
            <SelectValue
              placeholder={
                !draft.agentTargetId
                  ? "Select an agent first"
                  : revisionsLoading
                    ? "Loading revisions…"
                    : "Select a revision"
              }
            />
          </SelectTrigger>
          <SelectContent>
            {revisions.map((revision) => (
              <SelectItem key={revision.id} value={revision.id}>
                rev {revision.revision_no} ·{" "}
                {revision.provider_revision_id ?? revision.source_kind}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </FormField>

      <FormField
        label="What do you want to test?"
        htmlFor="simulation-description"
        required
        error={
          touched.description && !draft.description.trim()
            ? "Describe what Resona should evaluate."
            : undefined
        }
        hint="Describe the behavior, scenarios, or requirements you want Resona to evaluate."
      >
        <Textarea
          id="simulation-description"
          value={draft.description}
          onChange={(event) => update({ description: event.target.value })}
          onBlur={() => touch("description")}
          placeholder="Describe the behavior, scenarios, or requirements you want Resona to evaluate..."
          rows={8}
          className="max-h-72 resize-none overflow-y-auto"
        />
      </FormField>
    </div>
  );
}
