import { useState } from "react";

import { EvaluatorCard } from "./EvaluatorCard";
import type { CallRunDto, MetricResultDto, RunEvaluatorDto } from "@/types/api";

interface EvaluatorsSectionProps {
  evaluators: RunEvaluatorDto[];
  callRuns: CallRunDto[];
  metrics: MetricResultDto[];
  editable?: boolean;
  onEdit?: (evaluator: RunEvaluatorDto) => void;
}

export function EvaluatorsSection({
  evaluators,
  callRuns,
  metrics,
  editable = false,
  onEdit,
}: EvaluatorsSectionProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  const callRunsByEvaluator = callRuns.reduce<Record<string, CallRunDto[]>>(
    (acc, run) => {
      acc[run.run_evaluator_id] = acc[run.run_evaluator_id] ?? [];
      acc[run.run_evaluator_id].push(run);
      return acc;
    },
    {}
  );

  const metricsByEvaluator = metrics.reduce<Record<string, MetricResultDto[]>>(
    (acc, metric) => {
      acc[metric.call_run_id] = acc[metric.call_run_id] ?? [];
      acc[metric.call_run_id].push(metric);
      return acc;
    },
    {}
  );

  return (
    <section className="space-y-3">
      <h2 className="text-title-sm font-medium">Evaluators</h2>
      <div className="space-y-3">
        {evaluators.map((evaluator) => {
          const runs = callRunsByEvaluator[evaluator.id] ?? [];
          const metricResults = runs.flatMap(
            (run) => metricsByEvaluator[run.id] ?? []
          );
          const judgeExecutionId = metricResults.find((m) => m.judge_execution_id)
            ?.judge_execution_id;
          return (
            <EvaluatorCard
              key={evaluator.id}
              evaluator={evaluator}
              callRuns={runs}
              metrics={metricResults}
              judgeExecutionId={judgeExecutionId}
              editable={editable}
              onEdit={onEdit}
              isOpen={openId === evaluator.id}
              onToggle={() =>
                setOpenId((prev) => (prev === evaluator.id ? null : evaluator.id))
              }
            />
          );
        })}
      </div>
    </section>
  );
}
