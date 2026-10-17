import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/status/StatusBadge";
import { useJudgeExecution } from "@/features/runs/queries";
import type { EvaluatorRunResultsDto, RunEvaluatorDto } from "@/types/api";
import { EvaluatorResultCard } from "./EvaluatorResultCard";

interface EvaluatorResultPanelProps {
  evaluator?: RunEvaluatorDto;
  block: EvaluatorRunResultsDto;
}

export function EvaluatorResultPanel({
  evaluator,
  block,
}: EvaluatorResultPanelProps) {
  const judgeExecutionId =
    block.metric_results.find((m) => m.judge_execution_id)?.judge_execution_id ??
    undefined;
  const judgeQuery = useJudgeExecution(judgeExecutionId);
  const judgeResult = judgeQuery.data?.parsed_output;

  const sequence = evaluator?.sequence_no ?? block.runs[0]?.repetition_no ?? "?";

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex items-center gap-3">
          <CardTitle className="text-title-sm">Evaluator #{sequence}</CardTitle>
          {evaluator && (
            <span className="text-body-sm text-muted-foreground">
              {evaluator.languages.major ?? "—"}
              {evaluator.languages.minor && ` / ${evaluator.languages.minor}`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {block.runs.map((run) => (
            <StatusBadge key={run.id} status={run.status} />
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {block.runs.length === 0 ? (
          <p className="text-body-sm text-muted-foreground">No call runs yet.</p>
        ) : (
          block.runs.map((callRun) => (
            <EvaluatorResultCard
              key={callRun.id}
              callRun={callRun}
              judgeResult={judgeResult}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
