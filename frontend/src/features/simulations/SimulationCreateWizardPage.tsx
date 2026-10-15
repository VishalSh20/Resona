import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { useAgentRevisions, useAgents, useProviders } from "@/features/agents/queries";
import {
  useCreateSimulation,
  useSimulationPreferences,
} from "@/features/simulations/queries";
import { PreferenceGenerationLoader } from "@/features/simulations/wizard/PreferenceGenerationLoader";
import { PersonaSelectionStep } from "@/features/simulations/wizard/PersonaSelectionStep";
import { MetricSelectionStep } from "@/features/simulations/wizard/MetricSelectionStep";
import { SimulationConfigurationStep } from "@/features/simulations/wizard/SimulationConfigurationStep";
import { SimulationFormShell } from "@/features/simulations/wizard/SimulationFormShell";
import { SimulationReviewStep } from "@/features/simulations/wizard/SimulationReviewStep";
import { SimulationTargetStep } from "@/features/simulations/wizard/SimulationTargetStep";
import {
  CONFIGURATION_STEP,
  EMPTY_DRAFT,
  METRIC_STEP,
  PERSONA_STEP,
  REVIEW_STEP,
  SIMULATION_STEPS,
  TARGET_STEP,
  isEvaluatorCountValid,
  type SimulationDraft,
} from "@/features/simulations/wizard/types";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { newIdempotencyKey } from "@/lib/api/idempotency";
import { runsApi } from "@/lib/api/runs";
import { METRIC_OPTIONS } from "@/lib/constants/metrics";
import { PERSONALITY_OPTIONS } from "@/lib/constants/personalities";
import type {
  SimulationCreatedDto,
  SimulationWorkflowSpecDto,
} from "@/types/api";

type ToggleField = "languages" | "callAmbience" | "personalities" | "metrics";

export function SimulationCreateWizardPage() {
  useDocumentTitle("New simulation");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const agentsQuery = useAgents();
  const providersQuery = useProviders();
  const createSimulation = useCreateSimulation();
  const preferences = useSimulationPreferences();

  const [draft, setDraft] = useState<SimulationDraft>(() => ({
    ...EMPTY_DRAFT,
    agentTargetId: searchParams.get("agent") ?? "",
    targetRevisionId: searchParams.get("revision") ?? "",
  }));
  const [step, setStep] = useState<number>(TARGET_STEP);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [created, setCreated] = useState<SimulationCreatedDto | null>(null);
  const [generatedFor, setGeneratedFor] = useState<string | null>(null);

  const revisionsQuery = useAgentRevisions(draft.agentTargetId || undefined);

  const providers = useMemo(
    () => new Map((providersQuery.data ?? []).map((p) => [p.id, p])),
    [providersQuery.data],
  );
  const agents = agentsQuery.data ?? [];
  const revisions = revisionsQuery.data ?? [];

  const generate = useMutation({
    mutationFn: ({
      runId,
      spec,
    }: {
      runId: string;
      simulationId: string;
      spec: SimulationWorkflowSpecDto;
    }) =>
      runsApi.generateEvaluators(
        runId,
        { workflow_spec: spec },
        newIdempotencyKey("run:generate-evaluators"),
      ),
    onSuccess: (_data, variables) =>
      navigate(
        `/app/simulations/${variables.simulationId}/runs/${variables.runId}`,
      ),
  });

  const update = (patch: Partial<SimulationDraft>) =>
    setDraft((current) => ({ ...current, ...patch }));

  const touch = (field: string) =>
    setTouched((current) => ({ ...current, [field]: true }));

  const toggleIn = (field: ToggleField, key: string) =>
    setDraft((current) => {
      const values = current[field];
      const next = values.includes(key)
        ? values.filter((item) => item !== key)
        : [...values, key];
      const updated: SimulationDraft = { ...current };
      updated[field] = next;
      return updated;
    });

  const isGeneratingPreferences =
    step === CONFIGURATION_STEP &&
    (preferences.isPending || preferences.isError);

  const canAdvance = (): boolean => {
    switch (step) {
      case TARGET_STEP:
        return Boolean(
          draft.name.trim() &&
            draft.description.trim() &&
            draft.agentTargetId &&
            draft.targetRevisionId,
        );
      case CONFIGURATION_STEP:
        return (
          isEvaluatorCountValid(draft.evaluatorCount) && draft.languages.length > 0
        );
      case PERSONA_STEP:
        return draft.personalities.length > 0;
      case METRIC_STEP:
        return draft.metrics.length > 0;
      case REVIEW_STEP:
        return draft.metrics.length > 0 && draft.personalities.length > 0;
      default:
        return false;
    }
  };

  const runPreferences = () => {
    preferences.mutate(
      {
        description: draft.description,
        available_metrics: METRIC_OPTIONS.map((m) => m.key),
        available_personalities: PERSONALITY_OPTIONS.map((p) => p.key),
      },
      {
        onSuccess: (result) => {
          setGeneratedFor(draft.description);
          update({
            metrics: result.metrics,
            personalities: result.personalities,
          });
          setStep(PERSONA_STEP);
        },
      },
    );
  };

  // The evaluators are designed from the simulation itself (its description and
  // configuration) by the generation endpoint; runs after the first inherit a
  // copy of the first run's evaluators.
  const requestEvaluators = (runId: string, simulationId: string) => {
    generate.mutate({
      runId,
      simulationId,
      spec: { objective: draft.description.trim() },
    });
  };

  const createAndAdvance = async () => {
    if (created) {
      requestEvaluators(created.run.id, created.simulation.id);
      return;
    }
    try {
      const result = await createSimulation.mutateAsync({
        input: {
          name: draft.name.trim(),
          description: draft.description.trim() || null,
          agent_target_id: draft.agentTargetId,
          target_revision_id: draft.targetRevisionId,
          languages: draft.languages,
          call_ambience: draft.callAmbience,
          metric_set: draft.metrics,
          personalities: draft.personalities,
          knowledge_base: {},
          evaluator_count: draft.evaluatorCount ?? 20,
        },
        idempotencyKey: newIdempotencyKey("simulation:create"),
      });
      setCreated(result);
      requestEvaluators(result.run.id, result.simulation.id);
    } catch {
      // Surfaced by createSimulation.isError below the actions.
    }
  };

  const handleBack = () => {
    if (step === TARGET_STEP) {
      navigate("/app/simulations");
      return;
    }
    if (step === CONFIGURATION_STEP && preferences.isError) {
      preferences.reset();
    }
    setStep(step - 1);
  };

  const handleContinue = () => {
    if (step === TARGET_STEP) {
      setTouched((current) => ({
        ...current,
        name: true,
        description: true,
        agentTargetId: true,
        targetRevisionId: true,
      }));
    }
    if (step === CONFIGURATION_STEP) {
      setTouched((current) => ({
        ...current,
        evaluatorCount: true,
        languages: true,
      }));
    }
    if (!canAdvance()) return;

    switch (step) {
      case CONFIGURATION_STEP:
        if (preferences.isSuccess && generatedFor === draft.description) {
          setStep(PERSONA_STEP);
        } else {
          runPreferences();
        }
        return;
      case REVIEW_STEP:
        void createAndAdvance();
        return;
      default:
        setStep(step + 1);
    }
  };

  const continueLabel = (): string => {
    if (step === METRIC_STEP) return "Review Simulation";
    if (step === REVIEW_STEP) {
      return created ? "Retry evaluator generation" : "Create simulation";
    }
    return "Continue";
  };

  const continuePending = createSimulation.isPending || generate.isPending;

  const selectedAgent = agents.find((a) => a.id === draft.agentTargetId);
  const selectedRevision = revisions.find((r) => r.id === draft.targetRevisionId);

  return (
    <SimulationFormShell
      title="New Simulation"
      description="Describe what you want to test so Resona can generate relevant evaluators."
      steps={SIMULATION_STEPS}
      current={step}
      nav={
        <>
          <Button
            type="button"
            variant="ghost"
            onClick={handleBack}
            disabled={generate.isPending}
          >
            <ArrowLeft className="size-4" />
            {step === TARGET_STEP ? "Cancel" : "Back"}
          </Button>

          {!isGeneratingPreferences && (
            <Button
              type="button"
              onClick={handleContinue}
              disabled={!canAdvance() || continuePending}
            >
              {continuePending ? "Working…" : continueLabel()}
              <ArrowRight className="size-4" />
            </Button>
          )}
        </>
      }
    >
      {isGeneratingPreferences ? (
        <PreferenceGenerationLoader
          status={preferences.isError ? "error" : "loading"}
          error={preferences.error}
          onRetry={runPreferences}
        />
      ) : generate.isPending ? (
        <LoadingState label="Generating evaluators…" />
      ) : (
        <div className="space-y-4">
          {step === TARGET_STEP && (
            <SimulationTargetStep
              draft={draft}
              update={update}
              agents={agents}
              providers={providers}
              revisions={revisions}
              revisionsLoading={revisionsQuery.isLoading}
              touched={touched}
              touch={touch}
            />
          )}

          {step === CONFIGURATION_STEP && (
            <SimulationConfigurationStep
              draft={draft}
              update={update}
              toggleIn={toggleIn}
              touched={touched}
              touch={touch}
            />
          )}

          {step === PERSONA_STEP && (
            <PersonaSelectionStep
              personas={draft.personalities}
              onToggle={(key) => toggleIn("personalities", key)}
            />
          )}

          {step === METRIC_STEP && (
            <MetricSelectionStep
              metrics={draft.metrics}
              onToggle={(key) => toggleIn("metrics", key)}
            />
          )}

          {step === REVIEW_STEP && (
            <SimulationReviewStep
              draft={draft}
              agentLabel={selectedAgent?.name ?? draft.agentTargetId}
              revisionLabel={
                selectedRevision
                  ? `rev ${selectedRevision.revision_no} · ${
                      selectedRevision.provider_revision_id ??
                      selectedRevision.source_kind
                    }`
                  : draft.targetRevisionId
              }
            />
          )}

          {step === REVIEW_STEP && createSimulation.isError && (
            <ErrorState
              error={createSimulation.error}
              title="Could not create the simulation."
            />
          )}

          {step === REVIEW_STEP && generate.isError && (
            <ErrorState
              error={generate.error}
              title="Could not generate evaluators."
              onRetry={() =>
                created && requestEvaluators(created.run.id, created.simulation.id)
              }
            />
          )}
        </div>
      )}
    </SimulationFormShell>
  );
}
