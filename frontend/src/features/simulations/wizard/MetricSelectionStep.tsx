import { Gauge } from "lucide-react";

import { SelectableCard } from "@/components/forms/SelectableCard";
import { SelectionGrid } from "@/components/forms/SelectionGrid";
import {
  METRIC_OPTIONS,
  type MetricOption,
} from "@/lib/constants/metrics";

interface MetricSelectionStepProps {
  metrics: string[];
  onToggle: (key: string) => void;
}

function groupByFamily(options: MetricOption[]) {
  const groups = new Map<string, MetricOption[]>();
  for (const option of options) {
    const family = groups.get(option.family) ?? [];
    family.push(option);
    groups.set(option.family, family);
  }
  return [...groups.entries()];
}

export function MetricSelectionStep({
  metrics,
  onToggle,
}: MetricSelectionStepProps) {
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-title-sm font-medium">Metrics</h2>
        <p className="text-body-sm text-muted-foreground">
          What this simulation should measure. Recommended metrics are
          preselected — adjust them freely.
        </p>
      </div>

      {groupByFamily(METRIC_OPTIONS).map(([family, options]) => (
        <section key={family} className="space-y-2">
          <h3 className="text-label uppercase tracking-wide text-muted-foreground">
            {family}
          </h3>
          <SelectionGrid minWidth="260px">
            {options.map((metric) => (
              <SelectableCard
                key={metric.key}
                selected={metrics.includes(metric.key)}
                onToggle={() => onToggle(metric.key)}
                leading={<Gauge className="size-4" aria-hidden />}
                title={metric.label}
                description={metric.description}
              />
            ))}
          </SelectionGrid>
        </section>
      ))}

      {metrics.length === 0 && (
        <p className="text-micro text-red-600">Select at least one metric.</p>
      )}
    </div>
  );
}
