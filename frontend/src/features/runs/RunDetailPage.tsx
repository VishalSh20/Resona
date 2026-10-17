import { useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { Play } from "lucide-react";

import { ChipGroup } from "@/components/forms/ChipGroup";
import { FormField } from "@/components/forms/FormField";
import { PageHeader } from "@/components/domain/PageHeader";
import { ErrorState, LoadingState } from "@/components/domain/States";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useSimulation, useSimulationRuns } from "@/features/simulations/queries";
import {
  useMarkRunReady,
  useRun,
  useRunCallRuns,
  useRunEvaluators,
  useRunResults,
  useStartRun,
  useUpdateEvaluator,
} from "@/features/runs/queries";
import { useRunLive } from "@/features/runs/useRunLive";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import type { RunEvaluatorUpdateInput } from "@/lib/api/runs";
import { languageLabel } from "@/lib/constants/languages";
import { METRIC_OPTIONS } from "@/lib/constants/metrics";
import { PERSONALITY_OPTIONS } from "@/lib/constants/personalities";
import { formatDurationMs, formatTimestamp, truncateId } from "@/lib/formatters/format";
import type { RunEvaluatorDto } from "@/types/api";
import { RunProgressSummary } from "./RunProgressSummary";
import { EvaluatorsSection } from "./EvaluatorsSection";
import { ResultsSection } from "./results/ResultsSection";

export function RunDetailPage() {
  const { simulationId = "", runId } = useParams();
  useDocumentTitle("Run");
  const runQuery = useRun(runId);
  const simulation = useSimulation(runQuery.data?.simulation_id);
  const evaluatorsQuery = useRunEvaluators(runId);
  const callRunsQuery = useRunCallRuns(runId);
  const runStatus = runQuery.data?.status;
  const resultsQuery = useRunResults(
    runId,
    runStatus === "running" || runStatus === "queued" || runStatus === "partial",
  );
  const markReady = useMarkRunReady(runId ?? "");
  const updateEvaluator = useUpdateEvaluator(runId ?? "");
  const startRun = useStartRun(runId ?? "");
  const runsQuery = useSimulationRuns(runQuery.data?.simulation_id);

  const [editing, setEditing] = useState<RunEvaluatorDto | null>(null);

  const { connectionState } = useRunLive(runId);

  if (runQuery.isLoading) {
    return <LoadingState label="Loading run…" />;
  }
  if (runQuery.isError) {
    return (
      <ErrorState
        error={runQuery.error}
        title="Could not load run."
        onRetry={() => void runQuery.refetch()}
      />
    );
  }

  const run = runQuery.data!;
  const evaluators = evaluatorsQuery.data ?? [];
  const runs = runsQuery.data ?? [];
  const callRuns = callRunsQuery.data ?? [];
  const results = resultsQuery.data;
  const isFirstRun = runs.length > 0 && runs[0].id === run.id;
  const editable = run.status === "draft" || run.status === "ready";
  const liveVisible =
    connectionState === "connected" ||
    connectionState === "connecting" ||
    connectionState === "reconnecting";

  const runDuration =
    run.started_at && run.finished_at
      ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={truncateId(run.id, 8, 4)}
        description={
          <Link
            to={`/app/simulations/${simulationId}`}
            className="hover:text-foreground"
          >
            Back to simulation
          </Link>
        }
        meta={
          <div className="flex items-center gap-2">
            <StatusBadge status={run.status} />
            {liveVisible && (
              <span className="text-label text-muted-foreground">
                {connectionState === "connected" ? "● Live" : "↻ Reconnecting"}
              </span>
            )}
          </div>
        }
        actions={
          run.status === "draft" ? (
            <Button
              disabled={evaluators.length === 0 || markReady.isPending}
              onClick={() => void markReady.mutate()}
            >
              {markReady.isPending ? "Marking ready…" : "Mark ready"}
            </Button>
          ) : run.status === "ready" ? (
            <Button
              disabled={startRun.isPending}
              onClick={() => void startRun.mutate()}
            >
              <Play className="size-4" />
              {startRun.isPending ? "Starting…" : "Run"}
            </Button>
          ) : null
        }
      />

      {runQuery.data && (
        <Card className="gap-4 p-6">
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
            <Meta label="Agent revision" value={run.target_revision_id} mono />
            <Meta label="Evaluator count" value={run.evaluator_count.toString()} />
            <Meta
              label="Simulation"
              value={
                <Link
                  to={`/app/simulations/${simulationId}`}
                  className="font-mono hover:text-foreground"
                >
                  {truncateId(simulationId, 6, 3)}
                </Link>
              }
            />
            <Meta label="Duration" value={formatDurationMs(runDuration)} />
            <Meta label="Started" value={formatTimestamp(run.started_at)} />
            <Meta label="Finished" value={formatTimestamp(run.finished_at)} />
          </dl>
        </Card>
      )}

      {markReady.isError && (
        <ErrorState error={markReady.error} title="Could not mark ready." />
      )}
      {startRun.isError && (
        <ErrorState error={startRun.error} title="Could not start run." />
      )}

      <RunProgressSummary
        run={run}
        callRuns={callRuns}
        composite={results?.composite}
      />

      <EvaluatorsSection
        evaluators={evaluators}
        callRuns={callRuns}
        metrics={results?.evaluators.flatMap((e) => e.metric_results) ?? []}
        editable={editable}
        onEdit={setEditing}
      />

      {results && results.evaluators.some((e) => e.metric_results.length > 0) && (
        <ResultsSection results={results} evaluators={evaluators} />
      )}

      {resultsQuery.isError && (
        <ErrorState
          error={resultsQuery.error}
          title="Could not load results."
          onRetry={() => void resultsQuery.refetch()}
        />
      )}

      {editing && simulation.data && (
        <EvaluatorEditorDialog
          evaluator={editing}
          isFirstRun={isFirstRun}
          allowed={{
            languages: simulation.data.languages,
            metrics: simulation.data.metric_set,
            personalities: simulation.data.personalities,
          }}
          isPending={updateEvaluator.isPending}
          error={updateEvaluator.error}
          onClose={() => setEditing(null)}
          onSubmit={(input) =>
            updateEvaluator.mutateAsync({ evaluatorId: editing.id, input })
          }
        />
      )}
    </div>
  );
}

function Meta({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-label uppercase tracking-wide text-muted-foreground">
        {label}
      </dt>
      <dd className={`mt-0.5 text-body-sm ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

interface EvaluatorEditorDialogProps {
  evaluator: RunEvaluatorDto;
  isFirstRun: boolean;
  allowed: {
    languages: string[];
    metrics: string[];
    personalities: string[];
  };
  isPending: boolean;
  error: Error | null;
  onClose: () => void;
  onSubmit: (input: RunEvaluatorUpdateInput) => Promise<unknown>;
}

function EvaluatorEditorDialog({
  evaluator,
  isFirstRun,
  allowed,
  isPending,
  error,
  onClose,
  onSubmit,
}: EvaluatorEditorDialogProps) {
  const [scenario, setScenario] = useState(evaluator.scenario);
  const [expectedOutputPrompt, setExpectedOutputPrompt] = useState(
    evaluator.expected_output_prompt,
  );
  const [metrics, setMetrics] = useState<string[]>(evaluator.metrics);
  const [personality, setPersonality] = useState<string[]>(evaluator.personality);
  const [major, setMajor] = useState(evaluator.languages.major ?? "");
  const [minor, setMinor] = useState(evaluator.languages.minor ?? "");

  const metricOptions = METRIC_OPTIONS.filter((m) =>
    allowed.metrics.includes(m.key),
  );
  const personalityOptions = PERSONALITY_OPTIONS.filter((p) =>
    allowed.personalities.includes(p.key),
  );

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Evaluator #{evaluator.sequence_no}</DialogTitle>
          <DialogDescription>
            {isFirstRun
              ? "Edit the concrete caller scenario and what the judge should inspect."
              : "Only personality can be changed on this run."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {isFirstRun && (
            <>
              <FormField label="Scenario" htmlFor="scenario">
                <Textarea
                  id="scenario"
                  value={scenario}
                  onChange={(event) => setScenario(event.target.value)}
                  rows={8}
                />
              </FormField>
              <FormField label="Expected output prompt" htmlFor="expected">
                <Textarea
                  id="expected"
                  value={expectedOutputPrompt}
                  onChange={(event) => setExpectedOutputPrompt(event.target.value)}
                  rows={6}
                />
              </FormField>

              <FormField label="Languages">
                <div className="flex gap-2">
                  <Select value={major || undefined} onValueChange={setMajor}>
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="Major" />
                    </SelectTrigger>
                    <SelectContent>
                      {allowed.languages.map((lang) => (
                        <SelectItem key={lang} value={lang}>
                          {languageLabel(lang)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Select value={minor || undefined} onValueChange={setMinor}>
                    <SelectTrigger className="w-40">
                      <SelectValue placeholder="Minor (optional)" />
                    </SelectTrigger>
                    <SelectContent>
                      {allowed.languages.map((lang) => (
                        <SelectItem key={lang} value={lang}>
                          {languageLabel(lang)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </FormField>

              <FormField label="Metrics">
                <ChipGroup
                  options={metricOptions}
                  value={metrics}
                  onChange={setMetrics}
                />
              </FormField>
            </>
          )}

          <FormField label="Personality">
            <ChipGroup
              options={personalityOptions}
              value={personality}
              onChange={setPersonality}
            />
          </FormField>

          {error && <ErrorState error={error} title="Could not save evaluator." />}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            disabled={isPending}
            onClick={async () => {
              await onSubmit(
                isFirstRun
                  ? {
                      scenario,
                      expected_output_prompt: expectedOutputPrompt,
                      metrics,
                      languages: { major: major || null, minor: minor || null },
                      personality,
                    }
                  : { personality },
              );
              onClose();
            }}
          >
            {isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
