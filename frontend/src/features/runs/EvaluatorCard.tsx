import { ChevronDown, FileText, Languages, Pencil, User } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { formatDurationMs } from "@/lib/formatters/format";
import type {
  CallRunDto,
  JudgeMetricDto,
  MetricResultDto,
  RunEvaluatorDto,
} from "@/types/api";
import { useJudgeExecution } from "./queries";

interface EvaluatorCardProps {
  evaluator: RunEvaluatorDto;
  callRuns: CallRunDto[];
  metrics: MetricResultDto[];
  judgeExecutionId?: string | null;
  editable?: boolean;
  onEdit?: (evaluator: RunEvaluatorDto) => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function EvaluatorCard({
  evaluator,
  callRuns,
  metrics,
  judgeExecutionId,
  editable = false,
  onEdit,
  isOpen,
  onToggle,
}: EvaluatorCardProps) {
  const judgeQuery = useJudgeExecution(judgeExecutionId ?? undefined);
  const judgeResult = judgeQuery.data?.parsed_output;

  const dominantStatus = deriveDominantStatus(callRuns);
  const totalDuration = callRuns.reduce(
    (sum, run) => sum + (run.duration_ms ?? 0),
    0
  );

  const score = judgeResult
    ? averageScore(judgeResult.metrics)
    : averageMetricScore(metrics);

  return (
    <Card className="gap-0 overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between gap-4 p-4 text-left hover:bg-muted/40 transition-colors"
      >
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-6 gap-y-2">
          <div className="flex items-center gap-3">
            <span className="text-title-sm font-semibold">
              #{evaluator.sequence_no}
            </span>
            <StatusBadge status={dominantStatus} />
          </div>

          <div className="flex items-center gap-2 text-body-sm text-muted-foreground">
            <Languages className="size-3.5" />
            {evaluator.languages.major ?? "—"}
            {evaluator.languages.minor && ` / ${evaluator.languages.minor}`}
          </div>

          <div className="flex items-center gap-2 text-body-sm text-muted-foreground">
            <User className="size-3.5" />
            {evaluator.personality.slice(0, 2).join(", ") || "—"}
            {evaluator.personality.length > 2 &&
              ` +${evaluator.personality.length - 2}`}
          </div>

          <Badge variant="secondary" className="text-body-sm">
            {evaluator.metrics.length} metrics
          </Badge>

          {totalDuration > 0 && (
            <span className="text-body-sm tabular-nums text-muted-foreground">
              {formatDurationMs(totalDuration)}
            </span>
          )}

          {score != null && (
            <span
              className={cn(
                "text-body-sm font-semibold tabular-nums",
                score >= 4 ? "text-green-600" : score >= 3 ? "text-amber-600" : "text-red-600"
              )}
            >
              Avg {score.toFixed(1)}
            </span>
          )}
        </div>
        <ChevronDown
          className={cn(
            "size-5 shrink-0 text-muted-foreground transition-transform",
            isOpen && "rotate-180"
          )}
        />
      </button>

      {isOpen && (
        <CardContent className="border-t bg-muted/20 p-4">
          <Tabs defaultValue="details">
            <TabsList>
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="calls">Calls ({callRuns.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="details" className="mt-4 space-y-4">
              {editable && onEdit && (
                <div className="flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(evaluator)}
                  >
                    <Pencil className="size-3.5" />
                    Edit evaluator
                  </Button>
                </div>
              )}
              <ReadOnlyField
                icon={<FileText className="size-4" />}
                label="Scenario"
                value={evaluator.scenario}
              />
              <ReadOnlyField
                icon={<FileText className="size-4" />}
                label="Expected output prompt"
                value={evaluator.expected_output_prompt}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <ReadOnlyField
                  label="Personality"
                  value={evaluator.personality.join(", ") || "—"}
                />
                <ReadOnlyField
                  label="Metrics"
                  value={evaluator.metrics.join(", ") || "—"}
                />
              </div>
            </TabsContent>
            <TabsContent value="calls" className="mt-4">
              <CallRunsList callRuns={callRuns} />
            </TabsContent>
          </Tabs>
        </CardContent>
      )}
    </Card>
  );
}

function CallRunsList({ callRuns }: { callRuns: CallRunDto[] }) {
  if (callRuns.length === 0) {
    return (
      <p className="text-body-sm text-muted-foreground">No call runs yet.</p>
    );
  }
  return (
    <div className="space-y-2">
      {callRuns.map((run) => (
        <div
          key={run.id}
          className="flex items-center justify-between rounded-md border bg-card p-3"
        >
          <div className="space-y-1">
            <p className="text-body-sm font-medium">Rep {run.repetition_no}</p>
            <p className="text-micro text-muted-foreground">
              {run.selected_attempt_id ?? "No attempt selected"}
            </p>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge status={run.status} />
            <span className="text-body-sm tabular-nums text-muted-foreground">
              {formatDurationMs(run.duration_ms)}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function ReadOnlyField({
  icon,
  label,
  value,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2 text-label uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="rounded-md border bg-card p-3 text-body-sm whitespace-pre-wrap">
        {value || "—"}
      </div>
    </div>
  );
}

function deriveDominantStatus(callRuns: CallRunDto[]): string {
  if (callRuns.length === 0) return "queued";
  if (callRuns.some((r) => r.status === "running")) return "running";
  if (callRuns.some((r) => r.status === "infrastructure_failed")) return "infrastructure_failed";
  if (callRuns.every((r) => r.status === "completed")) return "completed";
  return callRuns[0].status;
}

function averageScore(metrics: JudgeMetricDto[]): number | null {
  const values = metrics
    .map((m) => (typeof m.value === "number" ? m.value : null))
    .filter((v): v is number => v != null);
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function averageMetricScore(metrics: MetricResultDto[]): number | null {
  const values = metrics
    .filter((m) => m.status === "computed" && typeof m.value === "number")
    .map((m) => m.value as number);
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}
