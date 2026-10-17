import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreRing } from "./ScoreRing";
import { BarChart } from "./BarChart";
import { DonutChart } from "./DonutChart";
import { formatPercent } from "@/lib/formatters/format";
import type { EvaluatorRunResultsDto, RunResultsReadDto } from "@/types/api";

interface MetricsOverviewProps {
  results: RunResultsReadDto;
}

const STATUS_COLORS: Record<string, string> = {
  ok: "#22c55e",
  not_applicable: "#94a3b8",
  not_measurable: "#f59e0b",
  insufficient_evidence: "#f59e0b",
  invalid: "#ef4444",
  error: "#ef4444",
};

export function MetricsOverview({ results }: MetricsOverviewProps) {
  const composite = results.composite;
  const allMetricResults = results.evaluators.flatMap((e) => e.metric_results);

  const categoryData = Object.entries(composite?.category_scores ?? {})
    .filter((entry): entry is [string, number] => entry[1] != null)
    .map(([category, value]) => ({
      label: category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      value,
      color: "#3b82f6",
    }));

  const statusCounts = allMetricResults.reduce<Record<string, number>>(
    (acc, metric) => {
      acc[metric.status] = (acc[metric.status] ?? 0) + 1;
      return acc;
    },
    {}
  );

  const donutData = Object.entries(statusCounts).map(([status, value]) => ({
    label: status.replace(/_/g, " "),
    value,
    color: STATUS_COLORS[status] ?? "#94a3b8",
  }));

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-body-sm font-medium">Composite score</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center justify-center gap-3">
            <ScoreRing score={composite?.score_0_100 ?? null} size={120} stroke={10} />
            <div className="space-y-1 text-center">
              <p className="text-label uppercase tracking-wide text-muted-foreground">
                Coverage
              </p>
              <p className="text-title-sm font-semibold">
                {formatPercent(composite?.coverage_ratio)}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-body-sm font-medium">
              Category scores
            </CardTitle>
          </CardHeader>
          <CardContent>
            <BarChart data={categoryData} max={100} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-body-sm font-medium">
              Metric status distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DonutChart data={donutData} />
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-body-sm font-medium">
              Metric comparison
            </CardTitle>
          </CardHeader>
          <CardContent>
            <MetricComparisonTable evaluators={results.evaluators} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricComparisonTable({
  evaluators,
}: {
  evaluators: EvaluatorRunResultsDto[];
}) {
  const metricKeys = Array.from(
    new Set(
      evaluators.flatMap((e) => e.metric_results.map((m) => m.metric_key))
    )
  );

  if (metricKeys.length === 0) {
    return (
      <p className="text-body-sm text-muted-foreground">No metrics to compare.</p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-body-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 pr-4 text-left font-medium">Metric</th>
            {evaluators.map((e) => (
              <th key={e.run_evaluator_id} className="py-2 pr-4 text-right font-medium">
                #{e.runs[0]?.repetition_no ?? "—"}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metricKeys.map((key) => (
            <tr key={key} className="border-b last:border-b-0">
              <td className="py-2 pr-4 font-medium">{key}</td>
              {evaluators.map((e) => {
                const result = e.metric_results.find((m) => m.metric_key === key);
                return (
                  <td
                    key={`${e.run_evaluator_id}-${key}`}
                    className="py-2 pr-4 text-right tabular-nums"
                  >
                    {result?.status === "computed" &&
                    typeof result.value === "number"
                      ? result.value.toFixed(1)
                      : result?.status ?? "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
