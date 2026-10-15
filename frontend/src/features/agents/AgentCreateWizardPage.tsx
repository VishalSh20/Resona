import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Bot, RefreshCw } from "lucide-react";

import { FormField } from "@/components/forms/FormField";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCreateAccount, useCreateAgent, useProviders } from "@/features/agents/queries";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { agentsApi } from "@/lib/api/agents";
import type {
  AgentPreviewResponseDto,
  CredentialFieldDto,
  IntegrationProviderDto,
} from "@/types/api";

const STEPS = ["Provider", "Connect", "Review"] as const;

const AGENT_ID_LABELS: Record<string, string> = {
  retell: "Agent ID",
  vapi: "Assistant ID",
  elevenlabs: "Agent ID",
  livekit: "Agent name (dispatch)",
  pipecat: "Agent name",
};

export function AgentCreateWizardPage() {
  useDocumentTitle("New agent");
  const navigate = useNavigate();
  const providersQuery = useProviders();
  const createAccount = useCreateAccount();
  const createAgent = useCreateAgent();

  const [step, setStep] = useState(0);
  const [provider, setProvider] = useState<IntegrationProviderDto | null>(null);
  const [agentId, setAgentId] = useState("");
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [config, setConfig] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<AgentPreviewResponseDto | null>(null);
  // Custom / generic WebSocket agent fields (slug === "custom").
  const [customName, setCustomName] = useState("");
  const [customUrl, setCustomUrl] = useState("");
  const [customProtocol, setCustomProtocol] = useState("custom");
  const [customAuth, setCustomAuth] = useState("");

  const isCustom = provider?.slug === "custom";

  const previewMutation = useMutation({
    mutationFn: () =>
      agentsApi.preview({
        provider_id: provider!.id,
        external_agent_id: agentId.trim(),
        config,
        secrets,
      }),
    onSuccess: (data) => {
      setPreview(data);
      setStep(2);
    },
  });

  const providers = providersQuery.data ?? [];

  function selectProvider(selected: IntegrationProviderDto) {
    setProvider(selected);
    setSecrets({});
    setConfig({});
    setAgentId("");
    setPreview(null);
    setCustomName("");
    setCustomUrl("");
    setCustomProtocol("custom");
    setCustomAuth("");
    setStep(1);
  }

  const canFetch = () =>
    isCustom ? false : Boolean(provider && agentId.trim() && hasRequiredFields(provider));

  const hasRequiredFields = (provider: IntegrationProviderDto) =>
    provider.credentials.every((field) => {
      if (field.secret) return secrets[field.key]?.trim();
      return config[field.key]?.trim();
    });

  // For a custom agent we have no provider API to preview; validation is that a
  // name and a websocket URL are present so the generic JSON bridge can be built.
  const canContinueCustom = () => Boolean(customName.trim() && customUrl.trim());

  async function onAdd() {
    if (!provider) return;

    if (isCustom) {
      const account = await createAccount.mutateAsync({
        provider_id: provider.id,
        name: customName.trim(),
        config: {},
        secrets: customAuth.trim() ? { authorization: customAuth.trim() } : {},
      });
      const result = await createAgent.mutateAsync({
        provider_id: provider.id,
        integration_account_id: account.id,
        name: customName.trim(),
        agent_url: customUrl.trim(),
      });
      // Attach the client-supplied websocket bridge (kind=websocket → bridge).
      await agentsApi.setConnection(result.target.id, {
        kind: "websocket",
        transport: "bridge",
        config: { url: customUrl.trim(), provider: customProtocol },
        secrets: customAuth.trim() ? { authorization: customAuth.trim() } : {},
      });
      navigate(`/app/agents/${result.target.id}/overview`);
      return;
    }

    if (!preview) return;
    const account = await createAccount.mutateAsync({
      provider_id: provider.id,
      name: `${preview.identity.name}`,
      config,
      secrets,
    });
    const result = await createAgent.mutateAsync({
      provider_id: provider.id,
      integration_account_id: account.id,
      external_agent_id: agentId.trim(),
    });
    navigate(`/app/agents/${result.target.id}/overview`);
  }

  if (providersQuery.isLoading) {
    return <LoadingState label="Loading providers…" />;
  }
  if (providersQuery.isError) {
    return (
      <ErrorState
        error={providersQuery.error}
        title="Could not load providers."
        onRetry={() => void providersQuery.refetch()}
      />
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="New agent"
        description="Connect a provider, fetch the agent's current configuration, then add it."
      />

      <div className="flex items-center gap-2">
        {STEPS.map((label, index) => (
          <div key={label} className="flex flex-1 items-center gap-2">
            <span
              className={
                index === step
                  ? "flex size-6 items-center justify-center rounded-full bg-foreground text-micro font-medium text-background"
                  : "flex size-6 items-center justify-center rounded-full border border-border text-micro text-muted-foreground"
              }
            >
              {index + 1}
            </span>
            <span
              className={
                index === step
                  ? "text-body-sm font-medium"
                  : "text-body-sm text-muted-foreground"
              }
            >
              {label}
            </span>
          </div>
        ))}
      </div>

      <Card className="p-6">
        {step === 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {providers.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => selectProvider(item)}
                className="flex flex-col gap-1 rounded-lg border border-border p-4 text-left transition-colors hover:border-foreground hover:bg-surface-hover"
              >
                <span className="flex items-center gap-2 font-medium">
                  <Bot className="size-4" />
                  {item.display_name}
                </span>
                <span className="text-micro text-muted-foreground">
                  {credentialSummary(item.credentials)}
                </span>
              </button>
            ))}
          </div>
        )}

        {step === 1 && provider && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-title-sm font-medium">{provider.display_name}</h2>
                <p className="text-body-sm text-muted-foreground">
                  {isCustom
                    ? "Provide the WebSocket endpoint this agent exposes."
                    : "Enter the credentials and agent identifier."}
                </p>
              </div>
            </div>

            {isCustom ? (
              <>
                <FormField label="Agent name" required>
                  <Input
                    value={customName}
                    onChange={(event) => setCustomName(event.target.value)}
                    placeholder="e.g. My generic agent"
                  />
                </FormField>

                <FormField
                  label="WebSocket URL"
                  required
                  hint="The wss:// endpoint your agent listens on."
                >
                  <Input
                    type="url"
                    value={customUrl}
                    onChange={(event) => setCustomUrl(event.target.value)}
                    placeholder="wss://my-agent.example.com/ws"
                  />
                </FormField>

                <FormField label="Protocol" hint="Encoding used on the socket.">
                  <Select
                    value={customProtocol}
                    onValueChange={setCustomProtocol}
                  >
                    <SelectTrigger className="w-full max-w-md">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {["custom", "vapi", "retell", "pipecat", "elevenlabs"].map(
                        (protocol) => (
                          <SelectItem key={protocol} value={protocol}>
                            {protocol}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                </FormField>

                <FormField
                  label="Authorization header (optional)"
                  hint="Sent as an Authorization header on connection."
                >
                  <Input
                    type="password"
                    value={customAuth}
                    onChange={(event) => setCustomAuth(event.target.value)}
                    placeholder="Bearer …"
                  />
                </FormField>
              </>
            ) : (
              <>
                {provider.credentials.map((field) =>
                  field.secret ? (
                    <FormField
                      key={field.key}
                      label={field.label}
                      required={field.required}
                    >
                      <Input
                        type="password"
                        value={secrets[field.key] ?? ""}
                        onChange={(event) =>
                          setSecrets((prev) => ({
                            ...prev,
                            [field.key]: event.target.value,
                          }))
                        }
                        placeholder={field.label}
                      />
                    </FormField>
                  ) : (
                    <FormField
                      key={field.key}
                      label={field.label}
                      required={field.required}
                    >
                      <Input
                        value={config[field.key] ?? ""}
                        onChange={(event) =>
                          setConfig((prev) => ({
                            ...prev,
                            [field.key]: event.target.value,
                          }))
                        }
                        placeholder={field.label}
                      />
                    </FormField>
                  ),
                )}

                <FormField
                  label={AGENT_ID_LABELS[provider.slug] ?? "Agent identifier"}
                  required
                >
                  <Input
                    value={agentId}
                    onChange={(event) => setAgentId(event.target.value)}
                    placeholder={AGENT_ID_LABELS[provider.slug] ?? "agent id"}
                  />
                </FormField>
              </>
            )}

            {previewMutation.isError && (
              <ErrorState
                error={previewMutation.error}
                title="Could not fetch agent details."
              />
            )}
          </div>
        )}

        {step === 2 && preview && provider && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-title-sm font-medium">{preview.identity.name}</h2>
              <span className="text-micro text-muted-foreground">
                {preview.revision.provider_revision_id ?? "latest"}
              </span>
            </div>

            <dl className="space-y-2 text-body-sm">
              <PreviewRow label="Agent ID" value={preview.identity.external_agent_id} />
              <PreviewRow
                label="Revision type"
                value={preview.revision.provider_revision_type ?? "—"}
              />
              <PreviewRow label="Description" value={preview.revision.description ?? "—"} />
              <PreviewRow
                label="First message"
                value={preview.revision.first_message ?? "—"}
              />
            </dl>

            <details className="text-micro text-muted-foreground">
              <summary className="cursor-pointer">Canonical config</summary>
              <pre className="mt-2 overflow-auto rounded-md border border-border p-2 font-mono">
                {JSON.stringify(preview.revision.canonical_config, null, 2)}
              </pre>
            </details>

            {(createAccount.isError || createAgent.isError) && (
              <ErrorState
                error={createAgent.error ?? createAccount.error}
                title="Could not add the agent."
              />
            )}
          </div>
        )}

        {step === 2 && isCustom && provider && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-title-sm font-medium">{customName.trim()}</h2>
              <span className="text-micro text-muted-foreground">
                Custom / WebSocket
              </span>
            </div>

            <dl className="space-y-2 text-body-sm">
              <PreviewRow label="Name" value={customName.trim()} />
              <PreviewRow label="WebSocket URL" value={customUrl.trim()} />
              <PreviewRow label="Protocol" value={customProtocol} />
            </dl>

            {(createAccount.isError || createAgent.isError) && (
              <ErrorState
                error={createAgent.error ?? createAccount.error}
                title="Could not add the agent."
              />
            )}
          </div>
        )}

        <div className="flex items-center justify-between pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              if (step === 0) navigate("/app/agents");
              else if (step === 1) setStep(0);
              else setStep(1);
            }}
          >
            {step === 0 ? "Cancel" : "Back"}
          </Button>

          {step === 0 ? (
            <span className="text-micro text-muted-foreground">
              Choose a provider to continue
            </span>
          ) : step === 1 ? (
            isCustom ? (
              <Button
                type="button"
                disabled={!canContinueCustom()}
                onClick={() => setStep(2)}
              >
                <ArrowRight className="size-4" />
                Review agent
              </Button>
            ) : (
              <Button
                type="button"
                disabled={!canFetch() || previewMutation.isPending}
                onClick={() => void previewMutation.mutate()}
              >
                {previewMutation.isPending ? (
                  <RefreshCw className="size-4 animate-spin" />
                ) : (
                  <ArrowRight className="size-4" />
                )}
                Fetch details
              </Button>
            )
          ) : (
            <Button
              type="button"
              disabled={createAccount.isPending || createAgent.isPending}
              onClick={() => void onAdd()}
            >
              {createAgent.isPending ? "Adding…" : "Add agent"}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

function credentialSummary(fields: CredentialFieldDto[]): string {
  const secrets = fields.filter((f) => f.secret).map((f) => f.label);
  const config = fields.filter((f) => !f.secret).map((f) => f.label);
  const parts = [...secrets, ...config];
  return parts.length > 0 ? parts.join(" · ") : "No credentials required";
}

function PreviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border py-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="max-w-[70%] text-right font-medium">{value}</dd>
    </div>
  );
}
