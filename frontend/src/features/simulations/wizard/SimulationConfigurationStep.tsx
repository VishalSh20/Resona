import {
  Building2,
  Car,
  Headphones,
  Languages,
  Music,
  Users,
  Volume2,
  VolumeX,
  type LucideIcon,
} from "lucide-react";

import { FormField } from "@/components/forms/FormField";
import { NumberInput } from "@/components/forms/NumberInput";
import { SelectableCard } from "@/components/forms/SelectableCard";
import { SelectionGrid } from "@/components/forms/SelectionGrid";
import { CALL_AMBIENCE_OPTIONS } from "@/lib/constants/ambience";
import { LANGUAGE_OPTIONS } from "@/lib/constants/languages";
import {
  isEvaluatorCountValid,
  type SimulationDraft,
} from "@/features/simulations/wizard/types";

const AMBIENCE_ICONS: Record<string, LucideIcon> = {
  QUIET: VolumeX,
  NOISY: Volume2,
  PEOPLE_TALKING: Users,
  MUSIC: Music,
  TRAFFIC: Car,
  OFFICE: Building2,
  CALL_CENTRE: Headphones,
  CAR: Car,
};

interface SimulationConfigurationStepProps {
  draft: SimulationDraft;
  update: (patch: Partial<SimulationDraft>) => void;
  toggleIn: (field: "languages" | "callAmbience", key: string) => void;
  touched: Record<string, boolean>;
  touch: (field: string) => void;
}

export function SimulationConfigurationStep({
  draft,
  update,
  toggleIn,
  touched,
  touch,
}: SimulationConfigurationStepProps) {
  const countInvalid = !isEvaluatorCountValid(draft.evaluatorCount);

  return (
    <div className="space-y-6">
      <FormField
        label="Evaluator count"
        htmlFor="evaluator-count"
        required
        error={
          touched.evaluatorCount && countInvalid
            ? "Enter a whole number between 1 and 100."
            : undefined
        }
        hint="How many concrete evaluators the first run should generate (1–100)."
      >
        <NumberInput
          id="evaluator-count"
          min={1}
          max={100}
          value={draft.evaluatorCount}
          onChange={(value) => update({ evaluatorCount: value })}
          className="w-32"
        />
      </FormField>

      <section className="space-y-3">
        <div>
          <h2 className="text-title-sm font-medium">Languages</h2>
          <p className="text-body-sm text-muted-foreground">
            Which caller languages should the simulation cover?
          </p>
        </div>
        <SelectionGrid minWidth="150px">
          {LANGUAGE_OPTIONS.map((language) => {
            const code = language.key.length <= 2 ? language.key.toUpperCase() : null;
            return (
              <SelectableCard
                key={language.key}
                selected={draft.languages.includes(language.key)}
                onToggle={() => {
                  toggleIn("languages", language.key);
                  touch("languages");
                }}
                leading={
                  code ? (
                    <span className="font-mono text-micro font-medium tracking-wide">
                      {code}
                    </span>
                  ) : (
                    <Languages className="size-4" aria-hidden />
                  )
                }
                title={language.label}
              />
            );
          })}
        </SelectionGrid>
        {touched.languages && draft.languages.length === 0 && (
          <p className="text-micro text-red-600">Select at least one language.</p>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-title-sm font-medium">Call ambience</h2>
          <p className="text-body-sm text-muted-foreground">
            Background conditions to mix into the caller's line. Optional.
          </p>
        </div>
        <SelectionGrid minWidth="170px">
          {CALL_AMBIENCE_OPTIONS.map((ambience) => {
            const Icon = AMBIENCE_ICONS[ambience.key] ?? Volume2;
            return (
              <SelectableCard
                key={ambience.key}
                selected={draft.callAmbience.includes(ambience.key)}
                onToggle={() => toggleIn("callAmbience", ambience.key)}
                leading={<Icon className="size-4" aria-hidden />}
                title={ambience.label}
              />
            );
          })}
        </SelectionGrid>
      </section>
    </div>
  );
}
