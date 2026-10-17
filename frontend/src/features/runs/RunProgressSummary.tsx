import { Card, CardContent } from "@/components/ui/card";
import { ProgressBar } from "@/components/data/ProgressBar";
import { ScoreRing } from "@/features/runs/results/ScoreRing";
import { formatPercent } from "@/lib/formatters/format";
import type { CallRunDto, CompositeDto, RunDto } from "@/types/api";

interface RunProgressSummaryProps {
  run: RunDto;
  callRuns: CallRunDto[];
  composite?: CompositeDto | null;
}

export function RunProgressSummary({
  run,
  callRuns,
  composite,
}: RunProgressSummaryProps) {
  const total = run.evaluator_count;
  const completed = callRuns.filter((c) => c.status === "completed").length;
  const running = callRuns.filter((c) => c.status === "running").length;
  const failed = callRuns.filter(
    (c) => c.status === "infrastructure_failed" || c.status === "cancelled"
  ).length;

  return (
    <Card>
      <CardContent className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2">
          <h3 className="text-label uppercase tracking-wide text-muted-foreground">
            Progress
          </h3>
          <ProgressBar
            total={total}
            completed={completed}
            running={running}
            failed={failed}
          />
        </div>

        <div className="flex items-center gap-4">
          <ScoreRing
            score={composite?.score_0_100 ?? null}
            size={72}
            stroke={6}
          />
          <div>
            <p className="text-label uppercase tracking-wide text-muted-foreground">
              Composite
            </p>
            <p className="text-body-sm text-muted-foreground">
              {composite?.score_0_100 != null
                ? `Score out of 100`
                : "No score yet"}
            </p>
          </div>
        </div>

        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Coverage
          </p>
          <p className="text-title-sm font-semibold">
            {formatPercent(composite?.coverage_ratio)}
          </p>
        </div>

        <div className="space-y-1">
          <p className="text-label uppercase tracking-wide text-muted-foreground">
            Run status
          </p>
          <p className="text-title-sm font-semibold capitalize">{run.status}</p>
        </div>
      </CardContent>
    </Card>
  );
}
