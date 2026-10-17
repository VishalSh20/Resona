import { MetricsOverview } from "./MetricsOverview";
import { EvaluatorResultPanel } from "./EvaluatorResultPanel";
import type { RunEvaluatorDto, RunResultsReadDto } from "@/types/api";

interface ResultsSectionProps {
  results: RunResultsReadDto;
  evaluators: RunEvaluatorDto[];
}

export function ResultsSection({ results, evaluators }: ResultsSectionProps) {
  const evaluatorById = new Map(evaluators.map((e) => [e.id, e]));
  const blocksWithResults = results.evaluators.filter(
    (block) => block.metric_results.length > 0 || block.runs.length > 0
  );

  return (
    <section className="space-y-6">
      <h2 className="text-title-sm font-medium">Results</h2>
      <MetricsOverview results={results} />
      {blocksWithResults.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-body-sm font-medium uppercase tracking-wide text-muted-foreground">
            Evaluator results
          </h3>
          {blocksWithResults.map((block) => (
            <EvaluatorResultPanel
              key={block.run_evaluator_id}
              evaluator={evaluatorById.get(block.run_evaluator_id)}
              block={block}
            />
          ))}
        </div>
      )}
    </section>
  );
}
