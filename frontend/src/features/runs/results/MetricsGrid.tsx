import { MetricResultCard } from "./MetricResultCard";
import type { JudgeMetricDto } from "@/types/api";

interface MetricsGridProps {
  metrics: JudgeMetricDto[];
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  if (metrics.length === 0) {
    return (
      <p className="text-body-sm text-muted-foreground">No metric results yet.</p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {metrics.map((metric) => (
        <MetricResultCard key={metric.metric_key} metric={metric} />
      ))}
    </div>
  );
}
