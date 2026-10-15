import { callAmbienceLabel } from "@/lib/constants/ambience";
import { languageLabel } from "@/lib/constants/languages";
import { metricLabel } from "@/lib/constants/metrics";
import { personalityLabel } from "@/lib/constants/personalities";
import type { SimulationDraft } from "@/features/simulations/wizard/types";

interface SimulationReviewStepProps {
  draft: SimulationDraft;
  agentLabel: string;
  revisionLabel: string;
}

export function SimulationReviewStep({
  draft,
  agentLabel,
  revisionLabel,
}: SimulationReviewStepProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-title-sm font-medium">Review</h2>
        <p className="text-body-sm text-muted-foreground">
          Confirm the configuration before Resona creates the simulation, its
          first run, and generates the run's evaluators.
        </p>
      </div>

      <dl className="text-body-sm">
        <ReviewRow label="Name" value={draft.name} />
        <ReviewRow label="Agent" value={agentLabel} />
        <ReviewRow label="Version" value={revisionLabel} />
        <ReviewRow label="What to test" value={draft.description} />
        <ReviewRow
          label="Evaluator count"
          value={draft.evaluatorCount?.toString() ?? "—"}
        />
        <ReviewRow
          label="Languages"
          value={draft.languages.map(languageLabel).join(", ") || "—"}
        />
        <ReviewRow
          label="Call ambience"
          value={draft.callAmbience.map(callAmbienceLabel).join(", ") || "—"}
        />
        <ReviewRow
          label="Personas"
          value={draft.personalities.map(personalityLabel).join(", ") || "—"}
        />
        <ReviewRow
          label="Metrics"
          value={draft.metrics.map(metricLabel).join(", ") || "—"}
        />
      </dl>
    </div>
  );
}

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-6 border-b border-border py-2 last:border-b-0">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-right font-medium">{value}</dd>
    </div>
  );
}
