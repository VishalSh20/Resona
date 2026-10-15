import { UserRound } from "lucide-react";

import { SelectableCard } from "@/components/forms/SelectableCard";
import { SelectionGrid } from "@/components/forms/SelectionGrid";
import { PERSONALITY_OPTIONS } from "@/lib/constants/personalities";

interface PersonaSelectionStepProps {
  personas: string[];
  onToggle: (key: string) => void;
}

export function PersonaSelectionStep({
  personas,
  onToggle,
}: PersonaSelectionStepProps) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-title-sm font-medium">Personas</h2>
        <p className="text-body-sm text-muted-foreground">
          The caller traits Resona will use to generate evaluators. Recommended
          personas are preselected — adjust them freely.
        </p>
      </div>

      <SelectionGrid minWidth="240px">
        {PERSONALITY_OPTIONS.map((persona) => (
          <SelectableCard
            key={persona.key}
            selected={personas.includes(persona.key)}
            onToggle={() => onToggle(persona.key)}
            leading={<UserRound className="size-4" aria-hidden />}
            title={persona.label}
            description={persona.description}
          />
        ))}
      </SelectionGrid>

      {personas.length === 0 && (
        <p className="text-micro text-red-600">Select at least one persona.</p>
      )}
    </div>
  );
}
